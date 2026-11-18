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
                'customActions': [{'name': '提交审批', 'type': 'triggerWorkflow', 'intentHints': ['发起审批']}],
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
                'actions': [{'name': '提交审批', 'id': 'act-001', 'workflowId': 'wf-precreated-001'}],
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


if __name__ == '__main__':
    unittest.main()
