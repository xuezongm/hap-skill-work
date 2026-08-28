#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_context.py
HAP App Builder 渐进加载上下文动态解析引擎。

根据工作流模式 (mode)、资产类型 (assets)、复杂场景 (scenarios) 或搭建步骤 (step)，
计算当前任务所需加载的最小参考文件集合，避免无关文档进入上下文。
"""

import argparse
import json
import os
import re
import sys
from typing import List, Dict, Set


MODIFY_GUIDE_SECTION_MAPPING: Dict[str, str] = {
    "app": "第 2 章 应用信息与导航",
    "navigation": "第 2 章 应用信息与导航",
    "worksheet": "第 3 章 工作表与字段",
    "field": "第 3 章 工作表与字段",
    "relation": "第 3 章 工作表与字段",
    "layout": "第 3 章 工作表与字段",
    "view": "第 4 章 视图与自定义动作",
    "action": "第 4 章 视图与自定义动作",
    "rule": "第 5 章 业务规则",
    "business_rule": "第 5 章 业务规则",
    "print_template": "第 6 章 打印模板",
    "template": "第 6 章 打印模板",
    "page": "第 7 章 自定义页面与图表",
    "chart": "第 7 章 自定义页面与图表",
    "workflow": "第 8 章 工作流",
    "workflow_design": "第 8 章 工作流",
    "role": "第 9 章 角色与权限",
    "permission": "第 9 章 角色与权限",
    "record": "第 10 章 数据修改、结构重构与迁移",
    "data": "第 10 章 数据修改、结构重构与迁移",
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

MODIFY_GUIDE_SECTION_ORDER: List[str] = [
    "第 1 章 使用方法",
    "第 2 章 应用信息与导航",
    "第 3 章 工作表与字段",
    "第 4 章 视图与自定义动作",
    "第 5 章 业务规则",
    "第 6 章 打印模板",
    "第 7 章 自定义页面与图表",
    "第 8 章 工作流",
    "第 9 章 角色与权限",
    "第 10 章 数据修改、结构重构与迁移",
]

# Audit 检查项前缀到维度的映射
AUDIT_CHECK_PREFIXES: Dict[str, str] = {
    "STR": "structure",
    "BIZ": "business",
    "UX": "user_experience",
    "PRF": "performance",
    "SEC": "security",
}

# Audit 维度到 audit-checks.md 中章节标题的映射
AUDIT_DIMENSION_SECTIONS: Dict[str, str] = {
    "structure": "三、结构健康度",
    "business": "四、业务完整度",
    "user_experience": "五、用户体验",
    "performance": "六、性能与容量",
    "security": "七、安全与维护",
}

# collection-guide.md 中资产类型到章节标题的映射
COLLECTION_ASSET_SECTIONS: Dict[str, str] = {
    "app": "应用与导航",
    "navigation": "应用与导航",
    "worksheet": "工作表与字段",
    "field": "工作表与字段",
    "relation": "工作表与字段",
    "layout": "工作表与字段",
    "view": "视图",
    "action": "自定义动作",
    "rule": "业务规则",
    "business_rule": "业务规则",
    "print_template": "打印模板",
    "template": "打印模板",
    "workflow": "工作流",
    "role": "角色与权限",
    "permission": "角色与权限",
    "page": "自定义页面与图表",
    "chart": "自定义页面与图表",
    "record": "业务数据",
    "data": "业务数据",
}


def get_skill_root() -> str:
    """获取 Skill 根目录绝对路径"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_files(
    mode: str,
    assets: List[str],
    scenarios: List[str] = None,
    step: str = None,
) -> List[str]:
    """解析出需要加载的文件相对路径列表"""
    files: Set[str] = set()
    scenarios = scenarios or []

    # 1. 基础工作流文件
    if mode == "plan":
        files.add("workflows/plan.md")
        files.add("plan/1a_plan_overview.md")
        files.add("plan/1b_plan_schema.md")
        files.add("references/guide-design.md")
        files.add("references/guide-workflows.md")
        files.add("references/spec-app-styles.md")
    elif mode == "build":
        files.add("workflows/build.md")
        files.add("build/CONTEXT.md")
        files.add("build/PROGRESS.md")
        files.add("build/OUTPUT_CONTRACT.md")
    elif mode == "modify":
        # 普通修改只加载主流程与目标对象 Guide；高风险规则由场景触发。
        files.add("workflows/modify.md")
        files.add("modify/modify_guide.md")
    elif mode == "audit":
        files.add("workflows/audit.md")
        files.add("audit/audit-checks.md")
        files.add("audit/collection-guide.md")

    # 2. 根据 Build Step 加载专属步骤 SOP 与对应的 references 规格
    step_mapping: Dict[str, List[str]] = {
        "1": ["build/steps/1_create_app.md", "references/spec-app-styles.md"],
        "1b": ["build/steps/1b_update_app_desc.md"],
        "2a": ["build/steps/2a_create_worksheets.md", "references/spec-worksheets.md"],
        "2b": ["build/steps/2b_create_relations.md", "references/spec-worksheets.md"],
        "3": [
            "build/steps/3_create_actions_views_rules.md",
            "references/spec-actions-views.md",
            "references/spec-business-rules.md"
        ],
        "4": ["build/steps/4_create_chatbots.md", "references/spec-chatbots.md"],
        "5": [
            "build/steps/5_create_sample_data.md",
            "references/spec-sample-data.md",
            "references/resource-sample-images.md"
        ],
        "6": ["build/steps/6_create_pages.md", "references/spec-pages-charts.md"],
        "7": ["build/steps/7_sort_app_items.md", "references/guide-design.md"],
        "8": ["build/steps/8_create_roles.md", "references/spec-roles-permissions.md"],
        "9": ["build/steps/9_design_workflows.md", "references/guide-workflows.md"],
        "10": ["build/steps/10_create_workflows.md", "references/spec-workflows.md"],
        "11": ["build/steps/11_create_action_workflows.md", "references/spec-workflows.md"],
    }

    if step and step in step_mapping:
        for f in step_mapping[step]:
            files.add(f)

    # 3. 根据目标资产 (assets) 加载对应的 references 规格文件 (主要用于 Modify / Audit)
    asset_mapping: Dict[str, List[str]] = {
        "app": [],
        "navigation": ["references/guide-design.md"],
        "worksheet": ["references/spec-worksheets.md"],
        "field": ["references/spec-worksheets.md"],
        "relation": ["references/spec-worksheets.md"],
        "layout": ["references/spec-worksheets.md"],
        "sample_data": ["references/spec-sample-data.md"],
        "rule": ["references/spec-business-rules.md"],
        "business_rule": ["references/spec-business-rules.md"],
        "print_template": ["references/spec-print-templates.md"],
        "template": ["references/spec-print-templates.md"],
        "view": ["references/spec-actions-views.md"],
        "action": ["references/spec-actions-views.md"],
        "chatbot": ["references/spec-chatbots.md"],
        "page": ["references/spec-pages-charts.md"],
        "chart": ["references/spec-pages-charts.md"],
        "role": ["references/spec-roles-permissions.md"],
        "permission": ["references/spec-roles-permissions.md"],
        "record": [],
        "data": [],
        "workflow": ["references/spec-workflows.md"],
        "workflow_design": ["references/guide-workflows.md"],
        "custom_field": ["references/spec-custom-fields.md"],
        "free_field": ["references/spec-custom-fields.md"],
        "index": ["references/spec-worksheet-indexes.md"],
        "worksheet_index": ["references/spec-worksheet-indexes.md"],
        "icon": ["references/spec-app-styles.md"],
        "style": ["references/spec-app-styles.md"],
        "design": ["references/guide-design.md"],
    }

    for a in assets:
        key = a.strip().lower()
        if key in asset_mapping:
            for f in asset_mapping[key]:
                files.add(f)

    # 复杂执行边界只属于 Modify，由操作场景触发，不与目标资产混用。
    normalized_scenarios = {s.strip().lower() for s in scenarios}
    if mode == "modify" and normalized_scenarios.intersection(MODIFY_COMPLEX_SCENARIOS):
        files.add("modify/safety-rules.md")
        files.add("modify/execution-boundaries.md")

    # 保持确定的顺序
    return sorted(list(files))


def validate_all_mappings() -> bool:
    """自检所有模式、步骤、资产与复杂场景映射的文件物理存在性"""
    skill_root = get_skill_root()
    all_files: Set[str] = set()
    for m in ["plan", "build", "audit"]:
        all_files.update(resolve_files(m, []))
    all_files.update(resolve_files("modify", []))
    for s in ["1", "1b", "2a", "2b", "3", "4", "5", "6", "7", "8", "9", "10", "11"]:
        all_files.update(resolve_files("build", [], step=s))
    all_assets = [
        "app", "navigation", "worksheet", "field", "relation", "layout", "sample_data",
        "rule", "business_rule", "print_template", "template", "view", "action", "chatbot",
        "page", "chart", "role", "permission", "record", "data", "workflow",
        "workflow_design", "custom_field", "free_field", "index", "worksheet_index", "icon", "style", "design"
    ]
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
    """返回本次任务实际需要阅读的章节或检索方式。"""
    if rel_path != "modify/modify_guide.md":
        if rel_path.startswith("references/"):
            return ["按当前操作和参数检索"]
        return ["全文"]

    sections = {"第 1 章 使用方法"}
    for asset in assets:
        section = MODIFY_GUIDE_SECTION_MAPPING.get(asset.strip().lower())
        if section:
            sections.add(section)
    if {s.strip().lower() for s in scenarios}.intersection(MODIFY_DATA_SCENARIOS):
        sections.add("第 10 章 数据修改、结构重构与迁移")
    return [section for section in MODIFY_GUIDE_SECTION_ORDER if section in sections]


def reference_purpose(rel_path: str) -> str:
    """说明参考文件对当前任务的职责。"""
    if rel_path == "workflows/modify.md":
        return "Modify 执行流程与阶段门禁"
    if rel_path == "modify/modify_guide.md":
        return "对象关联影响、修改与验证规则"
    if rel_path == "modify/safety-rules.md":
        return "复杂或高风险修改的安全底线"
    if rel_path == "modify/execution-boundaries.md":
        return "Modify 复杂操作执行、停止与人工协同边界"
    if rel_path == "audit/audit-checks.md":
        return "Audit 检查项、证据要求与评分规则"
    if rel_path == "audit/collection-guide.md":
        return "Audit 证据范围、接口选择与停止条件"
    if rel_path.startswith("references/spec-"):
        return "目标资产底层参数规范"
    if rel_path.startswith("references/guide-"):
        return "目标资产业务设计指导"
    return "任务所需参考资料"


def build_reference_records(
    resolved_rel_paths: List[str],
    assets: List[str],
    scenarios: List[str],
    absolute: bool = False,
) -> List[Dict[str, object]]:
    """生成轻量参考清单，不计算内容哈希。"""
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
    """从 Guide 中提取指定的二级编号章节。"""
    lines = content.splitlines(keepends=True)
    heading_indexes = []
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+(目录|([0-9]+)\.)", line)
        if match:
            key = "目录" if match.group(1) == "目录" else f"第 {match.group(2)} 章"
            heading_indexes.append((index, key))

    requested_keys = set()
    for section in requested_sections:
        chapter_match = re.match(r"第\s+([0-9]+)\s+章", section)
        if chapter_match:
            requested_keys.add(f"第 {chapter_match.group(1)} 章")

    selected = []
    for position, (start, key) in enumerate(heading_indexes):
        if key not in requested_keys:
            continue
        end = heading_indexes[position + 1][0] if position + 1 < len(heading_indexes) else len(lines)
        selected.extend(lines[start:end])
    return "".join(selected).rstrip()


def extract_audit_checks(content: str, check_ids: List[str]) -> str:
    """从 audit-checks.md 提取指定 CHK-* 行所在维度的表头和匹配行。

    返回包含通用章节（执行与证据契约、评分算法）和匹配维度表格的精简内容。
    """
    lines = content.splitlines(keepends=True)

    # 解析需要的维度
    needed_dimensions: Set[str] = set()
    for cid in check_ids:
        match = re.match(r"CHK-([A-Z]+)-\d+", cid)
        if match and match.group(1) in AUDIT_CHECK_PREFIXES:
            needed_dimensions.add(AUDIT_CHECK_PREFIXES[match.group(1)])

    # 定位各二级章节
    section_spans = []
    for index, line in enumerate(lines):
        if re.match(r"^## ", line):
            section_spans.append((index, line.strip()))

    # 始终包含一、二章（契约和算法）；按需包含维度章节
    selected = []
    check_id_set = set(check_ids)
    for position, (start, title) in enumerate(section_spans):
        end = section_spans[position + 1][0] if position + 1 < len(section_spans) else len(lines)
        # 一、二章始终包含
        if "执行与证据契约" in title or "评分与评级算法" in title:
            selected.extend(lines[start:end])
            continue
        # 检查维度章节是否匹配
        matched_dimension = False
        for dim, section_keyword in AUDIT_DIMENSION_SECTIONS.items():
            if section_keyword in title and dim in needed_dimensions:
                matched_dimension = True
                break
        if not matched_dimension:
            continue
        # 提取表头和匹配行
        section_lines = lines[start:end]
        header_added = False
        for sline in section_lines:
            # 章节标题始终保留
            if sline.startswith("## ") or sline.startswith("| 检查项") or sline.startswith("|---"):
                selected.append(sline)
                header_added = True
            elif sline.startswith("| `CHK-"):
                # 检查行是否匹配请求的 check_ids
                row_match = re.match(r"^\| `(CHK-[A-Z]+-\d+)`", sline)
                if row_match and row_match.group(1) in check_id_set:
                    selected.append(sline)
            elif not header_added:
                # 章节标题之前的空行
                selected.append(sline)

    return "".join(selected).rstrip()


def extract_collection_sections(content: str, asset_types: List[str]) -> str:
    """从 collection-guide.md 提取指定资产类型对应的子章节。

    始终包含一～三章（核心原则、三类证据、按模式采集）和五～七章（预算、观察、并行）。
    四章按资产类型选择性提取子章节。
    """
    lines = content.splitlines(keepends=True)

    # 需要的子章节标题
    needed_subsections: Set[str] = set()
    for at in asset_types:
        key = at.strip().lower()
        if key in COLLECTION_ASSET_SECTIONS:
            needed_subsections.add(COLLECTION_ASSET_SECTIONS[key])

    # 定位二级章节
    h2_spans = []
    for index, line in enumerate(lines):
        if re.match(r"^## ", line):
            h2_spans.append((index, line.strip()))

    selected = []
    for position, (start, title) in enumerate(h2_spans):
        end = h2_spans[position + 1][0] if position + 1 < len(h2_spans) else len(lines)

        # 四章需要选择性提取
        if "各类对象的读取规则" in title:
            section_lines = lines[start:end]
            # 定位三级子章节
            h3_spans_local = []
            for local_idx, sline in enumerate(section_lines):
                if re.match(r"^### ", sline):
                    h3_spans_local.append((local_idx, sline.strip()))

            # 始终保留章节标题
            selected.append(section_lines[0])
            if len(section_lines) > 1 and not section_lines[1].startswith("###"):
                selected.append(section_lines[1])

            for sub_pos, (sub_start, sub_title) in enumerate(h3_spans_local):
                sub_end = h3_spans_local[sub_pos + 1][0] if sub_pos + 1 < len(h3_spans_local) else len(section_lines)
                # 检查子章节标题是否匹配需要的资产类型
                for needed in needed_subsections:
                    if needed in sub_title:
                        selected.extend(section_lines[sub_start:sub_end])
                        break
        else:
            # 其他章节全部保留
            selected.extend(lines[start:end])

    # 文件标题（#开头的行在第一个 ## 之前）
    if h2_spans:
        header = lines[:h2_spans[0][0]]
        return "".join(header + selected).rstrip()
    return "".join(selected).rstrip()


def render_modify_policy_bundle(
    resolved_rel_paths: List[str],
    assets: List[str],
    scenarios: List[str],
    absolute: bool = False,
) -> str:
    """输出 Modify 所需的最小 Guide 正文和按需参考清单。"""
    skill_root = get_skill_root()
    references = build_reference_records(resolved_rel_paths, assets, scenarios, absolute=absolute)
    metadata = {
        "mode": "modify",
        "assets": assets,
        "scenarios": scenarios,
        "references": references,
        "note": "Guide 章节已渲染；references/spec-* 只需检索当前操作和参数，不要求阅读全文。",
    }
    parts = [
        "# Modify 最小上下文",
        "",
        "## 按需参考清单",
        "",
        "```json",
        json.dumps(metadata, ensure_ascii=False, indent=2),
        "```",
    ]

    policy_order = [
        "modify/modify_guide.md",
        "modify/safety-rules.md",
        "modify/execution-boundaries.md",
    ]
    for rel_path in policy_order:
        if rel_path not in resolved_rel_paths:
            continue
        with open(os.path.join(skill_root, rel_path), "r", encoding="utf-8") as file_obj:
            content = file_obj.read()
        if rel_path == "modify/modify_guide.md":
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
    absolute: bool = False,
) -> str:
    """输出 Audit 所需的最小检查项和采集章节。"""
    skill_root = get_skill_root()
    parts = [
        "# Audit 最小上下文",
        "",
    ]

    # audit-checks.md 按需提取
    checks_path = os.path.join(skill_root, "audit", "audit-checks.md")
    if os.path.exists(checks_path):
        with open(checks_path, "r", encoding="utf-8") as f:
            checks_content = f.read()
        if audit_checks:
            extracted = extract_audit_checks(checks_content, audit_checks)
            parts.extend([
                "## 已加载：audit/audit-checks.md（按需提取）",
                "",
                extracted.rstrip(),
                "",
            ])
        else:
            parts.extend([
                "## 已加载：audit/audit-checks.md（全文）",
                "",
                checks_content.rstrip(),
                "",
            ])

    # collection-guide.md 按需提取
    guide_path = os.path.join(skill_root, "audit", "collection-guide.md")
    if os.path.exists(guide_path):
        with open(guide_path, "r", encoding="utf-8") as f:
            guide_content = f.read()
        if audit_assets:
            extracted = extract_collection_sections(guide_content, audit_assets)
            parts.extend([
                "## 已加载：audit/collection-guide.md（按需提取）",
                "",
                extracted.rstrip(),
                "",
            ])
        else:
            parts.extend([
                "## 已加载：audit/collection-guide.md（全文）",
                "",
                guide_content.rstrip(),
                "",
            ])

    # audit.md 始终全文
    audit_path = os.path.join(skill_root, "workflows", "audit.md")
    if "workflows/audit.md" in resolved_rel_paths and os.path.exists(audit_path):
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_content = f.read()
        parts.extend([
            "## 已加载：workflows/audit.md（全文）",
            "",
            audit_content.rstrip(),
            "",
        ])

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
    parser = argparse.ArgumentParser(description="HAP App Builder 上下文动态解析器")
    parser.add_argument("--mode", choices=["plan", "build", "modify", "audit"], default="modify", help="工作流模式")
    parser.add_argument("--assets", type=str, default="", help="资产类型列表，逗号分隔 (如 field,relation,view)")
    parser.add_argument("--scenarios", type=str, default="", help="复杂场景列表，逗号分隔 (如 physical_delete,cross_table_migration)")
    parser.add_argument("--step", type=str, default="", help="Build 步骤编号 (如 2a, 3, 10)")
    parser.add_argument("--json", action="store_true", help="是否输出为 JSON 格式")
    parser.add_argument("--render", action="store_true", help="输出 Modify 前置规则正文包与参考清单")
    parser.add_argument("--absolute", action="store_true", help="是否输出绝对文件路径")
    parser.add_argument("--validate", action="store_true", help="校验所有映射文件的物理存在性")
    parser.add_argument("--audit-checks", type=str, default="", help="Audit 检查项 ID 列表，逗号分隔 (如 CHK-BIZ-006,CHK-BIZ-007)")
    parser.add_argument("--audit-assets", type=str, default="", help="Audit 采集资产类型列表，逗号分隔 (如 worksheet,workflow)")

    args = parser.parse_args()

    if args.render and args.json:
        parser.error("--render 与 --json 不能同时使用")
    if args.render and args.mode != "modify":
        parser.error("--render 仅支持 --mode modify")
    if (args.audit_checks or args.audit_assets) and args.mode != "audit":
        parser.error("--audit-checks 和 --audit-assets 仅支持 --mode audit")

    if args.validate:
        success = validate_all_mappings()
        sys.exit(0 if success else 1)

    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    audit_checks = [c.strip() for c in args.audit_checks.split(",") if c.strip()]
    audit_assets = [a.strip() for a in args.audit_assets.split(",") if a.strip()]

    unknown_scenarios = sorted({s.lower() for s in scenarios} - MODIFY_COMPLEX_SCENARIOS)
    if args.mode == "modify" and unknown_scenarios:
        parser.error(
            "未知 Modify 复杂场景：" + ", ".join(unknown_scenarios)
            + "；可选值：" + ", ".join(sorted(MODIFY_COMPLEX_SCENARIOS))
        )
    resolved_rel_paths = resolve_files(
        args.mode,
        assets,
        scenarios=scenarios,
        step=args.step,
    )

    skill_root = get_skill_root()
    if args.absolute:
        final_paths = [os.path.join(skill_root, p) for p in resolved_rel_paths]
    else:
        final_paths = resolved_rel_paths

    if args.render:
        print(render_modify_policy_bundle(
            resolved_rel_paths,
            assets,
            scenarios,
            absolute=args.absolute,
        ), end="")
    elif args.mode == "audit" and (audit_checks or audit_assets):
        # Audit 按需渲染模式
        print(render_audit_context(
            resolved_rel_paths,
            audit_checks,
            audit_assets,
            absolute=args.absolute,
        ), end="")
    elif args.json:
        references = build_reference_records(
            resolved_rel_paths,
            assets,
            scenarios,
            absolute=args.absolute,
        )
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
