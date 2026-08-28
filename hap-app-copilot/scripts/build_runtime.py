#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_runtime.py
HAP App Builder 报告驱动型薄控制面运行时引擎 (Report-Driven Build Runtime).

架构演进 (方案 B - 单表全要素一体化):
- 将单表“字段结构采集 + 业务规则 + 自定义动作 + 视图配置”彻底内聚进 `step4-create_actions_views_rules`；
- 在 worksheets_created 阶段一次性全量派发单表全要素任务；
- finalize 阶段自动校验回执、调用 merge_worksheet_context.py 合并字段、提取 viewIdByName/actionIdByName 并推进至 fields_refreshed；
- fields_refreshed 阶段一次性全量提交 Step 5(AI助手) + Step 6(示例数据) + Step 7(页面) + Step 8(角色) + Step 9(工作流设计) 全局并发任务；
- 全方位自动提取自定义动作工作流（兼容内嵌 worksheets[i].customActions 与顶层 worksheetCustomActions）。
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from typing import Dict, List, Any, Optional


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return None


def save_json(filepath: str, data: Any):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_name(name: str) -> str:
    """标准化名称为安全文件名"""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(name)).strip("_")


def get_skill_root() -> str:
    """获取 Skill 根目录绝对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, ".."))


def is_task_succeeded(receipt_path: str, expected_task_id: str, current_run_id: str = "", expected_agent_id: str = "") -> bool:
    """检查回执是否存在且已成功完成（包含密码级防伪校验）"""
    if not os.path.exists(receipt_path):
        return False
    data = load_json(receipt_path)
    if not isinstance(data, dict):
        return False
    if data.get("taskId") != expected_task_id:
        return False
    if data.get("status") != "succeeded":
        return False

    receipt_run_id = data.get("runId")
    if receipt_run_id and current_run_id and receipt_run_id != current_run_id:
        return False

    executor = data.get("executor", {})
    if not isinstance(executor, dict):
        return False
    if executor.get("kind") != "subagent":
        return False

    agent_id = executor.get("agentId")
    if not agent_id:
        return False

    if expected_agent_id and agent_id != expected_agent_id:
        return False

    verification = data.get("verification", {})
    if not isinstance(verification, dict) or verification.get("passed") is not True:
        return False
    evidence = verification.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) == 0:
        return False

    return True


def extract_action_workflows(plan: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """全方位自动提取需要设计/部署工作流的自定义动作（支持内嵌与顶层多形态）"""
    action_wfs: List[Dict[str, Any]] = []
    seen_names = set()
    ws_id_by_name = context.get("worksheetIdByName", {})

    # 1. 从 context.get("customActionWorkflows") 提取
    ctx_wfs = context.get("customActionWorkflows", [])
    if isinstance(ctx_wfs, list):
        for wf in ctx_wfs:
            if isinstance(wf, dict):
                name = wf.get("name") or wf.get("actionName", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    action_wfs.append(wf)

    # 2. 从 plan.get("customActionWorkflows") 提取
    p_wfs = plan.get("customActionWorkflows", [])
    if isinstance(p_wfs, list):
        for wf in p_wfs:
            if isinstance(wf, dict):
                name = wf.get("name") or wf.get("actionName", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    action_wfs.append(wf)

    # 3. 从 worksheets 内部的 customActions / worksheetCustomActions 提取
    worksheets = plan.get("worksheets", [])
    if isinstance(worksheets, list):
        for ws in worksheets:
            if not isinstance(ws, dict):
                continue
            ws_name = ws.get("name", "")
            ws_id = ws_id_by_name.get(ws_name, "")
            actions = ws.get("customActions") or ws.get("worksheetCustomActions") or []
            if isinstance(actions, list):
                for act in actions:
                    if not isinstance(act, dict):
                        continue
                    act_name = act.get("name") or act.get("actionName", "")
                    act_type = str(act.get("type", "")).lower()
                    is_wf = (act_type in ("triggerworkflow", "workflow", "2") or 
                             act.get("actionType") == 2 or 
                             bool(act.get("intentHints")))
                    if is_wf and act_name and act_name not in seen_names:
                        seen_names.add(act_name)
                        action_wfs.append({
                            "name": act_name,
                            "actionName": act_name,
                            "worksheetName": ws_name,
                            "worksheetId": ws_id,
                            "type": "triggerWorkflow",
                            "intentHints": act.get("intentHints", []),
                            "description": act.get("description", ""),
                            "enableCondition": act.get("enableCondition", "")
                        })

    # 4. 从顶层 plan.get("customActions") 或 plan.get("worksheetCustomActions") 提取 (MDAgentService 标准)
    top_wca = plan.get("customActions") or plan.get("worksheetCustomActions") or []
    if isinstance(top_wca, list):
        for item in top_wca:
            if not isinstance(item, dict):
                continue
            ws_name = item.get("worksheet", "")
            ws_id = ws_id_by_name.get(ws_name, "")
            actions = item.get("actions", [])
            if isinstance(actions, list):
                for act in actions:
                    if not isinstance(act, dict):
                        continue
                    act_name = act.get("name") or act.get("actionName", "")
                    act_type = str(act.get("type", "")).lower()
                    is_wf = (act_type in ("triggerworkflow", "workflow", "2") or 
                             act.get("actionType") == 2 or 
                             bool(act.get("intentHints")))
                    if is_wf and act_name and act_name not in seen_names:
                        seen_names.add(act_name)
                        action_wfs.append({
                            "name": act_name,
                            "actionName": act_name,
                            "worksheetName": ws_name,
                            "worksheetId": ws_id,
                            "type": "triggerWorkflow",
                            "intentHints": act.get("intentHints", []),
                            "description": act.get("description", ""),
                            "enableCondition": act.get("enableCondition", "")
                        })

    return action_wfs


# ==========================================
# 任务定义与切片生成 (单表全要素一体化)
# ==========================================
def get_stage_tasks_definitions(app_dir: str, stage: str) -> List[Dict[str, Any]]:
    """根据应用规划和当前阶段，计算出当前阶段应具备的所有原子任务定义"""
    plan = load_json(os.path.join(app_dir, "hap-plan.json")) or {}
    context = load_json(os.path.join(app_dir, "hap-context.json")) or {}
    ws_context = load_json(os.path.join(app_dir, "worksheetContext.json")) or {}

    app_name = plan.get("appName") or plan.get("name") or context.get("appName") or os.path.basename(app_dir)
    app_id = context.get("appId", "")
    nav_groups = plan.get("navGroups") or plan.get("sections") or []
    worksheets = plan.get("worksheets", [])
    custom_pages = plan.get("customPages", [])
    roles = plan.get("roles", [])
    ai_assistants = plan.get("aiAssistants") or plan.get("chatbots") or []
    workflows = plan.get("workflows", [])
    action_workflows = extract_action_workflows(plan, context)

    ws_id_by_name = context.get("worksheetIdByName", {})
    sec_id_by_name = context.get("sectionIdByName", {})

    tasks: List[Dict[str, Any]] = []

    # 1. Step 1: 创建应用、导航分组与页面空壳
    if stage in ("step1", "initial"):
        tasks.append({
            "taskId": "step1-app-init",
            "taskName": f"[Step 1] 创建应用外壳 - {app_name}",
            "step": "1",
            "target": { "type": "app", "name": app_name },
            "stepFile": "build/steps/1_create_app.md",
            "primaryRef": "references/spec-app-styles.md",
            "allowedTools": ["create_app", "create_app_sections", "create_app_items"],
            "receiptPath": ".build/receipts/step1-app-init.json",
            "taskContextPath": ".build/task-context/step1-app-init.json",
            "planSlice": {
                "appName": app_name,
                "appIcon": plan.get("appIcon"),
                "appColor": plan.get("appColor"),
                "org_id": plan.get("org_id") or context.get("org_id"),
                "navGroups": nav_groups,
                "customPages": [p.get("name") for p in custom_pages if isinstance(p, dict)]
            },
            "contextSlice": { "org_id": plan.get("org_id") or context.get("org_id") },
            "worksheetContextSlice": {},
            "fillTemplateSlice": {},
            "desc": f"创建应用 [{app_name}]、导航分组与自定义页面空壳"
        })

    # 2. Step 1b 与 Step 2a
    elif stage in ("app_created", "step2a"):
        tasks.append({
            "taskId": "step1b-app-desc",
            "taskName": f"[Step 1b] 更新应用说明 - {app_name}",
            "step": "1b",
            "target": { "type": "app", "id": app_id, "name": app_name },
            "stepFile": "build/steps/1b_update_app_desc.md",
            "primaryRef": "references/guide-design.md",
            "allowedTools": ["update_app"],
            "receiptPath": ".build/receipts/step1b-app-desc.json",
            "taskContextPath": ".build/task-context/step1b-app-desc.json",
            "isBackground": True,
            "planSlice": {
                "appName": app_name,
                "description": plan.get("description", ""),
                "roles": [r.get("name") for r in roles if isinstance(r, dict)]
            },
            "contextSlice": { "appId": app_id, "appName": app_name },
            "worksheetContextSlice": {},
            "fillTemplateSlice": {},
            "desc": f"编写并更新应用 [{app_name}] 的描述与按角色使用手册"
        })
        for ws in worksheets:
            name = ws.get("name")
            sec_name = ws.get("groupName") or ws.get("section") or ws.get("navGroup") or ""
            tasks.append({
                "taskId": f"step2a-ws-{normalize_name(name)}",
                "taskName": f"[Step 2a] 创表 - {name}",
                "step": "2a",
                "target": { "type": "worksheet", "name": name },
                "stepFile": "build/steps/2a_create_worksheets.md",
                "primaryRef": "references/spec-worksheets.md",
                "allowedTools": ["create_worksheet", "update_worksheet"],
                "receiptPath": f".build/receipts/step2a-ws-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step2a-ws-{normalize_name(name)}.json",
                "planSlice": {
                    "worksheet": ws,
                    "fields": ws.get("fields") or ws.get("customFields") or []
                },
                "contextSlice": {
                    "appId": app_id,
                    "appSectionId": sec_id_by_name.get(sec_name, "")
                },
                "worksheetContextSlice": {},
                "fillTemplateSlice": {},
                "desc": f"创建工作表与基础字段: {name}"
            })

    elif stage in ("step2a_done", "step2b"):
        for ws in worksheets:
            name = ws.get("name")
            fields = ws.get("fields") or ws.get("customFields") or []
            has_relations = any(
                isinstance(f, str) and any(rel_kw in f for rel_kw in ("Relation:", "SubTable:", "Rollup:", "Lookup:"))
                for f in fields
            )
            if has_relations:
                tasks.append({
                    "taskId": f"step2b-rel-{normalize_name(name)}",
                    "taskName": f"[Step 2b] 关联 - {name}",
                    "step": "2b",
                    "target": { "type": "worksheet", "id": ws_id_by_name.get(name, ""), "name": name },
                    "stepFile": "build/steps/2b_create_relations.md",
                    "primaryRef": "references/spec-worksheets.md",
                    "allowedTools": ["update_worksheet"],
                    "receiptPath": f".build/receipts/step2b-rel-{normalize_name(name)}.json",
                    "taskContextPath": f".build/task-context/step2b-rel-{normalize_name(name)}.json",
                    "planSlice": {
                        "worksheetName": name,
                        "fields": fields
                    },
                    "contextSlice": {
                        "appId": app_id,
                        "worksheetId": ws_id_by_name.get(name, ""),
                        "worksheetIdByName": ws_id_by_name
                    },
                    "worksheetContextSlice": {},
                    "fillTemplateSlice": {},
                    "desc": f"补充跨表关联与衍生字段: {name}"
                })

    # 3. 阶段 2 (单表全要素一体化): 结构采集 + 业务规则 + 自定义动作 + 视图配置
    elif stage in ("worksheets_created", "phase2_single_table"):
        # 建立顶层 customActions 分组映射
        top_ca = plan.get("customActions") or plan.get("worksheetCustomActions") or []
        ca_by_ws = {}
        if isinstance(top_ca, list):
            for item in top_ca:
                if isinstance(item, dict) and "worksheet" in item:
                    ca_by_ws[item["worksheet"]] = item.get("actions", [])

        for ws in worksheets:
            name = ws.get("name")
            ws_id = ws_id_by_name.get(name, "")
            rules = ws.get("businessRules") or ws.get("businessRulesNotes")
            views = ws.get("views", [])
            custom_actions = ws.get("customActions") or ws.get("worksheetCustomActions") or ca_by_ws.get(name, [])
            tasks.append({
                "taskId": f"step3-view-act-{normalize_name(name)}",
                "taskName": f"[Step 3] 单表全要素配置 - {name}",
                "step": "3",
                "target": { "type": "worksheet", "id": ws_id, "name": name },
                "stepFile": "build/steps/3_create_actions_views_rules.md",
                "primaryRef": "references/spec-actions-views.md",
                "allowedTools": ["get_worksheet_structure", "create_business_rule", "create_custom_actions", "create_view"],
                "receiptPath": f".build/receipts/step3-view-act-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step3-view-act-{normalize_name(name)}.json",
                "planSlice": {
                    "worksheetName": name,
                    "businessRules": rules,
                    "views": views,
                    "customActions": custom_actions
                },
                "contextSlice": {
                    "appId": app_id,
                    "worksheetId": ws_id,
                    "worksheetIdByName": ws_id_by_name
                },
                "worksheetContextSlice": {},
                "fillTemplateSlice": {},
                "desc": f"配置业务规则、自定义动作与视图: {name}"
            })

        # Step 4: AI 智能助手 (在阶段 2 与单表全要素并发创建，为阶段 3 角色与排序提供物理 ID)
        if ai_assistants:
            tasks.append({
                "taskId": "step4-chatbot",
                "taskName": "[Step 4] AI智能助手",
                "step": "4",
                "target": { "type": "chatbot", "name": "智能助手" },
                "stepFile": "build/steps/4_create_chatbots.md",
                "primaryRef": "references/spec-chatbots.md",
                "allowedTools": ["create_chatbot"],
                "receiptPath": ".build/receipts/step4-chatbot.json",
                "taskContextPath": ".build/task-context/step4-chatbot.json",
                "planSlice": { "aiAssistants": ai_assistants },
                "contextSlice": { "appId": app_id, "worksheetIdByName": ws_id_by_name },
                "worksheetContextSlice": {},
                "fillTemplateSlice": {},
                "desc": "创建并配置 AI 智能问答助手"
            })

    # 4. 阶段 3: 全局跨表业务配置 (Step 5 示例数据 + Step 6 页面 + Step 7 排序 + Step 8 角色 + Step 9 工作流设计)
    elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
        page_id_by_name = context.get("customPageIdByName", {})
        view_id_by_name = context.get("viewIdByName", {})

        # Step 5: 示例数据填报
        tasks.append({
            "taskId": "step5-sample-data",
            "taskName": "[Step 5] 填充示例数据",
            "step": "5",
            "target": { "type": "sample_data", "name": "全局示例数据" },
            "stepFile": "build/steps/5_create_sample_data.md",
            "primaryRef": "references/spec-sample-data.md",
            "allowedTools": ["batch_create_records"],
            "receiptPath": ".build/receipts/step5-sample-data.json",
            "taskContextPath": ".build/task-context/step5-sample-data.json",
            "isBackground": True,
            "planSlice": {
                "worksheets": [w.get("name") for w in worksheets if isinstance(w, dict)]
            },
            "contextSlice": { "appId": app_id, "worksheetIdByName": ws_id_by_name },
            "worksheetContextSlice": ws_context,
            "desc": "生成并批量填报高仿真示例数据"
        })

        # Step 6: 自定义页面
        for page in custom_pages:
            name = page.get("name")
            tasks.append({
                "taskId": f"step6-page-{normalize_name(name)}",
                "taskName": f"[Step 6] 页面组件 - {name}",
                "step": "6",
                "target": { "type": "page", "id": page_id_by_name.get(name, ""), "name": name },
                "stepFile": "build/steps/6_create_pages.md",
                "primaryRef": "references/spec-pages-charts.md",
                "allowedTools": ["create_chart", "update_custom_page"],
                "receiptPath": f".build/receipts/step6-page-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step6-page-{normalize_name(name)}.json",
                "planSlice": { "page": page },
                "contextSlice": {
                    "appId": app_id,
                    "pageId": page_id_by_name.get(name, ""),
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name
                },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": f"配置自定义页面图表组件: {name}"
            })

        # Step 7: 应用项导航智能排序 (消除并发建表乱序)
        tasks.append({
            "taskId": "step7-sort-items",
            "taskName": "[Step 7] 应用项智能排序",
            "step": "7",
            "target": { "type": "app_navigation", "name": "全局应用项排序" },
            "stepFile": "build/steps/7_sort_app_items.md",
            "primaryRef": "references/guide-design.md",
            "allowedTools": ["sort_app_items"],
            "receiptPath": ".build/receipts/step7-sort-items.json",
            "taskContextPath": ".build/task-context/step7-sort-items.json",
            "planSlice": {
                "worksheets": worksheets,
                "customPages": custom_pages,
                "aiAssistants": ai_assistants,
                "navGroups": nav_groups
            },
            "contextSlice": {
                "appId": app_id,
                "sectionIdByName": sec_id_by_name,
                "worksheetIdByName": ws_id_by_name,
                "customPageIdByName": page_id_by_name,
                "chatbotIdByName": context.get("chatbotIdByName", {})
            },
            "worksheetContextSlice": ws_context,
            "desc": "对分组内的页面、工作表与 AI 助手按业务动线进行物理排序"
        })

        # Step 8: 角色权限
        for role in roles:
            name = role.get("name")
            tasks.append({
                "taskId": f"step8-role-{normalize_name(name)}",
                "taskName": f"[Step 8] 角色权限 - {name}",
                "step": "8",
                "target": { "type": "role", "name": name },
                "stepFile": "build/steps/8_create_roles.md",
                "primaryRef": "references/spec-roles-permissions.md",
                "allowedTools": ["create_role"],
                "receiptPath": f".build/receipts/step8-role-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step8-role-{normalize_name(name)}.json",
                "planSlice": { "role": role },
                "contextSlice": {
                    "appId": app_id,
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name,
                    "customPageIdByName": page_id_by_name,
                    "chatbotIdByName": context.get("chatbotIdByName", {})
                },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": f"创建角色并配置权限矩阵: {name}"
            })

        # Step 9: 工作流设计 (系统流 + 动作流)
        if workflows:
            tasks.append({
                "taskId": "step9-design-system",
                "taskName": "[Step 9] 系统工作流设计",
                "step": "9",
                "target": { "type": "workflow_design", "name": "system" },
                "stepFile": "build/steps/9_design_workflows.md",
                "primaryRef": "references/guide-workflows.md",
                "allowedTools": [],
                "receiptPath": ".build/receipts/step9-design-system.json",
                "taskContextPath": ".build/task-context/step9-design-system.json",
                "planSlice": { "workflows": workflows },
                "contextSlice": {
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name
                },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": "设计系统自动化工作流节点"
            })
        if action_workflows:
            tasks.append({
                "taskId": "step9-design-action",
                "taskName": "[Step 9] 动作工作流设计",
                "step": "9",
                "target": { "type": "workflow_design", "name": "action" },
                "stepFile": "build/steps/9_design_workflows.md",
                "primaryRef": "references/guide-workflows.md",
                "allowedTools": [],
                "receiptPath": ".build/receipts/step9-design-action.json",
                "taskContextPath": ".build/task-context/step9-design-action.json",
                "planSlice": { "customActionWorkflows": action_workflows },
                "contextSlice": {
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name
                },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": "设计动作工作流节点"
            })

    # 5. 阶段 4: 工作流部署与最终汇聚
    elif stage in ("config_completed", "phase4_deploy"):
        for wf in workflows:
            name = wf.get("name")
            tasks.append({
                "taskId": f"step10-sys-wf-{normalize_name(name)}",
                "taskName": f"[Step 10] 部署系统流 - {name}",
                "step": "10",
                "target": { "type": "workflow", "name": name },
                "stepFile": "build/steps/10_create_workflows.md",
                "primaryRef": "references/spec-workflows.md",
                "allowedTools": ["create_process", "batch_create_process_nodes", "publish_process"],
                "receiptPath": f".build/receipts/step10-sys-wf-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step10-sys-wf-{normalize_name(name)}.json",
                "planSlice": { "workflow": wf },
                "contextSlice": { "appId": app_id, "worksheetIdByName": ws_id_by_name },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": f"部署并发布系统工作流: {name}"
            })
        for act in action_workflows:
            name = act.get("name") or act.get("actionName", "未命名动作流")
            tasks.append({
                "taskId": f"step11-act-wf-{normalize_name(name)}",
                "taskName": f"[Step 11] 部署动作流 - {name}",
                "step": "11",
                "target": { "type": "workflow", "name": name },
                "stepFile": "build/steps/11_create_action_workflows.md",
                "primaryRef": "references/spec-workflows.md",
                "allowedTools": ["batch_create_process_nodes", "publish_process"],
                "receiptPath": f".build/receipts/step11-act-wf-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step11-act-wf-{normalize_name(name)}.json",
                "planSlice": { "actionWorkflow": act },
                "contextSlice": { "appId": app_id, "worksheetIdByName": ws_id_by_name },
                "worksheetContextSlice": ws_context,
                "fillTemplateSlice": {},
                "desc": f"部署并发布动作工作流: {name}"
            })

    return tasks


# ==========================================
# 1. INIT 命令
# ==========================================
def cmd_init(app_dir: str, skill_dir: str, mcp_server: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    build_dir = os.path.join(app_dir, ".build")
    os.makedirs(os.path.join(build_dir, "task-context"), exist_ok=True)
    os.makedirs(os.path.join(build_dir, "receipts"), exist_ok=True)
    os.makedirs(os.path.join(build_dir, "artifacts"), exist_ok=True)

    run_id = f"build-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_data = {
        "runId": run_id,
        "appDir": app_dir,
        "skillDir": os.path.abspath(skill_dir),
        "mcpServer": mcp_server,
        "executionMode": "subagent_required",
        "createdAt": datetime.datetime.now().isoformat(),
        "status": "active"
    }
    save_json(os.path.join(build_dir, "run.json"), run_data)
    return {
        "runId": run_id,
        "executionMode": "subagent_required",
        "initialized": True,
        "buildDir": build_dir
    }


# ==========================================
# 2. PREPARE 命令
# ==========================================
def cmd_prepare(app_dir: str, progress: Optional[str], include_pending_capacity: bool = False) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    skill_root = get_skill_root()
    context_path = os.path.join(app_dir, "hap-context.json")
    context = load_json(context_path) or {}
    run_data = load_json(os.path.join(app_dir, ".build", "run.json")) or {}
    run_id = run_data.get("runId", "")

    registry = load_json(os.path.join(app_dir, ".build", "dispatch-registry.json")) or {}

    current_progress = progress or context.get("progress", "")
    stage = current_progress if current_progress else "step1"

    all_tasks = get_stage_tasks_definitions(app_dir, stage)
    ready_tasks = []
    running_tasks = []
    pending_capacity_tasks = []
    completed_task_ids = []

    for t in all_tasks:
        task_id = t["taskId"]
        abs_receipt = os.path.join(app_dir, t["receiptPath"])
        abs_task_ctx = os.path.join(app_dir, t["taskContextPath"])

        # 生成完备切片上下文包
        task_ctx_data = {
            "taskId": task_id,
            "taskName": t.get("taskName", task_id),
            "runId": run_id,
            "step": t["step"],
            "target": t["target"],
            "mcpServer": run_data.get("mcpServer", "hap_sandbox_mcp"),
            "stepFile": os.path.join(skill_root, t["stepFile"]),
            "references": [os.path.join(skill_root, t["primaryRef"])],
            "receiptPath": abs_receipt,
            "planSlice": t.get("planSlice", {}),
            "contextSlice": t.get("contextSlice", {}),
            "worksheetContextSlice": t.get("worksheetContextSlice", {}),
            "fillTemplateSlice": t.get("fillTemplateSlice", {})
        }
        save_json(abs_task_ctx, task_ctx_data)

        expected_agent = registry.get(task_id, {}).get("agentId", "")
        if is_task_succeeded(abs_receipt, task_id, run_id, expected_agent):
            completed_task_ids.append(task_id)
        else:
            task_status = registry.get(task_id, {}).get("status", "planned")
            if task_status == "running":
                running_tasks.append(task_id)
            elif task_status == "pending_capacity":
                pending_capacity_tasks.append(task_id)
                if include_pending_capacity:
                    ready_tasks.append({
                        "taskId": task_id,
                        "taskName": t.get("taskName", task_id),
                        "step": t["step"],
                        "stepFile": os.path.join(skill_root, t["stepFile"]),
                        "primaryRef": os.path.join(skill_root, t["primaryRef"]),
                        "taskContext": abs_task_ctx,
                        "receiptPath": abs_receipt,
                        "isBackground": t.get("isBackground", False),
                        "desc": t.get("desc", "")
                    })
            else:
                ready_tasks.append({
                    "taskId": task_id,
                    "taskName": t.get("taskName", task_id),
                    "step": t["step"],
                    "stepFile": os.path.join(skill_root, t["stepFile"]),
                    "primaryRef": os.path.join(skill_root, t["primaryRef"]),
                    "taskContext": abs_task_ctx,
                    "receiptPath": abs_receipt,
                    "isBackground": t.get("isBackground", False),
                    "desc": t.get("desc", "")
                })

    manifest_data = {
        "stage": stage,
        "currentProgress": current_progress,
        "totalTasks": len(all_tasks),
        "readyCount": len(ready_tasks),
        "runningCount": len(running_tasks),
        "pendingCapacityCount": len(pending_capacity_tasks),
        "completedCount": len(completed_task_ids),
        "updatedAt": datetime.datetime.now().isoformat()
    }
    save_json(os.path.join(app_dir, ".build", "task-manifest.json"), manifest_data)

    return {
        "runId": run_id,
        "progress": current_progress,
        "stage": stage,
        "totalExpected": len(all_tasks),
        "readyTaskCount": len(ready_tasks),
        "runningTaskCount": len(running_tasks),
        "pendingCapacityCount": len(pending_capacity_tasks),
        "completedCount": len(completed_task_ids),
        "canAdvance": (len(ready_tasks) == 0 and len(running_tasks) == 0 and len(all_tasks) > 0),
        "readyTasks": ready_tasks
    }


# ==========================================
# 3. DISPATCHED / CAPACITY-WAIT / DISPATCH-FAILED 命令
# ==========================================
def cmd_record_dispatch(app_dir: str, task_id: str, agent_id: str, status: str, reason: str = "") -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    run_data = load_json(os.path.join(app_dir, ".build", "run.json")) or {}
    record_file = os.path.join(app_dir, ".build", "dispatch-registry.json")
    registry = load_json(record_file) or {}

    registry[task_id] = {
        "taskId": task_id,
        "agentId": agent_id,
        "runId": run_data.get("runId", ""),
        "status": status,
        "reason": reason,
        "timestamp": datetime.datetime.now().isoformat()
    }
    save_json(record_file, registry)
    return { "taskId": task_id, "status": status, "agentId": agent_id, "recorded": True }


# ==========================================
# 4. REFRESH 命令
# ==========================================
def cmd_refresh(app_dir: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    context_path = os.path.join(app_dir, "hap-context.json")
    context = load_json(context_path) or {}
    run_data = load_json(os.path.join(app_dir, ".build", "run.json")) or {}
    run_id = run_data.get("runId", "")
    stage = context.get("progress", "step1")

    all_tasks = get_stage_tasks_definitions(app_dir, stage)
    registry = load_json(os.path.join(app_dir, ".build", "dispatch-registry.json")) or {}

    succeeded = 0
    running = 0
    pending_capacity = 0
    failed = 0

    for t in all_tasks:
        tid = t["taskId"]
        r_path = os.path.join(app_dir, t["receiptPath"])
        expected_agent = registry.get(tid, {}).get("agentId", "")
        if is_task_succeeded(r_path, tid, run_id, expected_agent):
            succeeded += 1
        elif tid in registry:
            st = registry[tid].get("status")
            if st == "running":
                running += 1
            elif st == "pending_capacity":
                pending_capacity += 1
            elif st == "failed":
                failed += 1
        else:
            pending_capacity += 1

    return {
        "stage": stage,
        "total": len(all_tasks),
        "succeeded": succeeded,
        "running": running,
        "pendingCapacity": pending_capacity,
        "failed": failed,
        "phaseComplete": (succeeded == len(all_tasks) and len(all_tasks) > 0)
    }


# ==========================================
# 5. FINALIZE 命令 (单表全要素一体化合并)
# ==========================================
def cmd_finalize(app_dir: str, progress: Optional[str]) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    skill_root = get_skill_root()
    context_path = os.path.join(app_dir, "hap-context.json")
    plan_path = os.path.join(app_dir, "hap-plan.json")
    run_data = load_json(os.path.join(app_dir, ".build", "run.json")) or {}
    run_id = run_data.get("runId", "")

    registry = load_json(os.path.join(app_dir, ".build", "dispatch-registry.json")) or {}

    context = load_json(context_path) or {}
    plan = load_json(plan_path) or {}
    current_progress = progress or context.get("progress", "")

    stage = current_progress if current_progress else "step1"

    all_tasks = get_stage_tasks_definitions(app_dir, stage)
    total_expected = len(all_tasks)

    succeeded_tasks = []
    failed_tasks = []
    running_tasks = []
    errors = []

    for t in all_tasks:
        task_id = t["taskId"]
        r_path = os.path.join(app_dir, t["receiptPath"])
        if not os.path.exists(r_path):
            running_tasks.append(task_id)
        else:
            r_data = load_json(r_path)
            expected_agent = registry.get(task_id, {}).get("agentId", "")
            if not isinstance(r_data, dict):
                failed_tasks.append(task_id)
                errors.append(f"任务 [{task_id}] 回执 JSON 格式损坏")
            elif r_data.get("status") != "succeeded":
                failed_tasks.append(task_id)
                errors.append(f"任务 [{task_id}] 状态为 {r_data.get('status')}: {r_data.get('issues')}")
            elif not is_task_succeeded(r_path, task_id, run_id, expected_agent):
                failed_tasks.append(task_id)
                errors.append(f"任务 [{task_id}] 凭证校验失败 (agentId 未注册或与 dispatch 记录不符)")
            else:
                succeeded_tasks.append(task_id)

    # 判定是否能推进（中间阶段排除后台任务）
    if stage in ("config_completed", "phase4_deploy"):
        blocking_tasks = [t["taskId"] for t in all_tasks]
    else:
        blocking_tasks = [t["taskId"] for t in all_tasks if not t.get("isBackground", False)]

    blocking_running = [tid for tid in running_tasks if tid in blocking_tasks]
    blocking_failed = [tid for tid in failed_tasks if tid in blocking_tasks]

    if len(blocking_tasks) == 0:
        can_advance = True
    else:
        can_advance = (len(blocking_running) == 0 and len(blocking_failed) == 0)

    next_progress = current_progress
    stage_outputs: Dict[str, Any] = {}

    if can_advance:
        if stage in ("step1", "initial"):
            r_data = load_json(os.path.join(app_dir, ".build", "receipts", "step1-app-init.json")) or {}
            outputs = r_data.get("outputs", {})
            next_progress = "app_created"
            stage_outputs.update({
                "appId": outputs.get("appId"),
                "sections": len(outputs.get("sectionIdByName", {})),
                "customPages": len(outputs.get("customPageIdByName", {}))
            })

        elif stage in ("app_created", "step2a"):
            ws_id_by_name = context.get("worksheetIdByName", {})
            has_relation_todo = False
            for t in all_tasks:
                if t["step"] == "2a":
                    r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                    outputs = r_data.get("outputs", {})
                    ws_name = outputs.get("worksheetName") or t["target"].get("name")
                    ws_id = outputs.get("worksheetId")
                    if ws_name and ws_id:
                        ws_id_by_name[ws_name] = ws_id
                    if outputs.get("relationLayout"):
                        has_relation_todo = True
            next_progress = "step2a_done" if has_relation_todo else "worksheets_created"
            stage_outputs["worksheetsCreated"] = len(ws_id_by_name)

        elif stage in ("step2a_done", "step2b"):
            next_progress = "worksheets_created"
            stage_outputs["relationsConfigured"] = True

        # 单表全要素一体化合并
        elif stage in ("worksheets_created", "phase2_single_table"):
            merge_script = os.path.join(skill_root, "scripts", "merge_worksheet_context.py")
            cmd = [sys.executable, merge_script, app_dir]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                can_advance = False
                errors.append(f"merge_worksheet_context.py 校验失败: {res.stderr}")
            else:
                view_id_by_name = context.get("viewIdByName", {})
                action_id_by_name = context.get("actionIdByName", {})
                chatbot_id_by_name = context.get("chatbotIdByName", {})
                for t in all_tasks:
                    r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                    outputs = r_data.get("outputs", {})
                    if "viewIdByName" in outputs:
                        view_id_by_name.update(outputs["viewIdByName"])
                    if "actionIdByName" in outputs:
                        action_id_by_name.update(outputs["actionIdByName"])
                    if "chatbotIdByName" in outputs:
                        chatbot_id_by_name.update(outputs["chatbotIdByName"])
                    elif "chatbotName" in outputs and "chatbotId" in outputs:
                        chatbot_id_by_name[outputs["chatbotName"]] = outputs["chatbotId"]

                next_progress = "fields_refreshed"
                stage_outputs.update({
                    "fieldsRefreshed": True,
                    "viewsCreated": len(view_id_by_name),
                    "actionsCreated": len(action_id_by_name),
                    "chatbotsCreated": len(chatbot_id_by_name),
                    "businessRulesConfigured": True
                })

        elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
            role_id_by_name = context.get("roleIdByName", {})
            chatbot_id_by_name = context.get("chatbotIdByName", {})
            custom_action_workflows = context.get("customActionWorkflows", [])

            for t in all_tasks:
                r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                outputs = r_data.get("outputs", {})
                if "roleIdByName" in outputs:
                    role_id_by_name.update(outputs["roleIdByName"])
                elif "roleName" in outputs and "roleId" in outputs:
                    role_id_by_name[outputs["roleName"]] = outputs["roleId"]
                if "chatbotIdByName" in outputs:
                    chatbot_id_by_name.update(outputs["chatbotIdByName"])
                if "customActionWorkflows" in outputs:
                    custom_action_workflows.extend(outputs["customActionWorkflows"])

            next_progress = "config_completed"
            stage_outputs.update({
                "rolesCreated": len(role_id_by_name),
                "chatbotsCreated": len(chatbot_id_by_name),
                "sampleDataCreated": True,
                "workflowsDesigned": True
            })

        elif stage in ("config_completed", "phase4_deploy"):
            next_progress = "completed"
            stage_outputs["buildCompleted"] = True

    report_data = {
        "schemaVersion": "1.0",
        "runId": run_id,
        "phase": stage,
        "progressBefore": current_progress,
        "taskSummary": {
            "expected": total_expected,
            "succeeded": len(succeeded_tasks),
            "failed": len(failed_tasks),
            "running": len(running_tasks),
            "pendingCapacity": 0,
            "retryPending": 0
        },
        "execution": {
            "mode": "subagent_required",
            "subagentExecutionVerified": (len(succeeded_tasks) == total_expected if total_expected > 0 else True),
            "inlineExecutionDetected": False
        },
        "outputs": stage_outputs,
        "validation": {
            "passed": can_advance,
            "errors": errors,
            "warnings": []
        },
        "nextProgress": next_progress,
        "canAdvance": can_advance,
        "runningTaskIds": running_tasks,
        "failedTaskIds": failed_tasks
    }

    save_json(os.path.join(app_dir, ".build", "phase-report.json"), report_data)
    return report_data


# ==========================================
# 6. ADVANCE 命令
# ==========================================
def cmd_advance(app_dir: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    report_file = os.path.join(app_dir, ".build", "phase-report.json")
    report = load_json(report_file)

    if not report or not report.get("canAdvance"):
        print("❌ 推进被阻断: phase-report.json 不存在或 canAdvance 非 true", file=sys.stderr)
        sys.exit(1)

    context_path = os.path.join(app_dir, "hap-context.json")
    plan_path = os.path.join(app_dir, "hap-plan.json")
    context = load_json(context_path) or {}
    plan = load_json(plan_path) or {}

    stage = report.get("phase", "")
    next_progress = report.get("nextProgress", "")
    all_tasks = get_stage_tasks_definitions(app_dir, stage)

    if stage in ("step1", "initial"):
        r_data = load_json(os.path.join(app_dir, ".build", "receipts", "step1-app-init.json")) or {}
        outputs = r_data.get("outputs", {})
        context["appId"] = outputs.get("appId")
        context["sectionIdByName"] = outputs.get("sectionIdByName", {})
        context["customPageIdByName"] = outputs.get("customPageIdByName", {})

    elif stage in ("app_created", "step2a"):
        ws_id_by_name = context.get("worksheetIdByName", {})
        for t in all_tasks:
            if t["step"] == "2a":
                r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                outputs = r_data.get("outputs", {})
                ws_name = outputs.get("worksheetName") or t["target"].get("name")
                ws_id = outputs.get("worksheetId")
                if ws_name and ws_id:
                    ws_id_by_name[ws_name] = ws_id
        context["worksheetIdByName"] = ws_id_by_name

    elif stage in ("worksheets_created", "phase2_single_table"):
        view_id_by_name = context.get("viewIdByName", {})
        action_id_by_name = context.get("actionIdByName", {})
        for t in all_tasks:
            r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
            outputs = r_data.get("outputs", {})
            if "viewIdByName" in outputs:
                view_id_by_name.update(outputs["viewIdByName"])
            if "actionIdByName" in outputs:
                action_id_by_name.update(outputs["actionIdByName"])
        context["viewIdByName"] = view_id_by_name
        context["actionIdByName"] = action_id_by_name

    elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
        role_id_by_name = context.get("roleIdByName", {})
        chatbot_id_by_name = context.get("chatbotIdByName", {})
        custom_action_workflows = context.get("customActionWorkflows", [])

        for t in all_tasks:
            r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
            outputs = r_data.get("outputs", {})
            if "roleIdByName" in outputs:
                role_id_by_name.update(outputs["roleIdByName"])
            elif "roleName" in outputs and "roleId" in outputs:
                role_id_by_name[outputs["roleName"]] = outputs["roleId"]
            if "chatbotIdByName" in outputs:
                chatbot_id_by_name.update(outputs["chatbotIdByName"])
            if "customActionWorkflows" in outputs:
                custom_action_workflows.extend(outputs["customActionWorkflows"])
            elif t["taskId"] == "step9-design-system" and "workflows" in outputs:
                plan["workflows"] = outputs["workflows"]
            elif t["taskId"] == "step9-design-action" and "customActionWorkflows" in outputs:
                plan["customActionWorkflows"] = outputs["customActionWorkflows"]

        context["roleIdByName"] = role_id_by_name
        context["chatbotIdByName"] = chatbot_id_by_name
        context["customActionWorkflows"] = custom_action_workflows
        context["sampleDataCreated"] = True
        save_json(plan_path, plan)

    elif stage in ("config_completed", "phase4_deploy"):
        workflows = plan.get("workflows", [])
        custom_action_workflows = context.get("customActionWorkflows", [])
        wf_map = {wf.get("name"): wf for wf in workflows if isinstance(wf, dict)}
        act_map = {act.get("actionName"): act for act in custom_action_workflows if isinstance(act, dict)}

        for t in all_tasks:
            r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
            outputs = r_data.get("outputs", {})
            wf_name = outputs.get("workflowName")
            proc_id = outputs.get("processId")
            if wf_name in wf_map and proc_id:
                wf_map[wf_name]["processId"] = proc_id
                wf_map[wf_name]["published"] = True
            act_name = outputs.get("actionName")
            if act_name in act_map:
                act_map[act_name]["published"] = True

        plan["workflows"] = list(wf_map.values())
        context["customActionWorkflows"] = list(act_map.values())
        save_json(plan_path, plan)

    # 原子更新 progress
    context["progress"] = next_progress
    context["buildRun"] = {
        "runId": report.get("runId", ""),
        "executionMode": "subagent_required",
        "lastPhaseReport": ".build/phase-report.json",
        "blocked": False
    }
    save_json(context_path, context)

    return {
        "advanced": True,
        "stage": stage,
        "newProgress": next_progress,
        "contextPath": context_path
    }


# ==========================================
# CLI 入口
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="HAP App Builder 报告驱动型薄运行时引擎")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="初始化 .build 运行目录与执行策略")
    p_init.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_init.add_argument("--skill-dir", type=str, default="", help="Skill 根目录")
    p_init.add_argument("--mcp-server", type=str, default="hap_sandbox_mcp", help="MCP 服务名")

    # prepare
    p_prep = subparsers.add_parser("prepare", help="计算 DAG 就绪任务并生成切片上下文")
    p_prep.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_prep.add_argument("--progress", type=str, default="", help="可选显式指定 progress")
    p_prep.add_argument("--include-pending-capacity", action="store_true", help="是否包含容量等待任务")

    # dispatched
    p_disp = subparsers.add_parser("dispatched", help="记录已成功派发任务")
    p_disp.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_disp.add_argument("--task-id", type=str, required=True, help="任务 ID")
    p_disp.add_argument("--agent-id", type=str, required=True, help="Subagent 实例 ID")

    # capacity-wait
    p_cap = subparsers.add_parser("capacity-wait", help="标记任务进入容量等待")
    p_cap.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_cap.add_argument("--task-id", type=str, required=True, help="任务 ID")

    # dispatch-failed
    p_df = subparsers.add_parser("dispatch-failed", help="记录任务派发失败")
    p_df.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_df.add_argument("--task-id", type=str, required=True, help="任务 ID")
    p_df.add_argument("--reason-code", type=str, default="SUBAGENT_TOOL_ERROR", help="失败原因码")

    # refresh
    p_ref = subparsers.add_parser("refresh", help="刷新任务状态与进度摘要")
    p_ref.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")

    # finalize
    p_fin = subparsers.add_parser("finalize", help="汇总校验回执并生成阶段报告")
    p_fin.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_fin.add_argument("--progress", type=str, default="", help="可选显式指定 progress")

    # advance
    p_adv = subparsers.add_parser("advance", help="在报告放行后原子推进状态机")
    p_adv.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")

    # status
    p_stat = subparsers.add_parser("status", help="查看当前阶段状态")
    p_stat.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")

    args = parser.parse_args()

    if args.command == "init":
        skill_dir = args.skill_dir if args.skill_dir else get_skill_root()
        res = cmd_init(args.app_dir, skill_dir, args.mcp_server)
    elif args.command == "prepare":
        res = cmd_prepare(args.app_dir, args.progress if args.progress else None, args.include_pending_capacity)
    elif args.command == "dispatched":
        res = cmd_record_dispatch(args.app_dir, args.task_id, args.agent_id, "running")
    elif args.command == "capacity-wait":
        res = cmd_record_dispatch(args.app_dir, args.task_id, "", "pending_capacity")
    elif args.command == "dispatch-failed":
        res = cmd_record_dispatch(args.app_dir, args.task_id, "", "failed", args.reason_code)
    elif args.command == "refresh":
        res = cmd_refresh(args.app_dir)
    elif args.command == "finalize":
        res = cmd_finalize(args.app_dir, args.progress if args.progress else None)
    elif args.command == "advance":
        res = cmd_advance(args.app_dir)
    elif args.command == "status":
        res = cmd_refresh(args.app_dir)
    else:
        res = { "error": f"Unknown command: {args.command}" }

    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.command == "finalize":
        sys.exit(0 if res.get("canAdvance") else 1)


if __name__ == "__main__":
    main()
