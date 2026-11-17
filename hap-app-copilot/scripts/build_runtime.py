#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_runtime.py
HAP App Copilot 报告驱动型薄控制面运行时引擎 (Report-Driven Build Runtime).

对齐 MDAgentService build-app-agent 最新全链路架构：
- 阶段 1 (step1): 创建应用、导航分组与自定义页面空壳 -> app_created
- 阶段 1.5 (app_created -> step2a_done -> worksheets_created):
  Step 1b(后台使用手册) + Step 2a(基础表与字段并发，产出 relationLayout 与 fieldOptionsContext)
  -> Step 2b(按 relationLayout 预留行号回填跨表关联与衍生字段，只写不回读)
- 阶段 2 (worksheets_created -> fields_refreshed):
  Step 3(单表结构采集 + 自定义动作 + 视图 + 四类业务规则) + Step 4a(AI助手实体创建)
  -> 自动触发 merge_worksheet_context.py 执行 10 项强校验合并
- 阶段 3 (fields_refreshed -> config_completed):
  Step 4b(AI助手关联工作流 ai_agent 节点配置发布) + Step 5(后台示例数据) + Step 6(页面组装与 summary 校正)
  + Step 7(应用项智能排序) + Step 8(单角色精细权限并发) + Step 9a/9b(单条系统流/动作流节点蓝图并发设计)
- 阶段 4 (config_completed -> completed):
  Step 10(单条系统流创建校验发布) + Step 11(单个动作流按 worksheet::action 精确匹配 processId 注入发布)
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

SYSTEM_WORKFLOW_TOOLS = [
    "find_member",
    "find_department",
    "get_current_user",
    "get_worksheet_field",
    "get_worksheet_structure",
    "create_process",
    "get_workflow_structure",
    "get_workflow_node",
    "get_workflow_variables",
    "update_workflow_node",
    "update_workflow_variables",
    "batch_create_process_nodes",
    "batch_delete_process_nodes",
    "validate_process",
    "publish_process",
    "get_sms_signatures",
]

ACTION_WORKFLOW_TOOLS = [t for t in SYSTEM_WORKFLOW_TOOLS if t != "create_process"]


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return None


def load_text(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def save_json(filepath: str, data: Any):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(name)).strip("_")


def get_skill_root() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, ".."))


def is_task_succeeded(receipt_path: str, expected_task_id: str, current_run_id: str = "", expected_agent_id: str = "") -> bool:
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
    if not isinstance(executor, dict) or executor.get("kind") != "subagent":
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
    """提取需要设计并部署工作流的自定义动作（按 worksheet::action 复合键去重，保留跨表同名按钮）"""
    action_wfs: List[Dict[str, Any]] = []
    seen_keys = set()
    ws_id_by_name = context.get("worksheetIdByName", {})
    proc_id_by_key = context.get("actionProcessIdByKey", {})

    def add_action_item(ws_name: str, act: Dict[str, Any]):
        act_name = act.get("name") or act.get("actionName", "")
        if not act_name:
            return
        comp_key = f"{ws_name}::{act_name}"
        act_type = str(act.get("type") or act.get("clickType", "")).lower()
        is_wf = (
            act_type in ("triggerworkflow", "workflow", "2")
            or act.get("actionType") == 2
            or act.get("runWorkflowAfterSubmit") is True
            or bool(act.get("intentHints"))
            or bool(act.get("processId"))
            or bool(proc_id_by_key.get(comp_key))
        )
        if not is_wf:
            return
        if comp_key in seen_keys:
            return
        seen_keys.add(comp_key)
        action_wfs.append({
            "key": comp_key,
            "worksheet": ws_name,
            "worksheetName": ws_name,
            "worksheetId": ws_id_by_name.get(ws_name, ""),
            "name": act_name,
            "actionName": act_name,
            "type": act.get("type", "triggerWorkflow"),
            "runWorkflowAfterSubmit": bool(act.get("runWorkflowAfterSubmit", False)),
            "targetWorksheet": act.get("targetWorksheet", ""),
            "relateFieldName": act.get("relateFieldName", ""),
            "enableCondition": act.get("enableCondition", ""),
            "description": act.get("description", ""),
            "intentHints": act.get("intentHints", []),
            "requirements": act.get("requirements", []),
            "processId": act.get("processId") or proc_id_by_key.get(comp_key, ""),
        })

    # 1. 从 worksheets 内嵌 customActions 提取
    for ws in plan.get("worksheets", []) or []:
        if not isinstance(ws, dict):
            continue
        ws_name = ws.get("name", "")
        for act in (ws.get("customActions") or ws.get("worksheetCustomActions") or []):
            if isinstance(act, dict):
                add_action_item(ws_name, act)

    # 2. 从顶层 customActions 数组提取 (MDAgentService 标准格式)
    for item in (plan.get("customActions") or plan.get("worksheetCustomActions") or []):
        if not isinstance(item, dict):
            continue
        ws_name = item.get("worksheet", "")
        ws_reqs = item.get("requirements", [])
        for act in item.get("actions", []) or []:
            if isinstance(act, dict):
                merged = dict(act)
                if ws_reqs and not merged.get("requirements"):
                    merged["requirements"] = ws_reqs
                add_action_item(ws_name, merged)

    # 3. 兼容旧版平铺 customActionWorkflows
    for wf in (plan.get("customActionWorkflows") or context.get("customActionWorkflows") or []):
        if isinstance(wf, dict):
            ws_name = wf.get("worksheet") or wf.get("worksheetName", "")
            add_action_item(ws_name, wf)

    return action_wfs


def get_stage_tasks_definitions(app_dir: str, stage: str) -> List[Dict[str, Any]]:
    plan = load_json(os.path.join(app_dir, "hap-plan.json")) or {}
    context = load_json(os.path.join(app_dir, "hap-context.json")) or {}
    ws_context = load_json(os.path.join(app_dir, "worksheetContext.json")) or {}
    overview_md = load_text(os.path.join(app_dir, "overview.md"))

    app_name = plan.get("appName") or plan.get("name") or context.get("appName") or os.path.basename(app_dir)
    app_id = context.get("appId", "")
    org_id = plan.get("org_id") or plan.get("orgId") or context.get("org_id") or context.get("orgId", "")
    app_lang = plan.get("language") or context.get("language") or "zh-CN"
    app_color = plan.get("appColor", "")
    app_reqs = plan.get("requirements", [])
    nav_groups = plan.get("navGroups") or plan.get("sections") or []
    worksheets = plan.get("worksheets", [])
    custom_pages = plan.get("customPages", [])
    roles = plan.get("roles", [])
    ai_assistants = plan.get("aiAssistants") or plan.get("chatbots") or []
    workflows = plan.get("workflows", [])
    action_workflows = extract_action_workflows(plan, context)

    ws_id_by_name = context.get("worksheetIdByName", {})
    sec_id_by_name = context.get("sectionIdByName", {})
    rel_layout_by_ws = context.get("relationLayoutByWorksheet", {})
    ws_fields_preview = context.get("worksheetFieldsPreview", {})
    field_options_ctx = context.get("fieldOptionsContext", [])
    chatbot_id_by_name = context.get("chatbotIdByName", {})

    tasks: List[Dict[str, Any]] = []

    # 阶段 1: 应用外壳、分组与页面空壳
    if stage in ("step1", "initial"):
        tasks.append({
            "taskId": "step1-app-init",
            "taskName": f"[Step 1] 创建应用外壳 - {app_name}",
            "step": "1",
            "target": {"type": "app", "name": app_name},
            "stepFile": "build/steps/1_create_app.md",
            "references": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
            "allowedTools": ["create_app", "create_app_sections", "create_app_items"],
            "receiptPath": ".build/receipts/step1-app-init.json",
            "taskContextPath": ".build/task-context/step1-app-init.json",
            "planSlice": {
                "appName": app_name,
                "appIcon": plan.get("appIcon"),
                "appColor": app_color,
                "navLayout": plan.get("navLayout"),
                "navColor": plan.get("navColor"),
                "enableExternalPortal": bool(plan.get("enableExternalPortal", False)),
                "requirements": app_reqs,
                "appLanguage": app_lang,
                "org_id": org_id,
                "navGroups": nav_groups,
                "customPages": custom_pages,
            },
            "contextSlice": {"org_id": org_id},
            "worksheetContextSlice": {},
            "desc": f"创建应用 [{app_name}]、导航分组与自定义页面空壳",
        })

    # 阶段 1.5 Pass 1: Step 2a 并发建表（Step 1b 应用说明已收归主调度器在阶段 1 内联完成）
    elif stage in ("app_created", "step2a"):
        for ws in worksheets:
            if not isinstance(ws, dict):
                continue
            name = ws.get("name", "")
            sec_name = ws.get("groupName") or ws.get("section") or ws.get("navGroup") or ""
            tasks.append({
                "taskId": f"step2a-ws-{normalize_name(name)}",
                "taskName": f"[Step 2a] 创表 - {name}",
                "step": "2a",
                "target": {"type": "worksheet", "name": name},
                "stepFile": "build/steps/2a_create_worksheets.md",
                "references": ["references/hap-domain-worksheet-spec.md", "references/hap-domain-custom-field-spec.md"],
                "allowedTools": ["create_worksheet", "update_worksheet", "update_worksheet_settings"],
                "receiptPath": f".build/receipts/step2a-ws-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step2a-ws-{normalize_name(name)}.json",
                "planSlice": {
                    "worksheet": ws,
                    "fields": ws.get("fields") or ws.get("customFields") or [],
                    "appLanguage": app_lang,
                },
                "contextSlice": {
                    "appId": app_id,
                    "appSectionId": sec_id_by_name.get(sec_name, ""),
                    "sectionIdByName": sec_id_by_name,
                },
                "worksheetContextSlice": {},
                "desc": f"创建工作表与基础字段排版: {name}",
            })

    # 阶段 1.5 Pass 2: Step 2b 关联与衍生字段回填
    elif stage in ("step2a_done", "step2b"):
        for ws in worksheets:
            if not isinstance(ws, dict):
                continue
            name = ws.get("name", "")
            rel_layout = rel_layout_by_ws.get(name)
            fields = ws.get("fields") or ws.get("customFields") or []
            has_relations = bool(rel_layout) or any(
                isinstance(f, str) and any(kw in f for kw in ("Relation:", "SubTable:", "Rollup:", "Lookup:"))
                for f in fields
            )
            if has_relations:
                tasks.append({
                    "taskId": f"step2b-rel-{normalize_name(name)}",
                    "taskName": f"[Step 2b] 关联回填 - {name}",
                    "step": "2b",
                    "target": {"type": "worksheet", "id": ws_id_by_name.get(name, ""), "name": name},
                    "stepFile": "build/steps/2b_create_relations.md",
                    "references": ["references/hap-domain-worksheet-spec.md"],
                    "allowedTools": ["update_worksheet"],
                    "receiptPath": f".build/receipts/step2b-rel-{normalize_name(name)}.json",
                    "taskContextPath": f".build/task-context/step2b-rel-{normalize_name(name)}.json",
                    "planSlice": {
                        "worksheetName": name,
                        "fields": fields,
                        "relationLayout": rel_layout or [],
                        "allRelationLayouts": rel_layout_by_ws,
                        "requirements": ws.get("requirements", []),
                        "appLanguage": app_lang,
                    },
                    "contextSlice": {
                        "appId": app_id,
                        "worksheetId": ws_id_by_name.get(name, ""),
                        "worksheetIdByName": ws_id_by_name,
                        "worksheetFieldsByName": ws_fields_preview,
                    },
                    "worksheetContextSlice": {},
                    "desc": f"按预留行号补充跨表关联与衍生字段: {name}",
                })

    # 阶段 2: Step 3 单表全要素 + Step 4a AI 助手实体创建
    elif stage in ("worksheets_created", "phase2_single_table"):
        top_ca = plan.get("customActions") or plan.get("worksheetCustomActions") or []
        ca_by_ws: Dict[str, List[Dict[str, Any]]] = {}
        if isinstance(top_ca, list):
            for item in top_ca:
                if isinstance(item, dict) and "worksheet" in item:
                    ca_by_ws[item["worksheet"]] = item.get("actions", [])

        for ws in worksheets:
            if not isinstance(ws, dict):
                continue
            name = ws.get("name", "")
            ws_id = ws_id_by_name.get(name, "")
            rules = ws.get("businessRules") or ws.get("businessRulesNotes") or []
            views = ws.get("views", [])
            custom_actions = ws.get("customActions") or ws.get("worksheetCustomActions") or ca_by_ws.get(name, [])
            tasks.append({
                "taskId": f"step3-view-act-{normalize_name(name)}",
                "taskName": f"[Step 3] 单表全要素配置 - {name}",
                "step": "3",
                "target": {"type": "worksheet", "id": ws_id, "name": name},
                "stepFile": "build/steps/3_create_actions_views_rules.md",
                "references": [
                    "references/hap-domain-view-spec.md",
                    "references/hap-domain-custom-action-spec.md",
                    "references/hap-domain-business-rule-spec.md",
                ],
                "allowedTools": [
                    "get_worksheet_structure",
                    "create_custom_actions",
                    "create_view",
                    "get_view_structure",
                    "update_view",
                    "create_business_rule",
                ],
                "receiptPath": f".build/receipts/step3-view-act-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step3-view-act-{normalize_name(name)}.json",
                "planSlice": {
                    "worksheetName": name,
                    "businessRules": rules,
                    "views": views,
                    "customActions": custom_actions,
                    "requirements": ws.get("requirements", []),
                    "appLanguage": app_lang,
                },
                "contextSlice": {
                    "appId": app_id,
                    "worksheetId": ws_id,
                    "worksheetIdByName": ws_id_by_name,
                    "artifactPath": os.path.join(app_dir, ".build", "artifacts", f"worksheet-{ws_id}.json"),
                },
                "worksheetContextSlice": {},
                "desc": f"拉取完整结构并配置自定义动作、视图与业务规则: {name}",
            })

        if ai_assistants:
            tasks.append({
                "taskId": "step4-chatbot",
                "taskName": "[Step 4a] 创建 AI 智能助手实体",
                "step": "4a",
                "target": {"type": "chatbot", "name": "AI智能助手"},
                "stepFile": "build/steps/4_create_chatbots.md",
                "references": ["references/hap-domain-chatbot-spec.md"],
                "allowedTools": ["create_chatbot"],
                "receiptPath": ".build/receipts/step4-chatbot.json",
                "taskContextPath": ".build/task-context/step4-chatbot.json",
                "planSlice": {
                    "aiAssistants": ai_assistants,
                    "worksheetsSummary": [{"name": w.get("name"), "description": w.get("description", "")} for w in worksheets if isinstance(w, dict)],
                    "appLanguage": app_lang,
                },
                "contextSlice": {
                    "appId": app_id,
                    "sectionIdByName": sec_id_by_name,
                    "worksheetIdByName": ws_id_by_name,
                },
                "worksheetContextSlice": {},
                "desc": "创建应用专属 AI 智能助手实体并获取 chatbotId",
            })

    # 阶段 3: Step 4b + Step 5 + Step 6 + Step 7 + Step 8 + Step 9a/9b
    elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
        page_id_by_name = context.get("customPageIdByName", {})
        view_id_by_name = context.get("viewIdByName", {})
        views_by_ws = context.get("viewsByWorksheet", {})

        # Step 4b: 为每个已建 AI 助手配置关联工作流 ai_agent 节点
        for bot in ai_assistants:
            if not isinstance(bot, dict):
                continue
            b_name = bot.get("name", "")
            b_id = chatbot_id_by_name.get(b_name, "")
            if b_name and b_id:
                tasks.append({
                    "taskId": f"step4b-chatbot-config-{normalize_name(b_name)}",
                    "taskName": f"[Step 4b] 配置 AI 助手节点 - {b_name}",
                    "step": "4b",
                    "target": {"type": "chatbot", "id": b_id, "name": b_name},
                    "stepFile": "build/steps/4_create_chatbots.md",
                    "references": ["references/hap-domain-chatbot-spec.md"],
                    "allowedTools": [
                        "get_workflow_structure",
                        "get_workflow_node",
                        "update_workflow_node",
                        "publish_process",
                        "get_app_ai_models",
                        "get_app_knowledge_list",
                        "get_worksheet_structure",
                        "get_view_structure",
                    ],
                    "receiptPath": f".build/receipts/step4b-chatbot-config-{normalize_name(b_name)}.json",
                    "taskContextPath": f".build/task-context/step4b-chatbot-config-{normalize_name(b_name)}.json",
                    "planSlice": {"assistant": bot, "appLanguage": app_lang},
                    "contextSlice": {
                        "appId": app_id,
                        "chatbotId": b_id,
                        "worksheetIdByName": ws_id_by_name,
                        "viewIdByName": view_id_by_name,
                    },
                    "worksheetContextSlice": ws_context,
                    "desc": f"为 AI 助手 [{b_name}] 配置关联工作流节点并发布",
                })

        # Step 5: 示例数据（后台任务）
        tasks.append({
            "taskId": "step5-sample-data",
            "taskName": "[Step 5] 填充示例数据",
            "step": "5",
            "target": {"type": "sample_data", "name": "全局示例数据"},
            "stepFile": "build/steps/5_create_sample_data.md",
            "references": ["references/hap-sample-data-spec.md"],
            "allowedTools": ["batch_create_records", "get_worksheet_structure"],
            "receiptPath": ".build/receipts/step5-sample-data.json",
            "taskContextPath": ".build/task-context/step5-sample-data.json",
            "isBackground": True,
            "planSlice": {
                "worksheets": [
                    {
                        "name": w.get("name"),
                        "worksheetType": w.get("worksheetType", "normal"),
                        "parentWorksheet": w.get("parentWorksheet", ""),
                        "requirements": w.get("requirements", []),
                    }
                    for w in worksheets
                    if isinstance(w, dict)
                ],
                "appLanguage": app_lang,
            },
            "contextSlice": {
                "appId": app_id,
                "worksheetIdByName": ws_id_by_name,
                "fieldOptionsContext": field_options_ctx,
            },
            "worksheetContextSlice": ws_context,
            "desc": "按拓扑顺序批量填报高仿真示例数据",
        })

        # Step 6: 自定义页面组装与 summary 布局校正
        for page in custom_pages:
            if not isinstance(page, dict):
                continue
            name = page.get("name", "")
            tasks.append({
                "taskId": f"step6-page-{normalize_name(name)}",
                "taskName": f"[Step 6] 页面组件组装 - {name}",
                "step": "6",
                "target": {"type": "page", "id": page_id_by_name.get(name, ""), "name": name},
                "stepFile": "build/steps/6_create_pages.md",
                "references": [
                    "references/hap-domain-custom-page-spec.md",
                    "references/hap-chart-design-guide.md",
                    "references/hap-icon-palette.md",
                ],
                "allowedTools": ["update_custom_page", "get_custom_page_structure", "patch_custom_page_components"],
                "receiptPath": f".build/receipts/step6-page-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step6-page-{normalize_name(name)}.json",
                "planSlice": {"page": page, "appColor": app_color, "appLanguage": app_lang},
                "contextSlice": {
                    "appId": app_id,
                    "pageId": page_id_by_name.get(name, ""),
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name,
                    "viewsByWorksheet": views_by_ws,
                },
                "worksheetContextSlice": ws_context,
                "desc": f"配置自定义页面组件并通过 summary 校验布局: {name}",
            })

        # Step 8: 角色精细权限并发构建（注：Step 7 应用项排序收归主调度器内联执行；工作流设计与创建在阶段 4 一体化执行）
        for role in roles:
            if not isinstance(role, dict):
                continue
            name = role.get("name", "")
            tasks.append({
                "taskId": f"step8-role-{normalize_name(name)}",
                "taskName": f"[Step 8] 角色权限 - {name}",
                "step": "8",
                "target": {"type": "role", "name": name},
                "stepFile": "build/steps/8_create_roles.md",
                "references": ["references/hap-domain-role-spec.md", "references/hap-app-design-guide.md"],
                "allowedTools": ["create_role", "get_role_list"],
                "receiptPath": f".build/receipts/step8-role-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step8-role-{normalize_name(name)}.json",
                "planSlice": {"role": role, "appLanguage": app_lang},
                "contextSlice": {
                    "appId": app_id,
                    "worksheetIdByName": ws_id_by_name,
                    "viewIdByName": view_id_by_name,
                    "viewsByWorksheet": views_by_ws,
                    "customPageIdByName": page_id_by_name,
                    "chatbotIdByName": chatbot_id_by_name,
                },
                "worksheetContextSlice": {},
                "desc": f"创建角色并推演精细权限矩阵: {name}",
            })

    # 阶段 4: Step 10 系统流与 Step 11 动作流「设计+创建+校验发布」一体化并发执行
    elif stage in ("config_completed", "phase4_deploy"):
        role_ctx = context.get("roleContext", [])
        view_id_by_name = context.get("viewIdByName", {})
        proc_id_by_key = context.get("actionProcessIdByKey", {})
        wf_index = [{"name": w.get("name"), "description": w.get("description", ""), "trigger": w.get("trigger", {})} for w in workflows if isinstance(w, dict)]
        act_index = [{"worksheet": a.get("worksheet"), "name": a.get("name"), "description": a.get("description", "")} for a in action_workflows]

        for wf in workflows:
            if not isinstance(wf, dict):
                continue
            name = wf.get("name", "")
            tasks.append({
                "taskId": f"step10-sys-wf-{normalize_name(name)}",
                "taskName": f"[Step 10] 设计并部署系统流 - {name}",
                "step": "10",
                "target": {"type": "workflow", "name": name},
                "stepFile": "build/steps/10_create_workflows.md",
                "references": ["references/hap-workflow-design-guide.md", "references/hap-domain-workflow-spec.md"],
                "allowedTools": SYSTEM_WORKFLOW_TOOLS,
                "receiptPath": f".build/receipts/step10-sys-wf-{normalize_name(name)}.json",
                "taskContextPath": f".build/task-context/step10-sys-wf-{normalize_name(name)}.json",
                "planSlice": {
                    "workflow": wf,
                    "workflowIndex": wf_index,
                    "customActionIndex": act_index,
                    "relationLayouts": rel_layout_by_ws,
                    "appLanguage": app_lang,
                },
                "contextSlice": {
                    "appId": app_id,
                    "org_id": org_id,
                    "worksheetIdByName": ws_id_by_name,
                    "roleContext": role_ctx,
                    "viewIdByName": view_id_by_name,
                },
                "worksheetContextSlice": ws_context,
                "desc": f"一体化设计、创建、校验并发布系统工作流: {name}",
            })

        for act in action_workflows:
            ws_n = act.get("worksheet", "")
            act_n = act.get("name", "未命名动作流")
            comp_key = f"{ws_n}::{act_n}"
            safe_key = f"{normalize_name(ws_n)}_{normalize_name(act_n)}"
            proc_id = act.get("processId") or proc_id_by_key.get(comp_key, "")
            tasks.append({
                "taskId": f"step11-act-wf-{safe_key}",
                "taskName": f"[Step 11] 设计并部署动作流 - {ws_n}/{act_n}",
                "step": "11",
                "target": {"type": "workflow", "id": proc_id, "name": f"{ws_n}/{act_n}"},
                "stepFile": "build/steps/11_create_action_workflows.md",
                "references": ["references/hap-workflow-design-guide.md", "references/hap-domain-workflow-spec.md"],
                "allowedTools": ACTION_WORKFLOW_TOOLS,
                "receiptPath": f".build/receipts/step11-act-wf-{safe_key}.json",
                "taskContextPath": f".build/task-context/step11-act-wf-{safe_key}.json",
                "planSlice": {
                    "actionWorkflow": act,
                    "workflowIndex": wf_index,
                    "customActionIndex": act_index,
                    "relationLayouts": rel_layout_by_ws,
                    "appLanguage": app_lang,
                },
                "contextSlice": {
                    "appId": app_id,
                    "org_id": org_id,
                    "processId": proc_id,
                    "worksheetIdByName": ws_id_by_name,
                    "roleContext": role_ctx,
                    "viewIdByName": view_id_by_name,
                },
                "worksheetContextSlice": ws_context,
                "desc": f"一体化设计节点、注入预建动作流、校验并发布: {ws_n}/{act_n}",
            })

    return tasks


def extract_h2_sections(md_text: str, keywords: List[str]) -> str:
    """从大型指南中按二级标题关键词提取指定章节，避免塞入数十 KB 无关内容。"""
    lines = md_text.splitlines(keepends=True)
    spans = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            spans.append((idx, line.strip()))
    if not spans:
        return md_text
    selected = []
    for pos, (start, title) in enumerate(spans):
        end = spans[pos + 1][0] if pos + 1 < len(spans) else len(lines)
        if any(kw in title for kw in keywords):
            selected.extend(lines[start:end])
    return "".join(selected).strip() + "\n" if selected else md_text


def compile_task_bundles(
    app_dir: str,
    skill_root: str,
    task_def: Dict[str, Any],
    task_ctx_data: Dict[str, Any],
    max_lines: int = 700,
    max_bytes: int = 41000,
) -> List[str]:
    """
    复刻线上 MDAgentService 的 inline:true 预编译机制：
    将 stepFile (SOP) + 必读 references 全文 + taskContext 数据打包为 .build/task-bundles/{taskId}*.md，
    按单次 read_file 上限（< 800 行且 < 46080 字节）自动无损分卷，从物理上消灭 Subagent 漏读或仅用 grep 扫读规范的问题。
    """
    bundle_dir = os.path.join(app_dir, ".build", "task-bundles")
    os.makedirs(bundle_dir, exist_ok=True)
    task_id = task_def["taskId"]
    step = str(task_def.get("step", ""))

    # 清理该 taskId 的历史分卷
    for fname in os.listdir(bundle_dir):
        if fname == f"{task_id}.md" or fname.startswith(f"{task_id}.part"):
            try:
                os.remove(os.path.join(bundle_dir, fname))
            except OSError:
                pass

    step_rel = task_def["stepFile"]
    step_text = load_text(os.path.join(skill_root, step_rel))
    ctx_json_str = json.dumps(task_ctx_data, ensure_ascii=False, indent=2)

    app_id_val = task_ctx_data.get("contextSlice", {}).get("appId", "")
    sections: List[str] = [
        f"# 预编译任务执行包：{task_def.get('taskName', task_id)}\n\n"
        f"- **Task ID**: `{task_id}` | **Step**: `{step}` | **Run ID**: `{task_ctx_data.get('runId', '')}`\n"
        f"- **MCP Server**: `{task_ctx_data.get('mcpServer', '')}` | **当前目标 `appId`**: `{app_id_val}`\n"
        f"- **准许工具白名单 (`allowedTools`)**: `{json.dumps(task_ctx_data.get('allowedTools', []), ensure_ascii=False)}`\n"
        f"- **回执落盘路径 (`receiptPath`)**: `{task_ctx_data.get('receiptPath', '')}`\n"
        f"- **⚠️ Lazy MCP 必读 Schema 与 `appId` 必传铁律**：下方文档中的 `tool(...)` 仅为重点参数简写！通过 `call_mcp_tool` 首次调用任何工具前必须先 `read_file` 读取其 `.json` Schema 核对 `required` 字段；除 `find_member`/`find_department`/`get_current_user` 等组织级接口外，**所有应用内读写工具均须显式传入 `\"appId\": \"{app_id_val}\"`**（若遇 `10001` 或 `401` 报错，立即检查是否漏传 `appId`）。\n\n"
        f"---\n\n## [1] 步骤执行 SOP (`{step_rel}`)\n\n{step_text.strip()}\n\n"
        f"---\n\n## [2] 专属任务上下文数据 (`taskContext`)\n\n```json\n{ctx_json_str}\n```\n"
    ]

    plan_dump = json.dumps(task_def.get("planSlice", {}), ensure_ascii=False).lower()
    ref_rel_list = task_def.get("references") or []
    for idx, ref_rel in enumerate(ref_rel_list, start=3):
        # Step 2a 若不涉及自定义自由字段，无需内联 custom-field-spec
        if step == "2a" and "custom-field-spec" in ref_rel:
            if not any(k in plan_dump for k in ("customfield", "customwidget", "自由字段", "自定义字段", "48", "54")):
                continue
        ref_text = load_text(os.path.join(skill_root, ref_rel))
        if not ref_text:
            continue
        # Step 8 角色权限只需 hap-app-design-guide 中的角色与外部门户章节
        if step == "8" and ref_rel.endswith("hap-app-design-guide.md"):
            ref_text = extract_h2_sections(ref_text, ["角色权限", "外部门户"])
        sections.append(f"---\n\n## [{idx}] 必读领域规范全文 (`{ref_rel}`)\n\n{ref_text.strip()}\n")

    full_lines = ("\n".join(sections)).splitlines(keepends=True)

    # 按行数与 UTF-8 字节数双重安全阈值切分分卷
    chunks: List[List[str]] = []
    cur_lines: List[str] = []
    cur_bytes = 0
    header_reserve_bytes = 350

    for line in full_lines:
        lb = len(line.encode("utf-8"))
        if cur_lines and (len(cur_lines) + 1 > max_lines or cur_bytes + lb + header_reserve_bytes > max_bytes):
            chunks.append(cur_lines)
            cur_lines = []
            cur_bytes = 0
        cur_lines.append(line)
        cur_bytes += lb
    if cur_lines:
        chunks.append(cur_lines)

    out_paths: List[str] = []
    total_parts = len(chunks)
    for i, ch in enumerate(chunks, start=1):
        if total_parts == 1:
            p = os.path.join(bundle_dir, f"{task_id}.md")
            banner = f"> **[完整单卷 1/1]** 本文件已内联 SOP、专属数据与全部必读规范正文，无需额外读取外部参考文档。\n\n"
        else:
            p = os.path.join(bundle_dir, f"{task_id}.part{i}.md")
            banner = f"> **[预编译任务包 分卷 {i}/{total_parts}]** ⚠️ 请务必在同一轮并行 `read_file` 读齐全部 {total_parts} 个分卷后再开始执行！\n\n"
        with open(p, "w", encoding="utf-8") as f:
            f.write(banner + "".join(ch))
        out_paths.append(p)

    return out_paths


def cmd_init(app_dir: str, skill_dir: str, mcp_server: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    # 若位于 .hap-copilot/ 隐藏工作目录内，自动写入 .gitignore 防止污染宿主仓库
    parts = app_dir.split(os.sep)
    if ".hap-copilot" in parts:
        idx = parts.index(".hap-copilot")
        hidden_root = os.sep.join(parts[: idx + 1]) or os.sep
        os.makedirs(hidden_root, exist_ok=True)
        gi_path = os.path.join(hidden_root, ".gitignore")
        if not os.path.exists(gi_path):
            with open(gi_path, "w", encoding="utf-8") as f:
                f.write("*\n")
    build_dir = os.path.join(app_dir, ".build")
    os.makedirs(os.path.join(build_dir, "task-context"), exist_ok=True)
    os.makedirs(os.path.join(build_dir, "task-bundles"), exist_ok=True)
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
        "status": "active",
    }
    save_json(os.path.join(build_dir, "run.json"), run_data)
    return {
        "runId": run_id,
        "executionMode": "subagent_required",
        "initialized": True,
        "buildDir": build_dir,
    }


def cmd_prepare(app_dir: str, progress: Optional[str], include_pending_capacity: bool = False) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    skill_root = get_skill_root()
    context = load_json(os.path.join(app_dir, "hap-context.json")) or {}
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
        ref_rel_list = t.get("references") or ([t["primaryRef"]] if t.get("primaryRef") else [])
        abs_refs = [os.path.join(skill_root, r) for r in ref_rel_list]
        allowed_tools = t.get("allowedTools", [])

        task_ctx_data = {
            "taskId": task_id,
            "taskName": t.get("taskName", task_id),
            "runId": run_id,
            "step": t["step"],
            "target": t["target"],
            "mcpServer": run_data.get("mcpServer", "hap_sandbox_mcp"),
            "stepFile": os.path.join(skill_root, t["stepFile"]),
            "references": abs_refs,
            "allowedTools": allowed_tools,
            "receiptPath": abs_receipt,
            "planSlice": t.get("planSlice", {}),
            "contextSlice": t.get("contextSlice", {}),
            "worksheetContextSlice": t.get("worksheetContextSlice", {}),
        }
        save_json(abs_task_ctx, task_ctx_data)

        expected_agent = registry.get(task_id, {}).get("agentId", "")
        if is_task_succeeded(abs_receipt, task_id, run_id, expected_agent):
            completed_task_ids.append(task_id)
        else:
            bundle_files = compile_task_bundles(app_dir, skill_root, t, task_ctx_data)
            task_status = registry.get(task_id, {}).get("status", "planned")
            ready_entry = {
                "taskId": task_id,
                "taskName": t.get("taskName", task_id),
                "step": t["step"],
                "stepFile": os.path.join(skill_root, t["stepFile"]),
                "primaryRef": abs_refs[0] if abs_refs else "",
                "references": abs_refs,
                "bundleFiles": bundle_files,
                "allowedTools": allowed_tools,
                "taskContext": abs_task_ctx,
                "receiptPath": abs_receipt,
                "isBackground": t.get("isBackground", False),
                "desc": t.get("desc", ""),
            }
            if task_status == "running":
                running_tasks.append(task_id)
            elif task_status == "pending_capacity":
                pending_capacity_tasks.append(task_id)
                if include_pending_capacity:
                    ready_tasks.append(ready_entry)
            else:
                ready_tasks.append(ready_entry)

    manifest_data = {
        "stage": stage,
        "currentProgress": current_progress,
        "totalTasks": len(all_tasks),
        "readyCount": len(ready_tasks),
        "runningCount": len(running_tasks),
        "pendingCapacityCount": len(pending_capacity_tasks),
        "completedCount": len(completed_task_ids),
        "updatedAt": datetime.datetime.now().isoformat(),
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
        "canAdvance": (len(ready_tasks) == 0 and len(running_tasks) == 0),
        "readyTasks": ready_tasks,
    }


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
        "timestamp": datetime.datetime.now().isoformat(),
    }
    save_json(record_file, registry)
    return {"taskId": task_id, "status": status, "agentId": agent_id, "recorded": True}


def cmd_refresh(app_dir: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    context = load_json(os.path.join(app_dir, "hap-context.json")) or {}
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
        "phaseComplete": (succeeded == len(all_tasks)),
    }


def cmd_finalize(app_dir: str, progress: Optional[str]) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    skill_root = get_skill_root()
    context = load_json(os.path.join(app_dir, "hap-context.json")) or {}
    run_data = load_json(os.path.join(app_dir, ".build", "run.json")) or {}
    run_id = run_data.get("runId", "")
    registry = load_json(os.path.join(app_dir, ".build", "dispatch-registry.json")) or {}

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
                errors.append(f"任务 [{task_id}] 凭证校验失败 (runId/agentId 不符或缺少验证证据)")
            else:
                succeeded_tasks.append(task_id)

    if stage in ("config_completed", "phase4_deploy"):
        blocking_tasks = [t["taskId"] for t in all_tasks]
    else:
        blocking_tasks = [t["taskId"] for t in all_tasks if not t.get("isBackground", False)]

    blocking_running = [tid for tid in running_tasks if tid in blocking_tasks]
    blocking_failed = [tid for tid in failed_tasks if tid in blocking_tasks]
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
                "customPages": len(outputs.get("customPageIdByName", {})),
            })

        elif stage in ("app_created", "step2a"):
            ws_id_by_name = dict(context.get("worksheetIdByName", {}))
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

        elif stage in ("worksheets_created", "phase2_single_table"):
            merge_script = os.path.join(skill_root, "scripts", "merge_worksheet_context.py")
            res = subprocess.run([sys.executable, merge_script, app_dir], capture_output=True, text=True)
            if res.returncode != 0:
                can_advance = False
                errors.append(f"merge_worksheet_context.py 校验失败: {res.stderr or res.stdout}")
            else:
                view_id_by_name = dict(context.get("viewIdByName", {}))
                action_id_by_name = dict(context.get("actionIdByName", {}))
                chatbot_id_by_name = dict(context.get("chatbotIdByName", {}))
                for t in all_tasks:
                    r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                    outputs = r_data.get("outputs", {})
                    if isinstance(outputs.get("viewIdByName"), dict):
                        view_id_by_name.update(outputs["viewIdByName"])
                    if isinstance(outputs.get("actionIdByName"), dict):
                        action_id_by_name.update(outputs["actionIdByName"])
                    if isinstance(outputs.get("chatbotIdByName"), dict):
                        chatbot_id_by_name.update(outputs["chatbotIdByName"])
                    elif outputs.get("chatbotName") and outputs.get("chatbotId"):
                        chatbot_id_by_name[outputs["chatbotName"]] = outputs["chatbotId"]

                next_progress = "fields_refreshed"
                stage_outputs.update({
                    "fieldsRefreshed": True,
                    "viewsCreated": len(view_id_by_name),
                    "actionsCreated": len(action_id_by_name),
                    "chatbotsCreated": len(chatbot_id_by_name),
                    "businessRulesConfigured": True,
                })

        elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
            role_id_by_name = dict(context.get("roleIdByName", {}))
            wf_designed_count = 0
            for t in all_tasks:
                r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                outputs = r_data.get("outputs", {})
                if isinstance(outputs.get("roleIdByName"), dict):
                    role_id_by_name.update(outputs["roleIdByName"])
                elif outputs.get("roleName") and outputs.get("roleId"):
                    role_id_by_name[outputs["roleName"]] = outputs["roleId"]
                if outputs.get("workflowDesign") or outputs.get("actionWorkflowDesign"):
                    wf_designed_count += 1

            next_progress = "config_completed"
            stage_outputs.update({
                "rolesCreated": len(role_id_by_name),
                "workflowsDesigned": wf_designed_count,
                "sampleDataDispatched": True,
            })

        elif stage in ("config_completed", "phase4_deploy"):
            next_progress = "completed"
            stage_outputs["buildCompleted"] = True

    report_data = {
        "schemaVersion": "1.1",
        "runId": run_id,
        "phase": stage,
        "progressBefore": current_progress,
        "taskSummary": {
            "expected": total_expected,
            "succeeded": len(succeeded_tasks),
            "failed": len(failed_tasks),
            "running": len(running_tasks),
            "pendingCapacity": 0,
            "retryPending": 0,
        },
        "execution": {
            "mode": "subagent_required",
            "subagentExecutionVerified": (all(tid in succeeded_tasks for tid in blocking_tasks) if total_expected > 0 else True),
            "inlineExecutionDetected": False,
        },
        "outputs": stage_outputs,
        "validation": {"passed": can_advance, "errors": errors, "warnings": []},
        "nextProgress": next_progress,
        "canAdvance": can_advance,
        "runningTaskIds": running_tasks,
        "failedTaskIds": failed_tasks,
    }
    save_json(os.path.join(app_dir, ".build", "phase-report.json"), report_data)
    return report_data


def cmd_advance(app_dir: str) -> Dict[str, Any]:
    app_dir = os.path.abspath(app_dir)
    report = load_json(os.path.join(app_dir, ".build", "phase-report.json"))
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
        if plan.get("language"):
            context["language"] = plan["language"]

    elif stage in ("app_created", "step2a"):
        ws_id_by_name = context.get("worksheetIdByName", {})
        rel_layout_by_ws = context.get("relationLayoutByWorksheet", {})
        ws_fields_preview = context.get("worksheetFieldsPreview", {})
        field_options_ctx = list(context.get("fieldOptionsContext", []))
        existing_opt_ws = {item.get("name") for item in field_options_ctx if isinstance(item, dict)}

        for t in all_tasks:
            if t["step"] == "2a":
                r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
                outputs = r_data.get("outputs", {})
                ws_name = outputs.get("worksheetName") or t["target"].get("name")
                ws_id = outputs.get("worksheetId")
                if ws_name and ws_id:
                    ws_id_by_name[ws_name] = ws_id
                if ws_name and isinstance(outputs.get("relationLayout"), list) and outputs["relationLayout"]:
                    rel_layout_by_ws[ws_name] = outputs["relationLayout"]
                if ws_name and isinstance(outputs.get("fields"), list):
                    ws_fields_preview[ws_name] = [
                        {"name": f.get("name"), "id": f.get("id"), "alias": f.get("alias"), "type": f.get("type")}
                        for f in outputs["fields"]
                        if isinstance(f, dict)
                    ]
                    opt_fields = [
                        {"name": f.get("name"), "alias": f.get("alias"), "options": f.get("options")}
                        for f in outputs["fields"]
                        if isinstance(f, dict) and f.get("options")
                    ]
                    if opt_fields and ws_name not in existing_opt_ws:
                        field_options_ctx.append({"name": ws_name, "fields": opt_fields})
                        existing_opt_ws.add(ws_name)
            elif t["step"] == "1b":
                if os.path.exists(os.path.join(app_dir, t["receiptPath"])):
                    context["appDescUpdated"] = True

        context["worksheetIdByName"] = ws_id_by_name
        context["relationLayoutByWorksheet"] = rel_layout_by_ws
        context["worksheetFieldsPreview"] = ws_fields_preview
        context["fieldOptionsContext"] = field_options_ctx

    elif stage in ("worksheets_created", "phase2_single_table"):
        view_id_by_name = context.get("viewIdByName", {})
        views_by_ws = context.get("viewsByWorksheet", {})
        action_id_by_name = context.get("actionIdByName", {})
        action_proc_by_key = context.get("actionProcessIdByKey", {})
        chatbot_id_by_name = context.get("chatbotIdByName", {})

        for t in all_tasks:
            r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
            outputs = r_data.get("outputs", {})
            ws_name = outputs.get("worksheetName") or t["target"].get("name", "")
            if isinstance(outputs.get("viewIdByName"), dict):
                view_id_by_name.update(outputs["viewIdByName"])
            if ws_name and isinstance(outputs.get("views"), list):
                views_by_ws[ws_name] = outputs["views"]
                for v in outputs["views"]:
                    if isinstance(v, dict) and v.get("name") and v.get("id"):
                        view_id_by_name.setdefault(f"{ws_name}/{v['name']}", v["id"])
            if isinstance(outputs.get("actionIdByName"), dict):
                action_id_by_name.update(outputs["actionIdByName"])
            if ws_name and isinstance(outputs.get("actions"), list):
                for act in outputs["actions"]:
                    if isinstance(act, dict) and act.get("name"):
                        a_name = act["name"]
                        if act.get("id"):
                            action_id_by_name.setdefault(f"{ws_name}/{a_name}", act["id"])
                        if act.get("processId"):
                            action_proc_by_key[f"{ws_name}::{a_name}"] = act["processId"]
            if isinstance(outputs.get("chatbotIdByName"), dict):
                chatbot_id_by_name.update(outputs["chatbotIdByName"])
            elif outputs.get("chatbotName") and outputs.get("chatbotId"):
                chatbot_id_by_name[outputs["chatbotName"]] = outputs["chatbotId"]
            if isinstance(outputs.get("chatbotContext"), list):
                for b in outputs["chatbotContext"]:
                    if isinstance(b, dict) and b.get("name") and b.get("id"):
                        chatbot_id_by_name[b["name"]] = b["id"]

        context["viewIdByName"] = view_id_by_name
        context["viewsByWorksheet"] = views_by_ws
        context["actionIdByName"] = action_id_by_name
        context["actionProcessIdByKey"] = action_proc_by_key
        context["chatbotIdByName"] = chatbot_id_by_name

    elif stage in ("fields_refreshed", "phase3_configs", "page_shells_created", "phase3"):
        role_id_by_name = context.get("roleIdByName", {})
        role_ctx = list(context.get("roleContext", []))
        seen_roles = {r.get("name") for r in role_ctx if isinstance(r, dict)}
        wf_designs = context.get("workflowDesigns", {})
        act_wf_designs = context.get("actionWorkflowDesigns", {})
        page_results = []

        for t in all_tasks:
            r_path = os.path.join(app_dir, t["receiptPath"])
            if not os.path.exists(r_path):
                continue
            r_data = load_json(r_path) or {}
            outputs = r_data.get("outputs", {})
            if isinstance(outputs.get("roleIdByName"), dict):
                role_id_by_name.update(outputs["roleIdByName"])
            if outputs.get("roleName") and outputs.get("roleId"):
                r_name = outputs["roleName"]
                r_id = outputs["roleId"]
                role_id_by_name[r_name] = r_id
                if r_name not in seen_roles:
                    role_ctx.append({"name": r_name, "id": r_id, "roleScope": outputs.get("roleScope", "general")})
                    seen_roles.add(r_name)
            if isinstance(outputs.get("workflowDesign"), dict):
                wd = outputs["workflowDesign"]
                if wd.get("name"):
                    wf_designs[wd["name"]] = wd
            if isinstance(outputs.get("actionWorkflowDesign"), dict):
                ad = outputs["actionWorkflowDesign"]
                ws_n = ad.get("worksheet") or ad.get("worksheetName", "")
                act_n = ad.get("name") or ad.get("actionName", "")
                if act_n:
                    act_wf_designs[f"{ws_n}::{act_n}"] = ad
            if t["step"] == "6":
                page_results.append({
                    "pageName": outputs.get("pageName") or t["target"].get("name"),
                    "completed": bool(outputs.get("completed", True)),
                    "notes": outputs.get("notes", []),
                })
            if t["step"] == "5" and r_data.get("status") == "succeeded":
                context["sampleDataCreated"] = True

        context["roleIdByName"] = role_id_by_name
        context["roleContext"] = role_ctx
        context["workflowDesigns"] = wf_designs
        context["actionWorkflowDesigns"] = act_wf_designs
        context["pageConfigurationResults"] = page_results

    elif stage in ("config_completed", "phase4_deploy"):
        workflows = plan.get("workflows", [])
        wf_map = {wf.get("name"): wf for wf in workflows if isinstance(wf, dict)}
        wf_results = []
        act_wf_results = []

        for t in all_tasks:
            r_data = load_json(os.path.join(app_dir, t["receiptPath"])) or {}
            outputs = r_data.get("outputs", {})
            if t["step"] == "10":
                wf_name = outputs.get("workflowName") or t["target"].get("name")
                proc_id = outputs.get("processId", "")
                st = outputs.get("status", "published" if proc_id else "draft")
                wf_results.append({
                    "name": wf_name,
                    "id": proc_id,
                    "status": st,
                    "description": outputs.get("description", ""),
                })
                if wf_name in wf_map and proc_id:
                    wf_map[wf_name]["processId"] = proc_id
                    wf_map[wf_name]["published"] = (st == "published")
            elif t["step"] == "11":
                ws_n = outputs.get("worksheetName", "")
                act_n = outputs.get("actionName", "")
                proc_id = outputs.get("processId") or t["target"].get("id", "")
                st = outputs.get("status", "published" if proc_id else "draft")
                act_wf_results.append({
                    "worksheet": ws_n,
                    "name": act_n,
                    "id": proc_id,
                    "status": st,
                    "description": outputs.get("description", ""),
                })
            elif t["isBackground"]:
                pass

        # 终态顺带收口后台任务标记
        if os.path.exists(os.path.join(app_dir, ".build", "receipts", "step5-sample-data.json")):
            context["sampleDataCreated"] = True
        if os.path.exists(os.path.join(app_dir, ".build", "receipts", "step1b-app-desc.json")):
            context["appDescUpdated"] = True

        plan["workflows"] = list(wf_map.values())
        context["workflowResults"] = wf_results
        context["customActionWorkflowResults"] = act_wf_results
        save_json(plan_path, plan)

    context["progress"] = next_progress
    context["buildRun"] = {
        "runId": report.get("runId", ""),
        "executionMode": "subagent_required",
        "lastPhaseReport": ".build/phase-report.json",
        "blocked": False,
    }
    save_json(context_path, context)

    return {
        "advanced": True,
        "stage": stage,
        "newProgress": next_progress,
        "contextPath": context_path,
    }


def main():
    parser = argparse.ArgumentParser(description="HAP App Copilot 报告驱动型薄运行时引擎")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="初始化 .build 运行目录与执行策略")
    p_init.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_init.add_argument("--skill-dir", type=str, default="", help="Skill 根目录")
    p_init.add_argument("--mcp-server", type=str, default="hap_sandbox_mcp", help="MCP 服务名")

    p_prep = subparsers.add_parser("prepare", help="计算阶段就绪任务并生成切片上下文")
    p_prep.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_prep.add_argument("--progress", type=str, default="", help="可选显式指定 progress")
    p_prep.add_argument("--include-pending-capacity", action="store_true", help="是否包含容量等待任务")

    p_disp = subparsers.add_parser("dispatched", help="记录已成功派发任务")
    p_disp.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_disp.add_argument("--task-id", type=str, required=True, help="任务 ID")
    p_disp.add_argument("--agent-id", type=str, required=True, help="Subagent 实例 ID")

    p_cap = subparsers.add_parser("capacity-wait", help="标记任务进入容量等待")
    p_cap.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_cap.add_argument("--task-id", type=str, required=True, help="任务 ID")

    p_df = subparsers.add_parser("dispatch-failed", help="记录任务派发失败")
    p_df.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_df.add_argument("--task-id", type=str, required=True, help="任务 ID")
    p_df.add_argument("--reason-code", type=str, default="SUBAGENT_TOOL_ERROR", help="失败原因码")

    p_ref = subparsers.add_parser("refresh", help="刷新任务状态与进度摘要")
    p_ref.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")

    p_fin = subparsers.add_parser("finalize", help="汇总校验回执并生成阶段报告")
    p_fin.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")
    p_fin.add_argument("--progress", type=str, default="", help="可选显式指定 progress")

    p_adv = subparsers.add_parser("advance", help="在报告放行后原子推进状态机")
    p_adv.add_argument("--app-dir", type=str, required=True, help="应用项目根目录")

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
        res = {"error": f"Unknown command: {args.command}"}

    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.command == "finalize":
        sys.exit(0 if res.get("canAdvance") else 1)


if __name__ == "__main__":
    main()
