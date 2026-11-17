#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_context.py
HAP App Copilot 渐进加载上下文动态解析与章节级点读引擎。

支持能力：
1. --mode {plan,build,modify,audit} --assets/--domains ... [--render]：
   按当前场景与目标领域计算最小参考清单，或直接渲染裁剪后的 Modify / Audit 上下文包；
2. --file <rel_path> [--section <关键词> | --list-sections]：
   对大体积设计指南或领域 Spec 执行二级章节精准点读（对齐线上 load_skill(skillName, section)）；
3. --validate：
   自检全库所有模式、构建步骤与领域资产映射文件的物理存在性。
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Set

# modify/modify_guide.md 章节映射（支持多项映射，如 chart 同时关联页面图表与工作表统计图）
MODIFY_GUIDE_SECTION_MAPPING: Dict[str, List[str]] = {
    "app": ["第 2 章"],
    "navigation": ["第 2 章"],
    "app_nav": ["第 2 章"],
    "app_navigation": ["第 2 章"],
    "worksheet": ["第 3 章"],
    "field": ["第 3 章"],
    "relation": ["第 3 章"],
    "layout": ["第 3 章"],
    "rule": ["第 3 章"],
    "business_rule": ["第 3 章"],
    "index": ["第 3 章"],
    "worksheet_index": ["第 3 章"],
    "worksheet_filter": ["第 3 章"],
    "custom_field": ["第 3 章"],
    "free_field": ["第 3 章"],
    "view": ["第 4 章"],
    "action": ["第 4 章"],
    "view_action": ["第 4 章"],
    "role": ["第 5 章"],
    "permission": ["第 5 章"],
    "role_permission": ["第 5 章"],
    "page": ["第 6 章"],
    "custom_page": ["第 6 章"],
    "worksheet_chart": ["第 7 章"],
    "page_chart": ["第 6 章", "第 7 章"],
    "chart": ["第 6 章", "第 7 章"],
    "chatbot": ["第 8 章"],
    "print_template": ["第 9 章"],
    "template": ["第 9 章"],
    "public_form": ["第 10 章"],
    "external_portal": ["第 11 章"],
    "portal": ["第 11 章"],
    "workflow": ["第 12 章"],
    "workflow_design": ["第 12 章"],
    "record": ["第 13 章"],
    "data": ["第 13 章"],
    "record_data": ["第 13 章"],
    "sample_data": ["第 13 章"],
}

MODIFY_GUIDE_SECTION_ORDER: List[str] = [
    "第 1 章",
    "第 2 章",
    "第 3 章",
    "第 4 章",
    "第 5 章",
    "第 6 章",
    "第 7 章",
    "第 8 章",
    "第 9 章",
    "第 10 章",
    "第 11 章",
    "第 12 章",
    "第 13 章",
]

# modify/impact-map.md 二级章节关键词映射
IMPACT_MAP_SECTION_MAPPING: Dict[str, List[str]] = {
    "app": ["应用与导航"],
    "navigation": ["应用与导航"],
    "app_nav": ["应用与导航"],
    "app_navigation": ["应用与导航"],
    "public_form": ["应用与导航"],
    "external_portal": ["应用与导航"],
    "portal": ["应用与导航"],
    "worksheet": ["工作表、字段、业务规则与索引"],
    "field": ["工作表、字段、业务规则与索引"],
    "relation": ["工作表、字段、业务规则与索引"],
    "layout": ["工作表、字段、业务规则与索引"],
    "rule": ["工作表、字段、业务规则与索引"],
    "business_rule": ["工作表、字段、业务规则与索引"],
    "index": ["工作表、字段、业务规则与索引"],
    "worksheet_index": ["工作表、字段、业务规则与索引"],
    "worksheet_filter": ["工作表、字段、业务规则与索引"],
    "custom_field": ["工作表、字段、业务规则与索引"],
    "free_field": ["工作表、字段、业务规则与索引"],
    "view": ["视图与自定义动作"],
    "action": ["视图与自定义动作"],
    "view_action": ["视图与自定义动作"],
    "page": ["自定义页面与统计图表"],
    "custom_page": ["自定义页面与统计图表"],
    "page_chart": ["自定义页面与统计图表"],
    "chart": ["自定义页面与统计图表"],
    "worksheet_chart": ["自定义页面与统计图表"],
    "chatbot": ["AI 助手、打印模板、角色与工作流/数据"],
    "print_template": ["AI 助手、打印模板、角色与工作流/数据"],
    "template": ["AI 助手、打印模板、角色与工作流/数据"],
    "role": ["AI 助手、打印模板、角色与工作流/数据"],
    "permission": ["AI 助手、打印模板、角色与工作流/数据"],
    "role_permission": ["AI 助手、打印模板、角色与工作流/数据"],
    "workflow": ["AI 助手、打印模板、角色与工作流/数据"],
    "workflow_design": ["AI 助手、打印模板、角色与工作流/数据"],
    "record": ["AI 助手、打印模板、角色与工作流/数据"],
    "data": ["AI 助手、打印模板、角色与工作流/数据"],
    "record_data": ["AI 助手、打印模板、角色与工作流/数据"],
    "sample_data": ["AI 助手、打印模板、角色与工作流/数据"],
}

MODIFY_COMPLEX_SCENARIOS: Set[str] = {
    "physical_delete",
    "published_workflow",
    "fixed_value_mapping",
    "bulk_data_update",
    "complex_conversion",
    "cross_table_migration",
    "dependency_governance",
}

MODIFY_DATA_SCENARIOS: Set[str] = {
    "fixed_value_mapping",
    "bulk_data_update",
    "complex_conversion",
    "cross_table_migration",
    "dependency_governance",
}

AUDIT_CHECK_PREFIXES: Dict[str, str] = {
    "STR": "structure",
    "BIZ": "business",
    "UX": "user_experience",
    "PRF": "performance",
    "SEC": "security",
}

AUDIT_DIMENSION_SECTIONS: Dict[str, str] = {
    "structure": "三、结构健康度",
    "business": "四、业务完整度",
    "user_experience": "五、用户体验",
    "performance": "六、性能与容量",
    "security": "七、安全与维护",
}

COLLECTION_ASSET_SECTIONS: Dict[str, str] = {
    "app": "应用与导航",
    "navigation": "应用与导航",
    "app_nav": "应用与导航",
    "app_navigation": "应用与导航",
    "external_portal": "公开表单与外部门户",
    "portal": "公开表单与外部门户",
    "worksheet": "工作表与字段",
    "field": "工作表与字段",
    "relation": "工作表与字段",
    "layout": "工作表与字段",
    "worksheet_filter": "视图与常用筛选",
    "public_form": "公开表单与外部门户",
    "view": "视图与常用筛选",
    "action": "自定义动作",
    "view_action": "视图与常用筛选",
    "rule": "业务规则",
    "business_rule": "业务规则",
    "print_template": "打印模板",
    "template": "打印模板",
    "workflow": "工作流",
    "role": "角色与权限",
    "permission": "角色与权限",
    "role_permission": "角色与权限",
    "page": "自定义页面与图表",
    "custom_page": "自定义页面与图表",
    "page_chart": "自定义页面与图表",
    "chart": "自定义页面与图表",
    "worksheet_chart": "自定义页面与图表",
    "chatbot": "AI 对话机器人",
    "record": "业务数据",
    "data": "业务数据",
    "record_data": "业务数据",
}


def get_skill_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_files(
    mode: str,
    assets: List[str],
    scenarios: List[str] = None,
    step: str = None,
) -> List[str]:
    files: Set[str] = set()
    scenarios = scenarios or []

    if mode == "plan":
        files.update([
            "workflows/plan.md",
            "plan/1a_plan_overview.md",
            "plan/1b_plan_schema.md",
            "references/hap-app-design-guide.md",
            "references/hap-workflow-design-guide.md",
            "references/hap-domain-app-spec.md",
            "references/hap-icon-palette.md",
        ])
    elif mode == "build":
        files.update([
            "workflows/build.md",
            "build/CONTEXT.md",
            "build/PROGRESS.md",
            "build/OUTPUT_CONTRACT.md",
            "scripts/build_runtime.py",
            "scripts/merge_worksheet_context.py",
        ])
    elif mode == "modify":
        files.update([
            "workflows/modify.md",
            "modify/impact-map.md",
            "modify/safety-rules.md",
            "modify/execution-boundaries.md",
            "modify/modify_guide.md",
        ])
    elif mode == "audit":
        files.update([
            "workflows/audit.md",
            "audit/audit-checks.md",
            "audit/collection-guide.md",
            "scripts/audit_calc.py",
        ])

    step_mapping: Dict[str, List[str]] = {
        "1": ["build/steps/1_create_app.md", "references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "1b": ["build/steps/1b_update_app_desc.md", "references/hap-domain-app-spec.md"],
        "2a": ["build/steps/2a_create_worksheets.md", "references/hap-domain-worksheet-spec.md", "references/hap-domain-custom-field-spec.md"],
        "2b": ["build/steps/2b_create_relations.md", "references/hap-domain-worksheet-spec.md"],
        "3": [
            "build/steps/3_create_actions_views_rules.md",
            "references/hap-domain-view-spec.md",
            "references/hap-domain-custom-action-spec.md",
            "references/hap-domain-business-rule-spec.md",
        ],
        "4": ["build/steps/4_create_chatbots.md", "references/hap-domain-chatbot-spec.md"],
        "4a": ["build/steps/4_create_chatbots.md", "references/hap-domain-chatbot-spec.md"],
        "4b": ["build/steps/4_create_chatbots.md", "references/hap-domain-chatbot-spec.md"],
        "5": ["build/steps/5_create_sample_data.md", "references/hap-sample-data-spec.md"],
        "6": [
            "build/steps/6_create_pages.md",
            "references/hap-domain-custom-page-spec.md",
            "references/hap-chart-design-guide.md",
            "references/hap-icon-palette.md",
        ],
        "7": ["build/steps/7_sort_app_items.md", "references/hap-domain-app-spec.md"],
        "8": ["build/steps/8_create_roles.md", "references/hap-domain-role-spec.md", "references/hap-app-design-guide.md"],
        "10": [
            "build/steps/10_create_workflows.md",
            "references/hap-workflow-design-guide.md",
            "references/hap-domain-workflow-spec.md",
        ],
        "11": [
            "build/steps/11_create_action_workflows.md",
            "references/hap-workflow-design-guide.md",
            "references/hap-domain-workflow-spec.md",
        ],
    }

    if step and step in step_mapping:
        files.update(step_mapping[step])

    asset_mapping: Dict[str, List[str]] = {
        "app": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "navigation": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "app_nav": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "app_navigation": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "worksheet": ["references/hap-domain-worksheet-spec.md"],
        "field": ["references/hap-domain-worksheet-spec.md"],
        "relation": ["references/hap-domain-worksheet-spec.md"],
        "layout": ["references/hap-domain-worksheet-spec.md"],
        "worksheet_filter": ["references/hap-domain-worksheet-spec.md"],
        "custom_field": ["references/hap-domain-custom-field-spec.md"],
        "free_field": ["references/hap-domain-custom-field-spec.md"],
        "index": ["references/hap-domain-worksheet-index-spec.md"],
        "worksheet_index": ["references/hap-domain-worksheet-index-spec.md"],
        "rule": ["references/hap-domain-business-rule-spec.md"],
        "business_rule": ["references/hap-domain-business-rule-spec.md"],
        "view": ["references/hap-domain-view-spec.md"],
        "action": ["references/hap-domain-custom-action-spec.md"],
        "view_action": ["references/hap-domain-view-spec.md", "references/hap-domain-custom-action-spec.md"],
        "role": ["references/hap-domain-role-spec.md"],
        "permission": ["references/hap-domain-role-spec.md"],
        "role_permission": ["references/hap-domain-role-spec.md"],
        "page": ["references/hap-domain-custom-page-spec.md", "references/hap-chart-design-guide.md"],
        "custom_page": ["references/hap-domain-custom-page-spec.md", "references/hap-chart-design-guide.md"],
        "worksheet_chart": ["references/hap-domain-worksheet-chart-spec.md", "references/hap-chart-design-guide.md"],
        "page_chart": [
            "references/hap-domain-custom-page-spec.md",
            "references/hap-domain-worksheet-chart-spec.md",
            "references/hap-chart-design-guide.md",
        ],
        "chart": [
            "references/hap-domain-custom-page-spec.md",
            "references/hap-domain-worksheet-chart-spec.md",
            "references/hap-chart-design-guide.md",
        ],
        "chatbot": ["references/hap-domain-chatbot-spec.md"],
        "print_template": ["modify/steps/print_template.md"],
        "template": ["modify/steps/print_template.md"],
        "public_form": ["references/hap-domain-worksheet-spec.md"],
        "external_portal": ["references/hap-domain-external-portal-spec.md"],
        "portal": ["references/hap-domain-external-portal-spec.md"],
        "workflow": ["references/hap-domain-workflow-spec.md", "references/hap-workflow-design-guide.md"],
        "workflow_design": ["references/hap-workflow-design-guide.md"],
        "record": ["references/hap-domain-record-data-spec.md"],
        "data": ["references/hap-domain-record-data-spec.md"],
        "record_data": ["references/hap-domain-record-data-spec.md", "references/hap-sample-data-spec.md"],
        "sample_data": ["references/hap-sample-data-spec.md"],
        "icon": ["references/hap-icon-palette.md"],
        "style": ["references/hap-domain-app-spec.md", "references/hap-icon-palette.md"],
        "design": ["references/hap-app-design-guide.md"],
    }

    for a in assets:
        key = a.strip().lower()
        if key in asset_mapping:
            files.update(asset_mapping[key])

    if mode == "modify" and {s.strip().lower() for s in scenarios}.intersection(MODIFY_DATA_SCENARIOS):
        files.add("references/hap-domain-record-data-spec.md")

    return sorted(list(files))


def validate_all_mappings() -> bool:
    skill_root = get_skill_root()
    all_files: Set[str] = set()
    for m in ["plan", "build", "modify", "audit"]:
        all_files.update(resolve_files(m, []))
    for s in ["1", "1b", "2a", "2b", "3", "4a", "4b", "5", "6", "7", "8", "10", "11"]:
        all_files.update(resolve_files("build", [], step=s))
    all_assets = list(MODIFY_GUIDE_SECTION_MAPPING.keys()) + ["icon", "style", "design"]
    for a in all_assets:
        all_files.update(resolve_files("modify", [a]))
    for scenario in sorted(MODIFY_COMPLEX_SCENARIOS):
        all_files.update(resolve_files("modify", [], scenarios=[scenario]))

    missing = []
    for rel_path in sorted(list(all_files)):
        abs_path = os.path.join(skill_root, rel_path)
        if not os.path.exists(abs_path):
            missing.append(rel_path)

    if missing:
        print(f"❌ 发现 {len(missing)} 个缺失的映射文件：", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return False
    print(f"✅ 所有映射文件（共 {len(all_files)} 个）均真实存在且路径有效！")
    return True


def reference_sections(rel_path: str, assets: List[str], scenarios: List[str]) -> List[str]:
    if rel_path == "modify/modify_guide.md":
        sections = {"第 1 章"}
        for asset in assets:
            for sec in MODIFY_GUIDE_SECTION_MAPPING.get(asset.strip().lower(), []):
                sections.add(sec)
        if {s.strip().lower() for s in scenarios}.intersection(MODIFY_DATA_SCENARIOS):
            sections.add("第 13 章")
        return [s for s in MODIFY_GUIDE_SECTION_ORDER if s in sections]
    if rel_path.startswith("modify/steps/"):
        return ["仅文件制作或替换时读取；纯配置和删除跳过"]
    if rel_path.startswith("references/"):
        return ["使用 --file <path> --section <关键词> 按需点读"]
    return ["已裁剪渲染"]


def reference_purpose(rel_path: str) -> str:
    if rel_path == "workflows/modify.md":
        return "Modify 内联执行流程与沟通红线"
    if rel_path == "modify/impact-map.md":
        return "跨领域连带分类与固定依赖顺序"
    if rel_path == "modify/modify_guide.md":
        return "12 领域增量读写规则与精确工具集"
    if rel_path == "modify/safety-rules.md":
        return "二元风险、14 类删除直通与数据阈值底线"
    if rel_path == "modify/execution-boundaries.md":
        return "平台能力边界与跨应用数据源引用规则"
    if rel_path == "audit/audit-checks.md":
        return "Audit 检查项、证据要求与评分规则"
    if rel_path == "audit/collection-guide.md":
        return "Audit 证据范围、接口选择与停止条件"
    if rel_path.startswith("modify/steps/"):
        return "本地文件制作步骤、HAP 专用语法与交付检查"
    if rel_path.endswith("-guide.md"):
        return "业务建模与设计指南"
    if rel_path.startswith("references/hap-domain-"):
        return "领域对象底层参数与合法结构规范"
    return "任务所需参考规范"


def build_reference_records(
    resolved_rel_paths: List[str],
    assets: List[str],
    scenarios: List[str],
    absolute: bool = False,
) -> List[Dict[str, object]]:
    skill_root = get_skill_root()
    records = []
    for rel_path in resolved_rel_paths:
        output_path = os.path.join(skill_root, rel_path) if absolute else rel_path
        records.append({
            "path": output_path,
            "sections": reference_sections(rel_path, assets, scenarios),
            "purpose": reference_purpose(rel_path),
        })
    return records


def extract_guide_sections(content: str, requested_sections: List[str]) -> str:
    """从 modify_guide.md 提取指定的编号二级章节。"""
    lines = content.splitlines(keepends=True)
    heading_indexes = []
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+([0-9]+)\.", line)
        if match:
            heading_indexes.append((index, f"第 {match.group(1)} 章"))

    requested_keys = set(requested_sections)
    selected = []
    for position, (start, key) in enumerate(heading_indexes):
        if key not in requested_keys:
            continue
        end = heading_indexes[position + 1][0] if position + 1 < len(heading_indexes) else len(lines)
        selected.extend(lines[start:end])
    return "".join(selected).rstrip()


def extract_impact_map_sections(content: str, assets: List[str], scenarios: List[str]) -> str:
    """从 impact-map.md 提取公共原则、命中领域的连带表格及固定顺序速查。"""
    lines = content.splitlines(keepends=True)
    h2_spans = []
    for idx, line in enumerate(lines):
        if re.match(r"^##\s+", line):
            h2_spans.append((idx, line.strip()))

    needed_keywords = {"统一分类与交互原则", "跨领域固定依赖顺序速查"}
    for a in assets:
        for kw in IMPACT_MAP_SECTION_MAPPING.get(a.strip().lower(), []):
            needed_keywords.add(kw)
    if {s.strip().lower() for s in scenarios}.intersection(MODIFY_DATA_SCENARIOS):
        needed_keywords.add("AI 助手、打印模板、角色与工作流/数据")

    selected = []
    for pos, (start, title) in enumerate(h2_spans):
        end = h2_spans[pos + 1][0] if pos + 1 < len(h2_spans) else len(lines)
        if any(kw in title for kw in needed_keywords):
            selected.extend(lines[start:end])
    return "".join(selected).rstrip()


def extract_markdown_section_by_keyword(content: str, section_query: str = "", list_only: bool = False) -> str:
    """通用二级章节目录展示与按标题关键词点读（对齐线上 load_skill(skillName, section)）。"""
    lines = content.splitlines(keepends=True)
    h2_spans = []
    for idx, line in enumerate(lines):
        if re.match(r"^##\s+", line):
            h2_spans.append((idx, line.strip()))

    if list_only or not section_query:
        toc = [title for _, title in h2_spans]
        return "可用二级章节列表：\n" + "\n".join(f"- {t}" for t in toc) + "\n"

    queries = [q.strip().lower() for q in section_query.split(",") if q.strip()]
    header = lines[: h2_spans[0][0]] if h2_spans else lines
    matched = []
    for pos, (start, title) in enumerate(h2_spans):
        end = h2_spans[pos + 1][0] if pos + 1 < len(h2_spans) else len(lines)
        title_lower = title.lower()
        if any(q in title_lower for q in queries):
            matched.extend(lines[start:end])

    if not matched:
        toc = "\n".join(f"- {t}" for _, t in h2_spans)
        return f"⚠️ 未找到匹配 '{section_query}' 的二级章节。当前文件可用章节如下：\n{toc}\n"

    return "".join(header + matched).rstrip() + "\n"


def extract_audit_checks(content: str, check_ids: List[str]) -> str:
    lines = content.splitlines(keepends=True)
    needed_dimensions: Set[str] = set()
    for cid in check_ids:
        match = re.match(r"CHK-([A-Z]+)-\d+", cid)
        if match and match.group(1) in AUDIT_CHECK_PREFIXES:
            needed_dimensions.add(AUDIT_CHECK_PREFIXES[match.group(1)])

    section_spans = []
    for index, line in enumerate(lines):
        if re.match(r"^## ", line):
            section_spans.append((index, line.strip()))

    selected = []
    check_id_set = set(check_ids)
    for position, (start, title) in enumerate(section_spans):
        end = section_spans[position + 1][0] if position + 1 < len(section_spans) else len(lines)
        if "执行与证据契约" in title or "评分与评级算法" in title:
            selected.extend(lines[start:end])
            continue
        matched_dimension = False
        for dim, section_keyword in AUDIT_DIMENSION_SECTIONS.items():
            if section_keyword in title and dim in needed_dimensions:
                matched_dimension = True
                break
        if not matched_dimension:
            continue
        section_lines = lines[start:end]
        header_added = False
        for sline in section_lines:
            if sline.startswith("## ") or sline.startswith("| 检查项") or sline.startswith("|---"):
                selected.append(sline)
                header_added = True
            elif sline.startswith("| `CHK-"):
                row_match = re.match(r"^\| `(CHK-[A-Z]+-\d+)`", sline)
                if row_match and row_match.group(1) in check_id_set:
                    selected.append(sline)
            elif not header_added:
                selected.append(sline)

    return "".join(selected).rstrip()


def extract_collection_sections(content: str, asset_types: List[str]) -> str:
    lines = content.splitlines(keepends=True)
    needed_subsections: Set[str] = set()
    for at in asset_types:
        key = at.strip().lower()
        if key in COLLECTION_ASSET_SECTIONS:
            needed_subsections.add(COLLECTION_ASSET_SECTIONS[key])

    h2_spans = []
    for index, line in enumerate(lines):
        if re.match(r"^## ", line):
            h2_spans.append((index, line.strip()))

    selected = []
    for position, (start, title) in enumerate(h2_spans):
        end = h2_spans[position + 1][0] if position + 1 < len(h2_spans) else len(lines)
        if "各类对象的读取规则" in title:
            section_lines = lines[start:end]
            h3_spans_local = []
            for local_idx, sline in enumerate(section_lines):
                if re.match(r"^### ", sline):
                    h3_spans_local.append((local_idx, sline.strip()))
            selected.append(section_lines[0])
            if len(section_lines) > 1 and not section_lines[1].startswith("###"):
                selected.append(section_lines[1])
            for sub_pos, (sub_start, sub_title) in enumerate(h3_spans_local):
                sub_end = h3_spans_local[sub_pos + 1][0] if sub_pos + 1 < len(h3_spans_local) else len(section_lines)
                for needed in needed_subsections:
                    if needed in sub_title:
                        selected.extend(section_lines[sub_start:sub_end])
                        break
        else:
            selected.extend(lines[start:end])

    if h2_spans:
        header = lines[: h2_spans[0][0]]
        return "".join(header + selected).rstrip()
    return "".join(selected).rstrip()


def render_modify_policy_bundle(
    resolved_rel_paths: List[str],
    assets: List[str],
    scenarios: List[str],
    absolute: bool = False,
) -> str:
    skill_root = get_skill_root()
    spec_paths = [p for p in resolved_rel_paths if p.startswith("references/")]
    references = build_reference_records(spec_paths, assets, scenarios, absolute=absolute)
    step_paths = [p for p in resolved_rel_paths if p.startswith("modify/steps/")]
    metadata = {
        "mode": "modify",
        "assets": assets,
        "scenarios": scenarios,
        "specReferences": references,
        "stepReferences": build_reference_records(step_paths, assets, scenarios, absolute=absolute),
        "note": "安全底线、能力边界、对应领域的连带影响表与操作卡已直接渲染；底层 references/hap-*.md 仅在构造复杂参数时用 --file <path> --section <关键词> 按需点读。",
    }
    parts = [
        "# Modify 最小上下文规则包",
        "",
        "## 按需底层规格清单",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
    ]

    render_plan = [
        ("modify/safety-rules.md", "full"),
        ("modify/execution-boundaries.md", "full"),
        ("modify/impact-map.md", "impact"),
        ("modify/modify_guide.md", "guide"),
    ]
    for rel_path, mode_tag in render_plan:
        abs_fp = os.path.join(skill_root, rel_path)
        if not os.path.exists(abs_fp):
            continue
        with open(abs_fp, "r", encoding="utf-8") as file_obj:
            content = file_obj.read()
        if mode_tag == "impact":
            content = extract_impact_map_sections(content, assets, scenarios)
        elif mode_tag == "guide":
            content = extract_guide_sections(content, reference_sections(rel_path, assets, scenarios))
        parts.extend([
            "",
            f"## 已加载：{rel_path}",
            "",
            content.rstrip(),
        ])
    return "\n".join(parts).rstrip() + "\n"


def render_audit_context(
    resolved_rel_paths: List[str],
    audit_checks: List[str],
    audit_assets: List[str],
) -> str:
    skill_root = get_skill_root()
    parts = ["# Audit 最小上下文", ""]

    checks_path = os.path.join(skill_root, "audit", "audit-checks.md")
    if os.path.exists(checks_path):
        with open(checks_path, "r", encoding="utf-8") as f:
            checks_content = f.read()
        if audit_checks:
            extracted = extract_audit_checks(checks_content, audit_checks)
            parts.extend(["## 已加载：audit/audit-checks.md（按需提取）", "", extracted.rstrip(), ""])
        else:
            parts.extend(["## 已加载：audit/audit-checks.md（全文）", "", checks_content.rstrip(), ""])

    guide_path = os.path.join(skill_root, "audit", "collection-guide.md")
    if os.path.exists(guide_path):
        with open(guide_path, "r", encoding="utf-8") as f:
            guide_content = f.read()
        if audit_assets:
            extracted = extract_collection_sections(guide_content, audit_assets)
            parts.extend(["## 已加载：audit/collection-guide.md（按需提取）", "", extracted.rstrip(), ""])
        else:
            parts.extend(["## 已加载：audit/collection-guide.md（全文）", "", guide_content.rstrip(), ""])

    audit_path = os.path.join(skill_root, "workflows", "audit.md")
    if "workflows/audit.md" in resolved_rel_paths and os.path.exists(audit_path):
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_content = f.read()
        parts.extend(["## 已加载：workflows/audit.md（全文）", "", audit_content.rstrip(), ""])

    metadata = {
        "mode": "audit",
        "auditChecks": audit_checks if audit_checks else "all",
        "auditAssets": audit_assets if audit_assets else "all",
        "note": "检查项和采集章节已按需提取。",
    }
    parts.extend([
        "## 按需参考清单",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
    ])
    return "\n".join(parts).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="HAP App Copilot 上下文渐进加载与章节级点读引擎")
    parser.add_argument("--mode", choices=["plan", "build", "modify", "audit"], default="modify", help="工作流模式")
    parser.add_argument("--assets", type=str, default="", help="目标资产/领域列表，逗号分隔 (如 worksheet,public_form,role_permission)")
    parser.add_argument("--domains", type=str, default="", help="--assets 的同义别名，逗号分隔")
    parser.add_argument("--scenarios", type=str, default="", help="可选复杂场景列表，逗号分隔")
    parser.add_argument("--step", type=str, default="", help="Build 步骤编号 (如 2a, 3, 4b, 9a, 10)")
    parser.add_argument("--file", type=str, default="", help="指定单个参考文件相对路径进行二级章节检索 (如 references/hap-app-design-guide.md)")
    parser.add_argument("--section", type=str, default="", help="配合 --file 按关键词点读二级章节正文 (逗号分隔可多选)")
    parser.add_argument("--list-sections", action="store_true", help="配合 --file 仅列出该文件的二级章节目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出文件清单")
    parser.add_argument("--render", action="store_true", help="渲染输出裁剪后的 Modify 最小规则包")
    parser.add_argument("--absolute", action="store_true", help="输出绝对文件路径")
    parser.add_argument("--validate", action="store_true", help="自检所有映射文件的物理存在性")
    parser.add_argument("--audit-checks", type=str, default="", help="Audit 检查项 ID 列表，逗号分隔")
    parser.add_argument("--audit-assets", type=str, default="", help="Audit 采集资产类型列表，逗号分隔")

    args = parser.parse_args()

    if args.validate:
        sys.exit(0 if validate_all_mappings() else 1)

    skill_root = get_skill_root()
    if args.file:
        target_fp = args.file if os.path.isabs(args.file) else os.path.join(skill_root, args.file)
        if not os.path.isfile(target_fp):
            print(f"❌ 参考文件不存在：{args.file}", file=sys.stderr)
            sys.exit(1)
        with open(target_fp, "r", encoding="utf-8") as f:
            content = f.read()
        print(extract_markdown_section_by_keyword(content, section_query=args.section, list_only=args.list_sections), end="")
        sys.exit(0)

    if args.render and args.json:
        parser.error("--render 与 --json 不能同时使用")
    if args.render and args.mode != "modify":
        parser.error("--render 仅支持 --mode modify")
    if (args.audit_checks or args.audit_assets) and args.mode != "audit":
        parser.error("--audit-checks 和 --audit-assets 仅支持 --mode audit")

    raw_assets = ",".join(x for x in (args.assets, args.domains) if x)
    assets = [a.strip() for a in raw_assets.split(",") if a.strip()]
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    audit_checks = [c.strip() for c in args.audit_checks.split(",") if c.strip()]
    audit_assets = [a.strip() for a in args.audit_assets.split(",") if a.strip()]

    unknown_scenarios = sorted({s.lower() for s in scenarios} - MODIFY_COMPLEX_SCENARIOS)
    if args.mode == "modify" and unknown_scenarios:
        parser.error(
            "未知 Modify 复杂场景：" + ", ".join(unknown_scenarios)
            + "；可选值：" + ", ".join(sorted(MODIFY_COMPLEX_SCENARIOS))
        )

    resolved_rel_paths = resolve_files(args.mode, assets, scenarios=scenarios, step=args.step)
    final_paths = [os.path.join(skill_root, p) for p in resolved_rel_paths] if args.absolute else resolved_rel_paths

    if args.render:
        print(render_modify_policy_bundle(resolved_rel_paths, assets, scenarios, absolute=args.absolute), end="")
    elif args.mode == "audit" and (audit_checks or audit_assets):
        print(render_audit_context(resolved_rel_paths, audit_checks, audit_assets), end="")
    elif args.json:
        references = build_reference_records(resolved_rel_paths, assets, scenarios, absolute=args.absolute)
        output_data = {
            "mode": args.mode,
            "guideIncluded": "modify/modify_guide.md" in resolved_rel_paths if args.mode == "modify" else None,
            "assets": assets,
            "scenarios": scenarios,
            "step": args.step if args.step else None,
            "resolvedCount": len(final_paths),
            "files": final_paths,
            "references": references,
        }
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        for p in final_paths:
            print(p)


if __name__ == "__main__":
    main()
