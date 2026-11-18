"""Copilot 本地运行身份、任务隔离、工程发现及上下文选择回归。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

ROOT = Path(__file__).resolve().parents[2] / 'hap-mcp-app-builder'
if not ROOT.exists() and (Path(__file__).resolve().parents[2] / 'hap-app-copilot').exists():
    ROOT = Path(__file__).resolve().parents[2] / 'hap-app-copilot'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


runtime = module('build_runtime')
resolver = module('resolve_context')
merger = module('merge_worksheet_context')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name)

    def put(self, rel, data):
        path = self.app / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False))
        return path

    def plan(self, names=('订单',)):
        self.put('hap-plan.json', {'appName': '应用', 'org_id': 'org-a',
                                  'worksheets': [{'name': n, 'fields': []} for n in names]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'app_created'})

    def init(self, server='chosen-mcp'):
        return runtime.cmd_init(str(self.app), str(ROOT), server)

    def prepare(self):
        return runtime.cmd_prepare(str(self.app), None)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / script), *args],
                              capture_output=True, text=True)

    def receipt(self, task, run_id):
        return self.put(task['receiptPath'], {'taskId': task['taskId'], 'runId': run_id,
                        'status': 'succeeded', 'executor': {'kind': 'subagent', 'agentId': 'agent-a'},
                        'outputs': {'worksheetName': '订单', 'worksheetId': 'ws-a'},
                        'verification': {'passed': True, 'evidence': ['创建工具返回 ws-a']}})


class RunTests(Fixture):
    def test_reset_after_finalize_requires_fresh_report(self):
        self.plan()
        run = self.init()
        task = self.prepare()['readyTasks'][0]
        self.receipt(task, run['runId'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        runtime.cmd_reset_task(str(self.app), task['taskId'])
        rejected = runtime.cmd_advance(str(self.app))
        self.assertFalse(rejected['advanced'])
        self.assertEqual(task['taskId'], rejected['taskId'])
        self.assertEqual('app_created', json.loads((self.app / 'hap-context.json').read_text())['progress'])

    def test_finalize_separates_reset_capacity_and_running_tasks(self):
        self.plan(('入库', '出库', '调拨'))
        self.init()
        reset, queued, active = [task['taskId'] for task in self.prepare()['readyTasks']]
        runtime.cmd_record_dispatch(str(self.app), reset, 'agent-a', 'running')
        runtime.cmd_reset_task(str(self.app), reset)
        runtime.cmd_record_dispatch(str(self.app), queued, '', 'pending_capacity')
        runtime.cmd_record_dispatch(str(self.app), active, 'agent-b', 'running')
        report = runtime.cmd_finalize(str(self.app), None)
        self.assertFalse(report['canAdvance'])
        self.assertEqual(([reset], [queued], [active]), (
            report['plannedTaskIds'], report['pendingCapacityTaskIds'], report['runningTaskIds']))
        self.assertEqual([1, 1, 1], [report['taskSummary'][key] for key in ('planned', 'pendingCapacity', 'running')])

    def test_delivery_status_uses_receipt_evidence_across_stages(self):
        self.put('hap-plan.json', {'workflows': [{'name': '发布状态待核实', 'published': True},
                                                  {'name': '等待成员'}, {'name': '已上线'}],
                                   'worksheets': [{'name': '单据', 'customActions': [
                                       {'name': '提交', 'type': 'triggerWorkflow'}]}]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'config_completed'})
        run_id = self.init()['runId']
        for task in self.prepare()['readyTasks']:
            if task['step'] == '5':
                self.put(task['receiptPath'], {'taskId': task['taskId'], 'runId': run_id,
                                               'status': 'failed', 'issues': ['缺少测试数据']})
                continue
            path = self.receipt(task, run_id)
            receipt = json.loads(path.read_text())
            outputs = {'processId': task['taskId']}
            if '等待成员' in task['taskId']:
                outputs['status'] = 'draft'
            elif '已上线' in task['taskId']:
                outputs['published'] = True
            elif task['step'] == '11':
                outputs.update({'worksheetName': '单据', 'actionName': '提交', 'actionEnabled': False})
            receipt['outputs'] = outputs
            self.put(task['receiptPath'], receipt)
        page = 'step6-page-总览'
        self.put(f'.build/receipts/{page}.json', {'taskId': page, 'runId': run_id,
                 'outputs': {'completed': False, 'notes': ['缺库存趋势图']}})
        self.put('.build/receipts/step6-page-旧项目.json', {'taskId': 'step6-page-旧项目',
                 'runId': 'old', 'issues': ['历史遗留']})
        report = runtime.cmd_finalize(str(self.app), None)
        self.assertTrue(report['canAdvance'])
        notes = {note['taskId']: note for note in report['deliveryNotes']}
        self.assertEqual('unknown', notes['step10-sys-wf-发布状态待核实']['publicationStatus'])
        self.assertEqual('unknown', notes['step11-act-wf-单据_提交']['publicationStatus'])
        self.assertIs(False, notes['step11-act-wf-单据_提交']['actionEnabled'])
        self.assertEqual('draft', notes['step10-sys-wf-等待成员']['publicationStatus'])
        self.assertNotIn('step10-sys-wf-已上线', notes)
        self.assertNotIn('step6-page-旧项目', notes)
        self.assertEqual((False, ['缺库存趋势图']), (notes[page]['pageCompleted'], notes[page]['pageNotes']))
        self.assertTrue(runtime.cmd_advance(str(self.app))['advanced'])
        ctx = json.loads((self.app / 'hap-context.json').read_text())
        self.assertFalse(ctx.get('sampleDataCreated'))
        self.assertEqual('unknown', ctx['customActionWorkflowResults'][0]['status'])
        self.assertIs(False, ctx['customActionWorkflowResults'][0]['actionEnabled'])
        statuses = {item['name']: item['status'] for item in ctx['workflowResults']}
        self.assertEqual({'发布状态待核实': 'unknown', '等待成员': 'draft', '已上线': 'published'}, statuses)
        plan = json.loads((self.app / 'hap-plan.json').read_text())
        flags = {wf['name']: wf.get('published') for wf in plan['workflows']}
        self.assertEqual({'发布状态待核实': None, '等待成员': False, '已上线': True}, flags)

    def test_rule_delivery_evidence_for_created_reused_and_inapplicable_rules(self):
        self.put('.build/artifacts/worksheet-sheet-a.json', {'worksheetId': 'sheet-a',
                 'fields': [{'name': '分类名称', 'id': 'name-id', 'type': 'Text', 'required': True}]})
        cases = [
            ({'rulesCreated': 0}, True),
            ({'rulesCreated': 2}, True),
            ({'ruleIds': [], 'noApplicableRulesReason': '   '}, True),
            ({'ruleIds': ['']}, True),
            ({'rulesCreated': 0, 'ruleIds': ['existing-rule']}, True),
            ({'ruleIds': [], 'noApplicableRulesReason': '方案未列规则，已有必填和默认值'}, True),
            ({'worksheetId': 'sheet-a', 'ruleIds': [], 'checkedFieldIds': ['wrong-id'],
              'noApplicableRulesReason': '分类名称已必填'}, True),
            ({'worksheetId': 'sheet-a', 'ruleIds': [], 'checkedFieldIds': ['name-id'],
              'noApplicableRulesReason': '分类仅维护名称；空名称由字段必填拦截，无状态或跨字段条件'}, True),
            ({'worksheetId': 'sheet-a', 'ruleIds': [], 'ruleChecks': [{
                'intent': '分类必须有名称', 'fieldId': 'name-id', 'property': 'required',
                'value': True, 'reason': '名称必填已覆盖这个条件'}]}, False),
            ({'worksheetId': 'sheet-a', 'ruleIds': ['r1'], 'ruleChecks': [{
                'intent': '不得重叠', 'ruleId': 'r1', 'name': '时间冲突', 'enabled': True,
                'conditions': {'type': 'group', 'children': [{'type': 'condition', 'fieldId': 'name-id', 'operator': 'eq'}]}}]}, False),
        ]
        for outputs, missing in cases:
            with self.subTest(outputs=outputs):
                task_id = 'step3-view-act-订单'
                self.put(f'.build/receipts/{task_id}.json', {
                    'taskId': task_id, 'runId': 'run', 'step': '3', 'outputs': outputs})
                notes = runtime.receipt_delivery_notes(str(self.app), 'run')
                self.assertEqual(missing, any(n.get('ruleEvidenceMissing') for n in notes))

    def test_incomplete_or_contradictory_booking_evidence(self):
        outputs = {'worksheetId': 'venue', 'ruleIds': [], 'ruleChecks': [{
            'intent': '名称必填', 'fieldId': 'title', 'property': 'required', 'value': True,
            'reason': '字段属性已设置'}]}
        self.put('.build/artifacts/worksheet-venue.json', {'worksheetId': 'venue',
                 'fields': [{'id': 'title', 'type': 'Text', 'required': True}]})
        self.assertFalse(runtime.has_rule_evidence(str(self.app), outputs, ['结束晚于开始']))
        outputs['ruleChecks'][0]['value'] = False
        self.assertFalse(runtime.has_rule_evidence(str(self.app), outputs))

    def test_old_receipts_report_unknown_page_and_action(self):
        for task in ['step6-page-A', 'step11-act-B']:
            self.put(f'.build/receipts/{task}.json', {'taskId': task, 'runId': 'run',
                                                       'outputs': {'status': 'published'}})
        notes = {n['taskId']: n for n in runtime.receipt_delivery_notes(str(self.app), 'run')}
        self.assertEqual('unknown', notes['step6-page-A']['pageCompleted'])
        self.assertEqual('unknown', notes['step11-act-B']['actionEnabled'])

    def test_dsl_field_attributes_preserve_known_and_unknown(self):
        fields = [{'id': 'a', 'type': 'Text', 'isTitle': True, 'required': True,
                   'defaultValue': [], 'layout': {'span': 6}, 'config': {'min': 0}},
                  {'id': 'b', 'type': 'Number', 'required': False}, {'id': 'c', 'type': 'Text'}]
        actual = merger.normalize_worksheet_shard(fields, 'ws', '预约')['fields']
        for src, dest in zip(fields, actual):
            for key, value in src.items():
                self.assertEqual(value, dest[key])
        self.assertNotIn('required', actual[2])
        self.assertNotIn('isTitle', actual[2])

    def test_role_task_projects_only_authorized_worksheet_action_ids(self):
        self.put('hap-plan.json', {'worksheets': [{'name': n, 'fields': []} for n in ('订单', '订单/分支', '客户')],
                                  'roles': [{'name': '申请人', 'permissions': ['订单(worksheet)']} ]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'fields_refreshed',
                                     'worksheetIdByName': {'订单': 'ws-a', '订单/分支': 'ws-b', '客户': 'ws-c'},
                                     'actionIdByName': {'订单/提交': 'action-a', '订单/分支/提交': 'action-b',
                                                        '客户/提交': 'action-c', '订单/缺失': ''}})
        self.init()
        task = next(t for t in self.prepare()['readyTasks'] if t['step'] == '8')
        context = json.loads(Path(task['taskContext']).read_text())
        self.assertEqual({'订单/提交': 'action-a'}, context['contextSlice']['actionIdByName'])
        # 恢复旧工程时无动作映射仍可正常准备。
        data = json.loads((self.app / 'hap-context.json').read_text())
        del data['actionIdByName']
        self.put('hap-context.json', data)
        task = next(t for t in self.prepare()['readyTasks'] if t['step'] == '8')
        self.assertEqual({}, json.loads(Path(task['taskContext']).read_text())['contextSlice']['actionIdByName'])

    def test_cli_requires_environment(self):
        result = self.cli('build_runtime.py', 'init', '--app-dir', str(self.app))
        self.assertNotEqual(0, result.returncode)
        self.assertIn('--mcp-server', result.stderr)
        self.assertFalse((self.app / '.build').exists())

    def test_missing_run_does_not_generate_tasks(self):
        self.plan()
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse((self.app / '.build').exists())

    def test_selected_environment_and_original_sources_are_propagated(self):
        self.plan(); run = self.init()
        task = self.prepare()['readyTasks'][0]
        context = json.loads(Path(task['taskContext']).read_text())
        self.assertEqual('chosen-mcp', context['mcpServer'])
        self.assertEqual(run['runId'], context['runId'])
        self.assertEqual(str(ROOT / 'HOST_ADAPTER.md'), context['hostAdapter'])
        self.assertEqual(context['sourceFiles'], task['sourceFiles'])
        self.assertEqual(str(self.app / 'hap-plan.json'), context['sourceFiles']['plan'])
        self.assertTrue(all(Path(p).is_file() for p in task['bundleFiles']))
        self.assertTrue(all('.build/task-bundles/' in p for p in task['bundleFiles']))
        for bf in task['bundleFiles']:
            raw = Path(bf).read_bytes()
            self.assertLess(len(raw), 46080)
            self.assertLess(len(raw.decode('utf-8').splitlines()), 800)
        # 原计划更新后仍能直接读取，不被任务生成时的副本遮蔽。
        self.put('hap-plan.json', {'requirements': ['新增跨表需求']})
        self.assertEqual(['新增跨表需求'], json.loads(Path(context['sourceFiles']['plan']).read_text())['requirements'])

    def test_worksheet_tasks_keep_complete_design_across_steps(self):
        worksheet = {'name': '联系人', 'fields': ['负责人(Lookup:客户.负责销售)'],
                     'views': ['我的联系人(Table)'], 'requirements': ['负责人变更后同步'],
                     'businessRules': ['姓名必填'], 'customActions': [{'name': '登记跟进'}]}
        self.put('hap-plan.json', {'worksheets': [worksheet]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'app_created',
                                     'worksheetIdByName': {'联系人': 'contact-id'}})
        self.init()
        for stage in ('app_created', 'step2a_done', 'worksheets_created'):
            with self.subTest(stage=stage):
                task = runtime.cmd_prepare(str(self.app), stage)['readyTasks'][0]
                context = json.loads(Path(task['taskContext']).read_text())
                self.assertEqual(worksheet, context['planSlice']['worksheet'])
                self.assertIn(str(ROOT / 'build/steps'), task['stepFile'])

    def test_init_reuses_run_without_rewriting(self):
        run = self.init(); original = (self.app / '.build/run.json').read_bytes()
        again = self.init()
        self.assertEqual(run['runId'], again['runId'])
        self.assertTrue(again['reused'])
        self.assertEqual(original, (self.app / '.build/run.json').read_bytes())

    def test_init_rejects_environment_change_without_overwrite(self):
        self.init(); original = (self.app / '.build/run.json').read_bytes()
        with self.assertRaises(ValueError): self.init('other-mcp')
        self.assertEqual(original, (self.app / '.build/run.json').read_bytes())

    def test_lost_run_with_history_cannot_be_reinitialized(self):
        self.put('.build/receipts/old.json', {'status': 'succeeded'})
        with self.assertRaises(ValueError): self.init()
        self.assertFalse((self.app / '.build/run.json').exists())

    def test_invalid_run_config_is_rejected(self):
        for data in ({'mcpServer': 'chosen-mcp'}, {'runId': 'x'}, {'runId': ' ', 'mcpServer': 'x'}):
            self.put('.build/run.json', data)
            with self.assertRaises(ValueError): self.prepare()

    def test_missing_or_wrong_receipt_run_cannot_pass_or_redispatch(self):
        self.plan(); self.init()
        task = self.prepare()['readyTasks'][0]
        for run_id in (None, '', 'old-run'):
            path = self.receipt(task, run_id)
            if run_id is None:
                data = json.loads(path.read_text()); del data['runId']; path.write_text(json.dumps(data))
            current = runtime.require_run(str(self.app))['runId']
            self.assertFalse(runtime.is_task_succeeded(str(path), task['taskId'], current, 'agent-a'))
            prepared = self.prepare()
            self.assertEqual([], prepared['readyTasks'])
            self.assertEqual([task['taskId']], [t['taskId'] for t in prepared['blockedTasks']])
            self.assertFalse(prepared['canAdvance'])
            self.assertFalse(runtime.cmd_finalize(str(self.app), None)['canAdvance'])

    def test_valid_receipt_skips_and_advances(self):
        self.plan(); run = self.init(); task = self.prepare()['readyTasks'][0]
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.receipt(task, run['runId'])
        result = self.prepare()
        self.assertEqual(1, result['completedCount']); self.assertEqual([], result['readyTasks'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        self.assertEqual('worksheets_created', runtime.cmd_advance(str(self.app))['newProgress'])

    def test_old_phase_report_cannot_advance(self):
        self.plan(); self.init()
        self.put('.build/phase-report.json', {'runId': 'old', 'canAdvance': True})
        before = (self.app / 'hap-context.json').read_bytes()
        with self.assertRaises(ValueError): runtime.cmd_advance(str(self.app))
        self.assertEqual(before, (self.app / 'hap-context.json').read_bytes())


class RecoveryTests(Fixture):
    def failed_receipt(self, task, run, agent='agent-a'):
        return self.put(task['receiptPath'], {
            'taskId': task['taskId'], 'runId': run['runId'], 'status': 'failed',
            'executor': {'kind': 'subagent', 'agentId': agent},
            'outputs': {'worksheetName': '订单', 'worksheetId': 'already-created'},
            'issues': ['表已创建，表单设置参数需要修正'],
        })

    def start(self):
        self.plan(); run = self.init(); task = self.prepare()['readyTasks'][0]
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        return run, task

    def test_failed_receipt_is_resumable_and_keeps_completed_outputs(self):
        run, task = self.start()
        path = self.failed_receipt(task, run); original = path.read_bytes()
        status = runtime.cmd_refresh(str(self.app))
        self.assertEqual((1, 0), (status['failed'], status['running']))
        prepared = self.prepare()
        self.assertEqual([task['taskId']], prepared['failedTaskIds'])
        self.assertEqual(0, prepared['runningTaskCount'])
        self.assertFalse(prepared['canAdvance'])
        resumed = prepared['readyTasks'][0]
        self.assertTrue(resumed['resume'])
        context = json.loads(Path(resumed['taskContext']).read_text())
        self.assertEqual('already-created', context['previousReceipt']['outputs']['worksheetId'])
        self.assertEqual(original, path.read_bytes())

    def test_incomplete_phase_is_a_recoverable_cli_result(self):
        run, task = self.start()
        path = self.failed_receipt(task, run)
        before = (self.app / 'hap-context.json').read_bytes()
        result = self.cli('build_runtime.py', 'finalize', '--app-dir', str(self.app))
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report['canAdvance'])
        self.assertEqual('prepare', report['nextAction'])
        result = self.cli('build_runtime.py', 'advance', '--app-dir', str(self.app))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)['advanced'])
        self.assertEqual(before, (self.app / 'hap-context.json').read_bytes())
        resumed = self.prepare()['readyTasks'][0]
        self.assertEqual(task['taskId'], resumed['taskId'])
        self.assertTrue(resumed['resume'])
        self.assertEqual(json.loads(path.read_text()),
                         json.loads(Path(resumed['taskContext']).read_text())['previousReceipt'])

    def test_other_phase_can_prepare_without_skipping_incomplete_progress(self):
        self.put('hap-plan.json', {'worksheets': [{'name': '订单', 'fields': []}],
                                  'customPages': [{'name': '概览'}]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'worksheets_created',
                                     'worksheetIdByName': {'订单': 'ws-a'},
                                     'customPageIdByName': {'概览': 'page-a'}})
        run = self.init()
        failed_task = self.prepare()['readyTasks'][0]
        runtime.cmd_record_dispatch(str(self.app), failed_task['taskId'], 'agent-a', 'running')
        failed_path = self.failed_receipt(failed_task, run)
        original_receipt = failed_path.read_bytes()
        self.assertFalse(runtime.cmd_finalize(str(self.app), None)['canAdvance'])

        later = runtime.cmd_prepare(str(self.app), 'fields_refreshed')
        page = next(t for t in later['readyTasks'] if t['step'] == '6')
        inputs = json.loads(Path(page['taskContext']).read_text())
        self.assertEqual('page-a', inputs['contextSlice']['pageId'])
        self.assertEqual(run['runId'], inputs['runId'])
        self.assertEqual(str(self.app / '.build/receipts'), inputs['sourceFiles']['receipts'])
        # 提前完成的页面有独立回执，不能令未完成的全局阶段跳步。
        self.put(page['receiptPath'], {
            'taskId': page['taskId'], 'runId': run['runId'], 'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'agent-a'},
            'outputs': {'pageId': 'page-a', 'pageName': '概览'},
            'verification': {'passed': True, 'evidence': ['页面配置已保存']},
        })
        runtime.cmd_record_dispatch(str(self.app), page['taskId'], 'agent-a', 'running')
        self.assertTrue(runtime.cmd_finalize(str(self.app), 'fields_refreshed')['canAdvance'])
        self.assertFalse(runtime.cmd_advance(str(self.app))['advanced'])
        self.assertEqual('worksheets_created', json.loads((self.app / 'hap-context.json').read_text())['progress'])
        self.assertEqual(original_receipt, failed_path.read_bytes())
        self.assertTrue(self.prepare()['readyTasks'][0]['resume'])
        # 再次准备后续阶段时复用成功回执，不重建页面。
        again = runtime.cmd_prepare(str(self.app), 'fields_refreshed')
        self.assertNotIn(page['taskId'], [t['taskId'] for t in again['readyTasks']])
        self.assertEqual(1, again['completedCount'])

    def test_redispatched_task_does_not_retry_again_from_old_failure(self):
        run, task = self.start()
        path = self.failed_receipt(task, run); original = path.read_bytes()
        self.prepare()
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-b', 'running')
        # 重复登记不会遗失续作状态，也不会删除旧执行证据。
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-b', 'running')
        prepared = self.prepare()
        self.assertEqual([], prepared['readyTasks'])
        self.assertEqual(1, prepared['runningTaskCount'])
        self.assertEqual(1, runtime.cmd_refresh(str(self.app))['running'])
        report = runtime.cmd_finalize(str(self.app), None)
        self.assertEqual([], report['failedTaskIds'])
        self.assertFalse(report['canAdvance'])
        self.assertEqual(original, path.read_bytes())
        self.receipt(task, run['runId'])
        data = json.loads(path.read_text()); data['executor']['agentId'] = 'agent-b'
        path.write_text(json.dumps(data))
        self.assertEqual(1, self.prepare()['completedCount'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])

    def test_same_agent_new_identical_failure_is_detected(self):
        run, task = self.start()
        path = self.failed_receipt(task, run)
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.assertEqual([], self.prepare()['readyTasks'])
        modified = path.stat().st_mtime_ns
        self.failed_receipt(task, run)
        os.utime(path, ns=(modified + 1000000, modified + 1000000))
        self.assertEqual(1, runtime.cmd_refresh(str(self.app))['failed'])
        self.assertTrue(self.prepare()['readyTasks'][0]['resume'])

    def test_fast_failure_before_first_dispatch_registration_is_not_hidden(self):
        self.plan(); run = self.init(); task = self.prepare()['readyTasks'][0]
        self.failed_receipt(task, run)
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.assertEqual(1, runtime.cmd_refresh(str(self.app))['failed'])
        self.assertTrue(self.prepare()['readyTasks'][0]['resume'])

    def test_fast_failure_after_capacity_wait_is_not_hidden(self):
        self.plan(); run = self.init(); task = self.prepare()['readyTasks'][0]
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], '', 'pending_capacity')
        self.failed_receipt(task, run)
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.assertEqual(1, runtime.cmd_refresh(str(self.app))['failed'])
        self.assertTrue(self.prepare()['readyTasks'][0]['resume'])

    def test_capacity_wait_is_returned_by_default_cli_and_cannot_advance(self):
        _, task = self.start()
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], '', 'pending_capacity')
        result = self.cli('build_runtime.py', 'prepare', '--app-dir', str(self.app))
        self.assertEqual(0, result.returncode, result.stderr)
        prepared = json.loads(result.stdout)
        self.assertEqual([task['taskId']], [t['taskId'] for t in prepared['readyTasks']])
        self.assertEqual(1, prepared['pendingCapacityCount'])
        self.assertFalse(prepared['canAdvance'])
        report = runtime.cmd_finalize(str(self.app), None)
        self.assertEqual(1, report['taskSummary']['pendingCapacity'])
        self.assertFalse(report['canAdvance'])
        self.assertFalse(runtime.cmd_prepare(str(self.app), None, False)['canAdvance'])
        runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.assertEqual([], self.prepare()['readyTasks'])

    def test_bad_receipt_is_isolated_without_overwriting_other_task_or_evidence(self):
        self.plan(('订单', '客户')); run = self.init()
        bad, other = self.prepare()['readyTasks']
        runtime.cmd_record_dispatch(str(self.app), bad['taskId'], 'agent-a', 'running')
        cases = ['malformed', 'wrong_run', 'wrong_task', 'empty_agent', 'missing_evidence', 'invalid_status']
        for case in cases:
            with self.subTest(case=case):
                path = self.receipt(bad, run['runId'])
                data = json.loads(path.read_text())
                if case == 'wrong_run': data['runId'] = 'old-run'
                if case == 'wrong_task': data['taskId'] = 'other-task'
                if case == 'empty_agent': data['executor']['agentId'] = '   '
                if case == 'missing_evidence': data['verification']['evidence'] = []
                if case == 'invalid_status': data['status'] = []
                path.write_text('{' if case == 'malformed' else json.dumps(data))
                original = path.read_bytes()
                context_before = Path(bad['taskContext']).read_bytes()
                prepared = self.prepare()
                self.assertEqual([other['taskId']], [t['taskId'] for t in prepared['readyTasks']])
                self.assertEqual([bad['taskId']], [t['taskId'] for t in prepared['blockedTasks']])
                self.assertFalse(prepared['canAdvance'])
                self.assertEqual(1, runtime.cmd_refresh(str(self.app))['blocked'])
                self.assertFalse(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
                self.assertEqual(original, path.read_bytes())
                self.assertEqual(context_before, Path(bad['taskContext']).read_bytes())
        # reset-task 安全归档异常回执并解除阻塞，使其重新进入 readyTasks。
        rst = runtime.cmd_reset_task(str(self.app), bad['taskId'])
        self.assertTrue(rst['reset'])
        self.assertTrue(Path(rst['archivedReceipt']).is_file())
        re_prepared = self.prepare()
        self.assertEqual([], re_prepared['blockedTasks'])
        self.assertIn(bad['taskId'], [t['taskId'] for t in re_prepared['readyTasks']])
        # 宿主异步派发 ID (host-conv-uuid) 与子代理自报 ID (subagent-self-id) 不同时绝不死锁。
        runtime.cmd_record_dispatch(str(self.app), bad['taskId'], 'host-conv-uuid', 'running')
        path = self.receipt(bad, run['runId'])
        data = json.loads(path.read_text()); data['executor']['agentId'] = 'subagent-self-id'
        path.write_text(json.dumps(data))
        recovered = self.prepare()
        self.assertEqual([], recovered['blockedTasks'])
        self.assertEqual(1, recovered['completedCount'])
        self.assertEqual([other['taskId']], [t['taskId'] for t in recovered['readyTasks']])

    def test_background_step5_does_not_block_prepare_or_refresh_can_advance(self):
        self.put('hap-plan.json', {'worksheets': [{'name': '订单', 'fields': []}], 'roles': [{'name': '销售'}]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'fields_refreshed', 'worksheetIdByName': {'订单': 'ws-a'}})
        run = self.init()
        tasks = self.prepare()['readyTasks']
        role_task = next(t for t in tasks if t['step'] == '8')
        step5_task = next(t for t in tasks if t['step'] == '5')
        runtime.cmd_record_dispatch(str(self.app), step5_task['taskId'], 'bg-agent', 'running')
        runtime.cmd_record_dispatch(str(self.app), role_task['taskId'], 'role-agent', 'running')
        self.put(role_task['receiptPath'], {
            'taskId': role_task['taskId'], 'runId': run['runId'], 'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'role-subagent'},
            'outputs': {'roleName': '销售', 'roleId': 'role-1'},
            'verification': {'passed': True, 'evidence': ['create_role ok']},
        })
        prep_after = self.prepare()
        self.assertTrue(prep_after['canAdvance'])
        self.assertTrue(runtime.cmd_refresh(str(self.app))['phaseComplete'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])

    def test_resolve_task_reconciles_failed_receipt_after_rework_and_completes_build(self):
        self.put('hap-plan.json', {
            'appName': '图书借阅',
            'worksheets': [{'name': '借阅记录', 'fields': [], 'customActions': [{'name': '申请续借', 'type': 'triggerWorkflow', 'intentHints': [{'label': '顺延日期'}]}]}],
        })
        self.put('hap-context.json', {
            'appId': 'app-a', 'progress': 'config_completed',
            'worksheetIdByName': {'借阅记录': 'ws-borrow'},
            'actionProcessIdByKey': {'借阅记录::申请续借': 'proc-old'},
        })
        run = self.init()
        act_task = self.prepare()['readyTasks'][0]
        runtime.cmd_record_dispatch(str(self.app), act_task['taskId'], 'agent-11', 'running')
        self.failed_receipt(act_task, run)
        self.assertFalse(runtime.cmd_finalize(str(self.app), None)['canAdvance'])

        # 返工修复后通过 resolve-task 回收旧失败回执并同步新 processId，工程顺利收口至 completed
        res = runtime.cmd_resolve_task(
            str(self.app),
            act_task['taskId'],
            '已补充续借日期字段并完成 updateCurrentRecord 关联动作流发布核验',
            json.dumps({'worksheetName': '借阅记录', 'actionName': '申请续借', 'processId': 'proc-new', 'status': 'published'}),
        )
        self.assertTrue(res['resolved'])
        self.assertTrue(Path(res['archivedPreviousReceipt']).is_file())
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        adv = runtime.cmd_advance(str(self.app))
        self.assertTrue(adv['advanced'])
        self.assertEqual('completed', adv['newProgress'])

    def test_validate_plan_warns_same_action_intents_and_bad_explicit_view_bindings(self):
        self.put('hap-plan.json', {
            'worksheets': [
                {'name': '调拨单', 'views': ['全部(Table)', '在途(Table)'], 'fields': []},
                {'name': '出库单', 'views': ['待出库(Table)'], 'fields': []},
            ],
            'customActions': [{'worksheet': '调拨单', 'actions': [
                {'name': '确认调出', 'type': 'triggerWorkflow', 'intentHints': [{'label': '确认调出：更新状态及台账'}]},
                {'name': '确认调入', 'type': 'triggerWorkflow', 'intentHints': [{'label': '确认调入：更新状态及台账'}]},
                {'name': '作废', 'type': 'triggerWorkflow', 'intentHints': [{'label': '记录作废原因'}]},
            ]}],
            'customPages': [{'name': '工作台', 'components': ['待出库(View)', '在途(View)'],
                             'viewBindings': {'待出库': {'worksheet': '调拨单', 'view': '待出库'},
                                              '在途': {'worksheet': '调拨单', 'view': '在途'}}}],
        })
        report = runtime.cmd_validate_plan(str(self.app))
        self.assertTrue(report['passed'])
        self.assertTrue(any('意图相同' in w and '确认调出' in w and '确认调入' in w for w in report['warnings']))
        self.assertTrue(any('调拨单/待出库' in w for w in report['warnings']))
        self.assertFalse(any('调拨单/在途' in w for w in report['warnings']))

    def test_validate_plan_legacy_and_malformed_optional_bindings_are_nonblocking(self):
        self.put('hap-plan.json', {'worksheets': [{'name': '出库单', 'fields': [], 'views': ['全部(Table)']}],
            'customPages': [{'name': '旧页面', 'components': ['全部(View)']},
                            {'name': '新页面', 'components': ['全部(View)'],
                             'viewBindings': {'全部': {'worksheet': '出库单', 'view': '全部'},
                                              '异常': None}}]})
        report = runtime.cmd_validate_plan(str(self.app))
        self.assertTrue(report['passed'])
        self.assertEqual(1, report['warningCount'])
        self.assertIn('异常', report['warnings'][0])

    def test_validate_plan_catches_broken_relations_and_warns_inputless_trigger_actions(self):
        self.put('hap-plan.json', {
            'appName': '图书借阅',
            'navGroups': ['借阅服务'],
            'worksheets': [
                {'name': '图书', 'groupName': '借阅服务', 'fields': ['书名(Text)']},
                {'name': '采购明细', 'worksheetType': 'subTable', 'parentWorksheet': '不存在主表', 'fields': ['数量(Number)']},
            ],
            'customActions': [
                {
                    'worksheet': '图书',
                    'actions': [
                        {'name': '发起借阅', 'type': 'triggerWorkflow', 'description': '选择借阅人并填写应还日期', 'intentHints': [{'label': '生成借阅记录'}]},
                        {'name': '报修登记', 'type': 'createRelatedRecord', 'targetWorksheet': '图书', 'relateFieldName': '不存在关联字段'},
                        {'name': '审批通过', 'type': 'triggerWorkflow', 'intentHints': [{'label': '通过'}]},
                    ],
                }
            ],
        })
        bad_res = self.cli('build_runtime.py', 'validate-plan', '--app-dir', str(self.app))
        self.assertEqual(1, bad_res.returncode)
        report = json.loads(bad_res.stdout)
        self.assertFalse(report['passed'])
        self.assertGreaterEqual(report['errorCount'], 3)
        self.assertTrue(any('发起借阅' in w and 'triggerWorkflow' in w for w in report['warnings']))

        # 修正为合规方案后 validate-plan 返回 0
        self.put('hap-plan.json', {
            'appName': '图书借阅',
            'navGroups': ['借阅服务'],
            'worksheets': [
                {'name': '图书', 'groupName': '借阅服务', 'fields': ['书名(Text)', '借阅明细(Relation:借阅记录:multiple:bi)']},
                {'name': '借阅记录', 'groupName': '借阅服务', 'fields': ['借阅人(Collaborator)', '应还日期(Date)']},
            ],
            'customActions': [
                {
                    'worksheet': '图书',
                    'actions': [
                        {
                            'name': '发起借阅',
                            'type': 'createRelatedRecord',
                            'targetWorksheet': '借阅记录',
                            'relateFieldName': '借阅明细',
                            'runWorkflowAfterSubmit': True,
                            'intentHints': [{'label': '借出后自动扣减图书可借库存'}],
                        }
                    ],
                }
            ],
        })
        ok_res = self.cli('build_runtime.py', 'validate-plan', '--app-dir', str(self.app))
        self.assertEqual(0, ok_res.returncode, ok_res.stderr)
        ok_report = json.loads(ok_res.stdout)
        self.assertTrue(ok_report['passed'])
        self.assertEqual(0, ok_report['warningCount'])


class TaskContextRegressionTests(Fixture):
    def test_portal_flag_belongs_to_app_creation(self):
        self.plan()
        self.init()
        for flag in (True, False, None):
            plan = {} if flag is None else {'enableExternalPortal': flag}
            self.put('hap-plan.json', plan)
            creation = runtime.get_stage_tasks_definitions(str(self.app), 'step1')[0]
            self.assertIs(creation['planSlice']['enableExternalPortal'], flag is True)
            self.assertIn('create_app', creation['allowedTools'])
            self.put('hap-context.json', {'appId': 'app-a', 'progress': 'config_completed'})
            report = runtime.cmd_finalize(str(self.app), None)
            self.assertTrue(report['canAdvance'])
            self.assertEqual('completed', report['nextProgress'])

    def test_brief_plan_dispatches_domain_specs_and_explicit_exclusions(self):
        pages = [{'name': name, 'type': 'workspace', 'components': ['待办(View)']}
                 for name in ('工作台', '纯列表')]
        pages[1]['requirements'] = ['本页不需要统计图']
        self.put('hap-plan.json', {'worksheets': [{'name': '单据', 'views': ['待办(Table)']}],
                                   'customPages': pages})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'worksheets_created'})
        self.init()
        tasks = self.prepare()['readyTasks']
        tasks += runtime.cmd_prepare(str(self.app), 'fields_refreshed')['readyTasks']
        references = {'3': 'hap-domain-view-spec.md', '5': 'hap-sample-data-spec.md',
                      '6': 'hap-domain-custom-page-spec.md'}
        targets = [task for task in tasks if task['step'] in references]
        self.assertEqual(['3', '5', '6', '6'], sorted(t['step'] for t in targets))
        for task in targets:
            parts = [Path(f).read_text() for f in task['bundleFiles']]
            self.assertIn('Plan 未逐项列出的配置也按规范补全', parts[0])
            bundle = ''.join(parts)
            self.assertIn(references[task['step']], bundle)
            self.assertNotIn('同一轮并行 `read_file`', bundle)
            if task['step'] == '6':
                page = json.loads(Path(task['taskContext']).read_text())['planSlice']['page']
                self.assertEqual(page['name'] == '纯列表', '本页不需要统计图' in bundle)

    def test_worksheet_usage_only_includes_related_business_context(self):
        self.plan(('预约', '场地'))
        path = self.app / 'hap-plan.json'
        plan = json.loads(path.read_text())
        plan.update(roles=[{'name': '接待员', 'permissions': ['预约(worksheet)']}],
                    workflows=[{'name': '预约提醒', 'trigger': {'source': '预约'}}],
                    customActions=[{'worksheet': '场地', 'actions': [{'name': '开放'}]}])
        path.write_text(json.dumps(plan))
        self.init()
        for task in self.prepare()['readyTasks']:
            ctx = json.loads(Path(task['taskContext']).read_text())
            usage = ctx['planSlice']['worksheetUsage']
            booking = ctx['target']['name'] == '预约'
            self.assertEqual(['预约提醒'] if booking else [], [w['name'] for w in usage['workflows']])
            self.assertEqual(['接待员'] if booking else [], [r['name'] for r in usage['roles']])
            self.assertEqual([] if booking else ['开放'], [a['name'] for a in usage['actions']])

    def test_booking_constraints_reach_the_correct_worksheet_after_advance(self):
        self.plan(('预约', '场地'))
        run_id = self.init()['runId']
        note = '结束时间应晚于开始时间'
        for task in self.prepare()['readyTasks']:
            path = self.receipt(task, run_id)
            data = json.loads(path.read_text())
            name = json.loads(Path(task['taskContext']).read_text())['target']['name']
            data['outputs'] = {'worksheetName': name, 'worksheetId': 'sheet-' + name}
            if name == '预约':
                data['outputs'].update(businessRulesNotes=[note], relationLayout=[{
                    'name': '预约场地', 'targetWorksheet': '场地', 'fieldType': 'Relation',
                    'alias': 'venue', 'required': True}])
            self.put(task['receiptPath'], data)
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        self.assertTrue(runtime.cmd_advance(str(self.app))['advanced'])
        group = self.prepare()['readyTasks'][0]
        layout = json.loads(Path(group['taskContext']).read_text())['planSlice']['items'][0]['relationLayout']
        self.assertTrue(layout[0]['required'])
        tasks = runtime.cmd_prepare(str(self.app), 'worksheets_created')['readyTasks']
        for task in tasks:
            ctx = json.loads(Path(task['taskContext']).read_text())
            expected = [note] if ctx['target']['name'] == '预约' else []
            self.assertEqual(expected, ctx['contextSlice']['businessRulesNotes'])

        # 已越过建表阶段，更新同一批次的有效回执后再次 prepare。
        receipt_path = self.app / '.build/receipts/step2a-ws-预约.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['outputs']['businessRulesNotes'] = ['时间段不可交叠']
        receipt_path.write_text(json.dumps(receipt))
        tasks = runtime.cmd_prepare(str(self.app), 'worksheets_created')['readyTasks']
        booking = next(t for t in tasks if t['taskId'] == 'step3-view-act-预约')
        self.assertEqual(['时间段不可交叠'], json.loads(Path(booking['taskContext']).read_text())
                         ['contextSlice']['businessRulesNotes'])

    def test_only_parent_task_gets_subtable_display_repair_access(self):
        # 父子表可以由不同关联组构建：阶段 3 必须由父表任务核对最终列。
        self.put('hap-plan.json', {'worksheets': [
            {'name': '入库单', 'fields': ['入库明细(SubTable:入库明细)']},
            {'name': '入库明细', 'worksheetType': 'subTable', 'parentWorksheet': '入库单',
             'fields': ['物料(Relation:物料:single:uni)']},
            {'name': '物料', 'fields': ['名称(Text)']},
        ]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'worksheets_created',
            'worksheetIdByName': {'入库单': 'parent-id', '入库明细': 'child-id', '物料': 'material-id'},
            'relationLayoutByWorksheet': {'入库单': [{'name': '入库明细', 'alias': 'biz_lines',
                'fieldType': 'SubTable', 'targetWorksheet': '入库明细'}]}})
        self.init()
        tasks = self.prepare()['readyTasks']
        loaded = [json.loads(Path(t['taskContext']).read_text()) for t in tasks]
        contexts = {ctx['target']['name']: ctx for ctx in loaded}
        parent, child = contexts['入库单'], contexts['入库明细']
        self.assertIn('update_worksheet', parent['allowedTools'])
        self.assertNotIn('update_worksheet', child['allowedTools'])
        self.assertNotIn('update_worksheet', contexts['物料']['allowedTools'])
        self.assertEqual([{'name': '入库明细', 'alias': 'biz_lines', 'worksheetName': '入库明细',
                           'worksheetId': 'child-id'}], parent['contextSlice']['subtableDisplayChecks'])
        self.assertEqual('step3-view-act-入库单', parent['taskId'])
        self.assertTrue(Path(parent['sourceFiles']['worksheetContext']).is_absolute())

    def test_workflow_bundles_preserve_full_context_and_legacy_role_mapping(self):
        field = {'id': 'field-id', 'name': '状态', 'alias': 'biz_state', 'type': 'SingleSelect',
                 'options': [{'key': 'key-a', 'value': '待审批'}], 'config': {'custom': 'preserve-me'}}
        self.put('hap-plan.json', {'worksheets': [{'name': '出库单', 'fields': []}],
            'workflows': [{'name': '库存预警', 'trigger': {'type': 'worksheet_event', 'source': '出库单'}}]})
        self.put('hap-context.json', {'appId': 'app-a', 'progress': 'config_completed',
            'worksheetIdByName': {'出库单': 'sheet-id'}, 'roleContext': [{'name': '仓管', 'id': 'old-role', 'note': '保留'}],
            'roleIdByName': {'仓管': 'old-role', '审批人': 'role-new'}})
        self.put('worksheetContext.json', {'worksheets': [{'worksheetId': 'sheet-id',
            'worksheetName': '出库单', 'fields': [field]}]})
        self.init()
        standard = next(t for t in self.prepare()['readyTasks'] if t['step'] == '10')
        full = json.loads(Path(standard['taskContext']).read_text())
        standard_bundle = '\n'.join(Path(p).read_text() for p in standard['bundleFiles'])
        self.assertEqual(field, full['worksheetContextSlice']['worksheets'][0]['fields'][0])
        self.assertIn('preserve-me', standard_bundle)
        self.assertEqual([{'name': '仓管', 'id': 'old-role', 'note': '保留'},
                          {'name': '审批人', 'id': 'role-new'}], full['contextSlice']['roleContext'])
        self.assertEqual('role-new', full['contextSlice']['roleIdByName']['审批人'])


class TaskTests(Fixture):
    def test_colliding_tasks_complete_independently(self):
        self.plan(('客户 A', '客户_A')); run = self.init()
        tasks = self.prepare()['readyTasks']
        for index, task in enumerate(tasks):
            name = json.loads(Path(task['taskContext']).read_text())['target']['name']
            path = self.receipt(task, run['runId'])
            data = json.loads(path.read_text())
            data['outputs'] = {'worksheetName': name, 'worksheetId': f'ws-{index}'}
            path.write_text(json.dumps(data))
            runtime.cmd_record_dispatch(str(self.app), task['taskId'], 'agent-a', 'running')
        self.assertEqual(2, self.prepare()['completedCount'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        runtime.cmd_advance(str(self.app))
        context = json.loads((self.app / 'hap-context.json').read_text())
        self.assertEqual({'客户 A': 'ws-0', '客户_A': 'ws-1'}, context['worksheetIdByName'])

    def test_collisions_get_isolated_stable_paths(self):
        self.plan(('客户 A', '客户_A')); self.init()
        tasks = self.prepare()['readyTasks']
        self.assertEqual(2, len({t['taskId'] for t in tasks}))
        self.assertEqual(2, len({t['receiptPath'] for t in tasks}))
        def identities(items):
            return {json.loads(Path(t['taskContext']).read_text())['target']['name']: t['taskId'] for t in items}
        before = identities(tasks)
        self.plan(('客户_A', '客户 A'))
        self.assertEqual(before, identities(self.prepare()['readyTasks']))
        self.plan(('客户 A',))
        self.assertEqual(before['客户 A'], self.prepare()['readyTasks'][0]['taskId'])

    def test_existing_unambiguous_id_is_unchanged(self):
        self.plan(); self.init()
        self.assertEqual('step2a-ws-订单', self.prepare()['readyTasks'][0]['taskId'])

    def test_ambiguous_legacy_history_stops_before_writing(self):
        self.plan(('客户 A', '客户_A')); self.init()
        old = self.put('.build/task-context/step2a-ws-客户_A.json', {'legacy': True})
        before = old.read_bytes()
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(before, old.read_bytes())
        self.assertEqual([], list((self.app / '.build/task-bundles').glob('*.md')))

    def test_duplicate_targets_and_case_insensitive_paths_are_rejected(self):
        self.init()
        for names in [('订单', '订单'), ('Orders', 'orders')]:
            self.plan(names)
            with self.assertRaises(ValueError): self.prepare()

    def test_step2b_small_app_packs_into_single_group(self):
        worksheets = [
            {'name': '字典', 'fields': ['编码(Text)']},
            {'name': '客户', 'fields': ['名称(Text)']},
            {'name': '订单', 'fields': ['所属客户(Relation:客户:bi)']},
            {'name': '回款', 'fields': ['关联订单(Relation:订单:bi)']},
        ]
        self.put('hap-plan.json', {'worksheets': worksheets})
        self.put('hap-context.json', {
            'appId': 'app-a',
            'progress': 'step2a_done',
            'worksheetIdByName': {w['name']: f"id-{i}" for i, w in enumerate(worksheets)},
        })
        self.init()
        prepared = self.prepare()
        self.assertEqual(1, len(prepared['readyTasks']))
        task = prepared['readyTasks'][0]
        self.assertEqual('step2b-rel-group-1', task['taskId'])
        ctx = json.loads(Path(task['taskContext']).read_text())
        self.assertEqual(['订单', '回款'], ctx['target']['worksheets'])
        self.assertEqual(['字典', '客户', '订单', '回款'], ctx['planSlice']['allWorksheetOrder'])

    def test_step2b_groups_connected_worksheets_and_enforces_complete_group_receipt(self):
        worksheets = [
            {'name': '字典', 'fields': ['名称(Text)']},
            {'name': '客户', 'fields': ['名称(Text)']},
            {'name': '仓库', 'fields': ['名称(Text)']},
            {'name': '商机', 'fields': ['客户(Relation:客户:bi)']},
            {'name': '入库单', 'fields': ['仓库(Relation:仓库:bi)']},
            {'name': '订单', 'fields': ['客户(Relation:客户:bi)']},
            {'name': '出库单', 'fields': ['仓库(Relation:仓库:bi)']},
            {'name': '回款', 'fields': ['客户(Relation:客户:bi)']},
            {'name': '盘点单', 'fields': ['仓库(Relation:仓库:bi)']},
        ]
        self.put('hap-plan.json', {'worksheets': worksheets})
        self.put('hap-context.json', {
            'appId': 'app-a',
            'progress': 'step2a_done',
            'worksheetIdByName': {w['name']: f"id-{i}" for i, w in enumerate(worksheets)},
        })
        run = self.init()
        tasks = self.prepare()['readyTasks']
        # 6 张待回填表（超过单组上限 5），共享同一主表（客户 / 仓库）的表各自聚在同一连通组内：3 + 3
        self.assertEqual(['step2b-rel-group-1', 'step2b-rel-group-2'], [t['taskId'] for t in tasks])
        ctx1 = json.loads(Path(tasks[0]['taskContext']).read_text())
        ctx2 = json.loads(Path(tasks[1]['taskContext']).read_text())
        self.assertEqual(['商机', '订单', '回款'], ctx1['target']['worksheets'])
        self.assertEqual(['入库单', '出库单', '盘点单'], ctx2['target']['worksheets'])

        # 组 1 漏掉「回款」却报 succeeded 时必须被拦截为 blocked，禁止闯关进入 Step 3
        self.put(tasks[0]['receiptPath'], {
            'taskId': tasks[0]['taskId'], 'runId': run['runId'], 'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'rel-agent-1'},
            'outputs': {'completedWorksheets': [{'worksheetName': '商机'}, {'worksheetName': '订单'}]},
            'verification': {'passed': True, 'evidence': ['update_worksheet ok']},
        })
        self.put(tasks[1]['receiptPath'], {
            'taskId': tasks[1]['taskId'], 'runId': run['runId'], 'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'rel-agent-2'},
            'outputs': {'completedWorksheets': ['入库单', '出库单', '盘点单']},
            'verification': {'passed': True, 'evidence': ['update_worksheet ok']},
        })
        check = self.prepare()
        self.assertFalse(check['canAdvance'])
        self.assertEqual([tasks[0]['taskId']], [b['taskId'] for b in check['blockedTasks']])
        self.assertIn('回款', check['blockedTasks'][0]['reason'])

        # 补齐组 1 完整列表后放行推进至 worksheets_created
        self.put(tasks[0]['receiptPath'], {
            'taskId': tasks[0]['taskId'], 'runId': run['runId'], 'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'rel-agent-1'},
            'outputs': {'completedWorksheets': ['商机', '订单', '回款']},
            'verification': {'passed': True, 'evidence': ['update_worksheet ok']},
        })
        self.assertTrue(self.prepare()['canAdvance'])
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        self.assertEqual('worksheets_created', runtime.cmd_advance(str(self.app))['newProgress'])


class ScanTests(Fixture):
    def scan(self):
        result = self.cli('scan_apps.py', str(self.app))
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)['apps']

    def test_same_name_different_orgs_remain_visible(self):
        self.put('.hap-copilot/apps/new/hap-plan.json', {'appName': '同名', 'org_id': 'org-a'})
        self.put('apps/old/hap-plan.json', {'appName': '同名', 'org_id': 'org-b'})
        self.put('apps/old/hap-context.json', {'appId': 'app-b', 'progress': 'app_created'})
        self.put('apps/old/.build/run.json', {'runId': 'old-run', 'mcpServer': 'other-mcp'})
        apps = self.scan()
        self.assertEqual(2, len(apps)); self.assertEqual({'org-a', 'org-b'}, {x['orgId'] for x in apps})
        old = next(x for x in apps if x['legacyLocation'])
        self.assertEqual(('app-b', 'other-mcp', 'old-run'), (old['appId'], old['mcpServer'], old['runId']))

    def test_unknown_identity_is_not_merged_by_name(self):
        for p in ('.hap-copilot/apps/a', 'apps/b'): self.put(p + '/hap-plan.json', {'appName': '同名'})
        self.assertEqual(2, len(self.scan()))

    def test_same_physical_project_via_symlink_is_not_duplicated(self):
        self.put('.hap-copilot/apps/a/hap-plan.json', {'appName': '项目'})
        (self.app / 'apps').mkdir()
        (self.app / 'apps/alias').symlink_to(self.app / '.hap-copilot/apps/a', target_is_directory=True)
        self.assertEqual(1, len(self.scan()))


class ResolveTests(Fixture):
    def test_validate_detects_existing_file_with_missing_mapped_section(self):
        original_open = open
        def changed_open(path, *args, **kwargs):
            if str(path).endswith('modify/modify_guide.md'):
                return io.StringIO((ROOT / 'modify/modify_guide.md').read_text().replace('## 5.', '## 第五章'))
            return original_open(path, *args, **kwargs)
        with patch.object(resolver, 'open', changed_open, create=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(resolver.validate_all_mappings())

    def test_unknown_domain_or_step_fails_without_partial_stdout(self):
        for args in [('--assets', 'workfow'), ('--assets', 'workflow,workfow'),
                     ('--mode', 'build', '--step', '9a'), ('--mode', 'modify', '--step', '3')]:
            result = self.cli('resolve_context.py', *args)
            self.assertNotEqual(0, result.returncode); self.assertEqual('', result.stdout)

    def test_missing_or_partly_missing_section_fails(self):
        for query in ('不存在', '执行步骤,不存在'):
            result = self.cli('resolve_context.py', '--file', 'modify/print-template-file.md', '--section', query)
            self.assertNotEqual(0, result.returncode); self.assertIn('可用章节', result.stderr)
            self.assertEqual('', result.stdout)

    def test_known_domain_aliases_and_steps_load(self):
        for key in resolver.MODIFY_GUIDE_SECTION_MAPPING:
            files = resolver.resolve_files('modify', [key])
            self.assertTrue(files)
            self.assertTrue(all((ROOT / p).exists() for p in files))
        for step in ('1', '1b', '2a', '2b', '3', '4', '4a', '4b', '5', '6', '7', '8', '10', '11'):
            self.assertTrue(any(p.startswith('build/steps/') for p in resolver.resolve_files('build', [], step=step)))

    def test_existing_section_and_print_alias_load(self):
        result = self.cli('resolve_context.py', '--file', 'modify/print-template-file.md', '--section', '执行步骤')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('replace_print_template_file', result.stdout)
        self.assertEqual(resolver.resolve_files('modify', ['template']), resolver.resolve_files('modify', ['print_template']))

    def test_data_mode_resolves_workflow_and_host_adapter(self):
        result = self.cli('resolve_context.py', '--mode', 'data', '--json')
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual('data', payload['mode'])
        self.assertIn('HOST_ADAPTER.md', payload['files'])
        self.assertIn('workflows/data.md', payload['files'])
        self.assertNotIn('modify/modify_guide.md', payload['files'])
        # --render 仅用于 modify，对 data 模式应拒绝混淆
        bad_render = self.cli('resolve_context.py', '--mode', 'data', '--render')
        self.assertNotEqual(0, bad_render.returncode)


class BuildPipelineResilienceTests(Fixture):
    def test_merge_worksheet_context_allows_self_relation_and_backfills_option_keys(self):
        ws_id = '6a0000000000000000000001'
        f_title = '6a0000000000000000000011'
        f_self = '6a0000000000000000000012'
        f_status = '6a0000000000000000000013'
        f_rollup = '6a0000000000000000000014'
        self.put('hap-plan.json', {'appName': '测试应用', 'worksheets': [{'name': '部门', 'fields': []}]})
        self.put('hap-context.json', {
            'appId': 'app-1',
            'worksheetIdByName': {'部门': ws_id},
            'fieldOptionsContext': {
                '部门.状态': [
                    {'key': 'opt-draft-key', 'value': '草稿', 'index': 1},
                    {'key': 'opt-active-key', 'value': '启用', 'index': 2},
                ]
            },
        })
        # 模拟 md 分片：ID 带 (isTitle)、自关联 dataSource="selfRelation"、选项缺 key、Rollup 省略 relationField
        self.put(f'.build/artifacts/worksheet-{ws_id}.json', {
            'worksheetId': ws_id,
            'worksheetName': '部门',
            'fields': [
                {'id': f'{f_title}(isTitle)', 'name': '部门名称(isTitle)', 'type': 'Text'},
                {'id': f_self, 'name': '上级部门', 'type': 'Relation', 'dataSource': 'selfRelation'},
                {'id': f_status, 'name': '状态', 'type': 'SingleSelect', 'options': [{'value': '草稿'}, {'value': '启用'}]},
                {'id': f_rollup, 'name': '下级数量', 'type': 'Rollup'},
            ],
        })
        res = self.cli('merge_worksheet_context.py', str(self.app))
        self.assertEqual(0, res.returncode, res.stderr + res.stdout)
        summary = json.loads((self.app / 'schema-validation.json').read_text())
        self.assertTrue(summary['passed'])
        self.assertEqual(0, summary['errorsCount'])
        self.assertGreaterEqual(summary['warningsCount'], 1)
        merged = json.loads((self.app / 'worksheetContext.json').read_text())
        fields = {f['name']: f for f in merged[0]['fields']}
        self.assertEqual(f_title, fields['部门名称']['id'])
        self.assertEqual('selfRelation', fields['上级部门']['dataSource'])
        self.assertEqual('opt-draft-key', fields['状态']['options'][0]['key'])

    def test_step5_slim_context_keeps_relation_datasource_and_filters_all_formulas(self):
        ws_cust = '6b0000000000000000000001'
        ws_order = '6b0000000000000000000002'
        self.put('hap-plan.json', {
            'appName': 'CRM',
            'worksheets': [{'name': '客户', 'fields': []}, {'name': '订单', 'fields': []}],
        })
        self.put('hap-context.json', {
            'appId': 'app-crm',
            'progress': 'fields_refreshed',
            'worksheetIdByName': {'客户': ws_cust, '订单': ws_order},
        })
        self.put('worksheetContext.json', {
            'worksheets': [
                {
                    'worksheetId': ws_order,
                    'worksheetName': '订单',
                    'fields': [
                        {'id': '6b0000000000000000000011', 'name': '订单号', 'alias': 'order_no', 'type': 'Text'},
                        {'id': '6b0000000000000000000012', 'name': '关联客户', 'alias': 'customer_rel', 'type': 'Relation', 'dataSource': ws_cust},
                        {'id': '6b0000000000000000000013', 'name': '到期天数', 'type': 'DateFormula'},
                        {'id': '6b0000000000000000000014', 'name': '大写金额', 'type': 'FormulaFunc'},
                        {'id': '6b0000000000000000000015', 'name': '汇总金额', 'type': 'Rollup'},
                    ],
                }
            ]
        })
        self.init()
        prepared = runtime.cmd_prepare(str(self.app), 'fields_refreshed')
        step5 = next(t for t in prepared['readyTasks'] if t['taskId'] == 'step5-sample-data')
        ctx = json.loads(Path(step5['taskContext']).read_text())
        fields = {f['name']: f for f in ctx['worksheetContextSlice']['worksheets'][0]['fields']}
        self.assertIn('订单号', fields)
        self.assertIn('关联客户', fields)
        self.assertEqual(ws_cust, fields['关联客户']['dataSource'])
        self.assertEqual('customer_rel', fields['关联客户']['alias'])
        self.assertNotIn('到期天数', fields)
        self.assertNotIn('大写金额', fields)
        self.assertNotIn('汇总金额', fields)

    def test_action_workflow_captures_workflow_id_alias_and_exposes_self_heal_tools(self):
        ws_id = '6c0000000000000000000001'
        self.put('hap-plan.json', {
            'appName': '审批中心',
            'worksheets': [{
                'name': '报销单',
                'fields': [],
                'customActions': [{'name': '提交审批', 'type': 'triggerWorkflow', 'intentHints': ['发起审批'], 'enabled': False}],
            }],
        })
        self.put('hap-context.json', {
            'appId': 'app-1',
            'progress': 'worksheets_created',
            'worksheetIdByName': {'报销单': ws_id},
        })
        run = self.init()
        stage2 = runtime.cmd_prepare(str(self.app), 'worksheets_created')
        step3_task = stage2['readyTasks'][0]
        step3_ctx = json.loads(Path(step3_task['taskContext']).read_text())
        self.assertIn('get_custom_action_list', step3_ctx['allowedTools'])
        self.assertIn('get_business_rule_list', step3_ctx['allowedTools'])
        runtime.cmd_record_dispatch(str(self.app), step3_task['taskId'], 'agent-s3', 'running')
        self.put(f'.build/artifacts/worksheet-{ws_id}.json', {
            'worksheetId': ws_id,
            'worksheetName': '报销单',
            'fields': [{'id': '6c0000000000000000000011', 'name': '报销事由', 'type': 'Text'}],
        })
        self.assertEqual(0, self.cli('merge_worksheet_context.py', str(self.app)).returncode)
        # Step 3 回执使用 create_custom_actions 原生字段名 workflowId
        self.put(step3_task['receiptPath'], {
            'taskId': step3_task['taskId'],
            'runId': run['runId'],
            'status': 'succeeded',
            'executor': {'kind': 'subagent', 'agentId': 'agent-s3'},
            'outputs': {
                'worksheetId': ws_id,
                'worksheetName': '报销单',
                'views': [{'name': '全部记录', 'id': '6c0000000000000000000021', 'type': 'table'}],
                'actions': [{'name': '提交审批', 'id': 'act-001', 'workflowId': 'wf-precreated-001',
                             'createdByBuild': True, 'disabledForWorkflowSetup': True, 'initialEnabled': False}],
                'rulesCreated': 0,
            },
            'verification': {'passed': True, 'evidence': ['已创建动作和视图']},
        })
        self.assertTrue(runtime.cmd_finalize(str(self.app), None)['canAdvance'])
        adv = runtime.cmd_advance(str(self.app))
        self.assertTrue(adv['advanced'])
        saved_ctx = json.loads((self.app / 'hap-context.json').read_text())
        self.assertEqual('wf-precreated-001', saved_ctx['actionProcessIdByKey']['报销单::提交审批'])
        stage4 = runtime.cmd_prepare(str(self.app), 'config_completed')
        step11_task = next(t for t in stage4['readyTasks'] if t['step'] == '11')
        step11_ctx = json.loads(Path(step11_task['taskContext']).read_text())
        self.assertEqual('wf-precreated-001', step11_ctx['contextSlice']['processId'])
        self.assertIn('get_custom_action_list', step11_ctx['allowedTools'])
        self.assertIn('update_custom_action', step11_ctx['allowedTools'])
        self.assertFalse(step11_ctx['planSlice']['actionWorkflow']['enabled'])
        self.assertEqual('act-001', step11_ctx['contextSlice']['actionId'])
        self.assertTrue(step11_ctx['contextSlice']['actionProvenance']['disabledForWorkflowSetup'])
        bundle = '\n'.join(Path(p).read_text() for p in step11_task['bundleFiles'])
        self.assertIn('成员为空或未知、未业务试跑只记录影响，不当作草稿理由', bundle)
        self.assertIn('独立停用', bundle)

    def test_action_workflow_keeps_explicit_status_and_does_not_invent_provenance(self):
        plan = {'customActions': [{'worksheet': '单据', 'actions': [
            {'name': '处理', 'type': 'triggerWorkflow', 'status': 0}]}]}
        action = runtime.extract_action_workflows(plan, {})[0]
        self.assertEqual(0, action['status'])
        self.assertNotIn('enabled', action)
        self.assertNotIn('createdByBuild', action)


if __name__ == '__main__':
    unittest.main()
