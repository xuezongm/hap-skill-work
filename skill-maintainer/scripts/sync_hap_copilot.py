#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_hap_copilot.py
将 MDAgentService/assets/agents/prod 中的权威领域 Skill 镜像同步至 hap-app-copilot/references/，
并核查 build-app / modify-app YAML 与本地 SOP 的对齐状态。

用法：
  python3 sync_hap_copilot.py --sync-specs [--clean-legacy]
  python3 sync_hap_copilot.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SHARED_SKILL_NAMES: List[str] = [
    # 通用设计指南与图标/数据规范 (5)
    "hap-app-design-guide",
    "hap-workflow-design-guide",
    "hap-chart-design-guide",
    "hap-icon-palette",
    "hap-sample-data-spec",
    # 领域对象规范 (14)；打印文件由本地 step 承接，不镜像服务端文件协议。
    "hap-domain-app-spec",
    "hap-domain-worksheet-spec",
    "hap-domain-custom-field-spec",
    "hap-domain-worksheet-index-spec",
    "hap-domain-business-rule-spec",
    "hap-domain-view-spec",
    "hap-domain-custom-action-spec",
    "hap-domain-custom-page-spec",
    "hap-domain-worksheet-chart-spec",
    "hap-domain-chatbot-spec",
    "hap-domain-external-portal-spec",
    "hap-domain-role-spec",
    "hap-domain-workflow-spec",
    "hap-domain-record-data-spec",
]

LEGACY_REFERENCE_FILES: List[str] = [
    "guide-design.md",
    "guide-workflows.md",
    "resource-portal-assets.md",
    "resource-sample-images.md",
    "spec-actions-views.md",
    "spec-app-styles.md",
    "spec-business-rules.md",
    "spec-chatbots.md",
    "spec-custom-fields.md",
    "spec-pages-charts.md",
    "spec-print-templates.md",
    "spec-roles-permissions.md",
    "spec-sample-data.md",
    "spec-workflows.md",
    "spec-worksheet-indexes.md",
    "spec-worksheets.md",
]

# 本地 build/steps/*.md 与线上 build-app/*.yaml 的权威对应关系
BUILD_STEP_YAML_MAP: Dict[str, List[str]] = {
    "build/steps/1_create_app.md": [
        "build-app/create-app-sub-agent.yaml",
        "build-app/custom-page-create-sub-agent.yaml",
    ],
    "build/steps/1b_update_app_desc.md": ["build-app/update-app-desc-sub-agent.yaml"],
    "build/steps/2a_create_worksheets.md": ["build-app/worksheet-build-sub-agent.yaml"],
    "build/steps/2b_create_relations.md": ["build-app/worksheet-relation-build-sub-agent.yaml"],
    "build/steps/3_create_actions_views_rules.md": [
        "build-app/view-build-sub-agent.yaml",
        "build-app/business-rule-build-sub-agent.yaml",
    ],
    "build/steps/4_create_chatbots.md": [
        "build-app/chatbot-create-sub-agent.yaml",
        "build-app/chatbot-config-sub-agent.yaml",
    ],
    "build/steps/5_create_sample_data.md": ["build-app/sample-data-sub-agent.yaml"],
    "build/steps/6_create_pages.md": ["build-app/custom-page-config-sub-agent.yaml"],
    "build/steps/7_sort_app_items.md": ["build-app/sort-app-items-sub-agent.yaml"],
    "build/steps/8_create_roles.md": ["build-app/roles-build-sub-agent.yaml"],
    "build/steps/10_create_workflows.md": [
        "build-app/workflow-design-sub-agent.yaml",
        "build-app/workflow-build-sub-agent.yaml",
    ],
    "build/steps/11_create_action_workflows.md": [
        "build-app/custom-action-design-sub-agent.yaml",
        "build-app/custom-action-workflow-sub-agent.yaml",
    ],
}

# modify/modify_guide.md 12 领域与线上 modify-app/*.yaml 的权威对应关系
MODIFY_YAML_LIST: List[str] = [
    "modify-app/app-navigation-revision-sub-agent.yaml",
    "modify-app/worksheet-revision-agent.yaml",
    "modify-app/view-action-revision-sub-agent.yaml",
    "modify-app/role-permission-revision-sub-agent.yaml",
    "modify-app/custom-page-revision-sub-agent.yaml",
    "modify-app/worksheet-chart-revision-sub-agent.yaml",
    "modify-app/chatbot-revision-sub-agent.yaml",
    "modify-app/print-template-revision-sub-agent.yaml",
    "modify-app/public-form-revision-sub-agent.yaml",
    "modify-app/external-portal-revision-sub-agent.yaml",
    "modify-app/workflow-revision-sub-agent.yaml",
    "modify-app/record-data-revision-sub-agent.yaml",
]

# 本地适配规程仅检查文件存在性与来源标记，不覆盖正文或比较服务端专用协议。
LOCAL_STEP_SOURCE_MAP: Dict[str, List[str]] = {
    "modify/print-template-file.md": [
        "skills/hap-domain-print-template-spec/SKILL.md",
        "modify-app/print-template-revision-sub-agent.yaml",
    ],
    "workflows/data.md": [
        "app-query-agent.yaml",
        "skills/hap-data-agent-rules/SKILL.md",
    ],
}


def default_paths() -> Tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent
    skills_repo = script_dir.parent.parent
    copilot_dir = skills_repo / "hap-mcp-app-builder"
    if not copilot_dir.exists() and (skills_repo / "hap-app-copilot").exists():
        copilot_dir = skills_repo / "hap-app-copilot"
    ai_work_dir = skills_repo.parent.parent
    prod_dir = ai_work_dir / "Mingo" / "MDAgentService" / "assets" / "agents" / "prod"
    return copilot_dir, prod_dir


def strip_frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5 :].lstrip("\n")
    # 将跨文件纯相对引用如 skills/hap-xxx 规范化为反引号代码标识或 references/hap-xxx.md，防止断链误报
    text = re.sub(
        r"(?<!`)(?:skills/)(hap-[a-z0-9-]+)(?:/SKILL\.md)?(?!`)",
        r"`references/\1.md`",
        text,
    )
    return text.rstrip() + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def get_git_head(repo_path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def sync_specs(copilot_dir: Path, prod_dir: Path, clean_legacy: bool = False) -> int:
    refs_dir = copilot_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    if clean_legacy:
        for legacy in LEGACY_REFERENCE_FILES:
            lp = refs_dir / legacy
            if lp.exists():
                lp.unlink()

    synced = 0
    missing = []
    for name in SHARED_SKILL_NAMES:
        src = prod_dir / "skills" / name / "SKILL.md"
        if not src.is_file():
            missing.append(str(src))
            continue
        cleaned = strip_frontmatter(src.read_text(encoding="utf-8"))
        dst = refs_dir / f"{name}.md"
        dst.write_text(cleaned, encoding="utf-8")
        synced += 1

    if missing:
        print(f"❌ 缺失线上源 Skill 文件 ({len(missing)} 个):", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    head = get_git_head(prod_dir)
    print(f"✅ 已从 MDAgentService (HEAD={head}) 镜像同步 {synced} 个共享规格至 {refs_dir}")
    return 0


def check_alignment(copilot_dir: Path, prod_dir: Path, as_json: bool = False) -> int:
    refs_dir = copilot_dir / "references"
    drifted_specs = []
    missing_specs = []

    for name in SHARED_SKILL_NAMES:
        src = prod_dir / "skills" / name / "SKILL.md"
        dst = refs_dir / f"{name}.md"
        if not src.is_file() or not dst.is_file():
            missing_specs.append(name)
            continue
        expected = strip_frontmatter(src.read_text(encoding="utf-8"))
        actual = dst.read_text(encoding="utf-8")
        if expected != actual:
            drifted_specs.append({
                "name": name,
                "prodHash": sha256_text(expected),
                "localHash": sha256_text(actual),
            })

    extra_refs = sorted(
        p.name
        for p in refs_dir.glob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and p.stem not in SHARED_SKILL_NAMES
    )

    missing_build_anchors = []
    for step_rel, yaml_rels in BUILD_STEP_YAML_MAP.items():
        step_fp = copilot_dir / step_rel
        if not step_fp.is_file():
            missing_build_anchors.append(f"{step_rel} (文件缺失)")
            continue
        step_txt = step_fp.read_text(encoding="utf-8")
        for y_rel in yaml_rels:
            if y_rel not in step_txt:
                missing_build_anchors.append(f"{step_rel} 缺少源标记 {y_rel}")

    modify_guide_fp = copilot_dir / "modify" / "modify_guide.md"
    missing_modify_anchors = []
    if not modify_guide_fp.is_file():
        missing_modify_anchors.append("modify/modify_guide.md (文件缺失)")
    else:
        mg_txt = modify_guide_fp.read_text(encoding="utf-8")
        for y_rel in MODIFY_YAML_LIST:
            if y_rel not in mg_txt:
                missing_modify_anchors.append(f"modify/modify_guide.md 缺少源标记 {y_rel}")

    local_step_issues = []
    for step_rel, source_rels in LOCAL_STEP_SOURCE_MAP.items():
        step_fp = copilot_dir / step_rel
        if not step_fp.is_file():
            local_step_issues.append(f"{step_rel} (文件缺失)")
            continue
        step_txt = step_fp.read_text(encoding="utf-8")
        for source_rel in source_rels:
            if not (prod_dir / source_rel).is_file():
                local_step_issues.append(f"{step_rel} 来源不存在：{source_rel}")
            if source_rel not in step_txt:
                local_step_issues.append(f"{step_rel} 缺少源标记 {source_rel}")

    ok = not (missing_specs or drifted_specs or extra_refs or missing_build_anchors or missing_modify_anchors or local_step_issues)
    report = {
        "ok": ok,
        "prodGitHead": get_git_head(prod_dir),
        "sharedSpecsCount": len(SHARED_SKILL_NAMES),
        "missingSpecs": missing_specs,
        "driftedSpecs": drifted_specs,
        "extraReferenceFiles": extra_refs,
        "missingBuildAnchors": missing_build_anchors,
        "missingModifyAnchors": missing_modify_anchors,
        "localStepIssues": local_step_issues,
    }

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"=== hap-app-copilot <-> MDAgentService (HEAD={report['prodGitHead']}) 对齐检查 ===")
        print(f"共享规格 ({len(SHARED_SKILL_NAMES)}): 缺失 {len(missing_specs)}，漂移 {len(drifted_specs)}，多余旧文件 {len(extra_refs)}")
        print(f"Build SOP 源锚点: 缺失 {len(missing_build_anchors)}")
        print(f"Modify Guide 源锚点: 缺失 {len(missing_modify_anchors)}")
        print(f"本地适配步骤: 来源问题 {len(local_step_issues)}")
        for item in missing_specs:
            print(f"  [缺失规格] {item}")
        for item in drifted_specs:
            print(f"  [规格漂移] {item['name']} (prod={item['prodHash']}, local={item['localHash']})")
        for item in extra_refs:
            print(f"  [多余文件] references/{item}")
        for item in missing_build_anchors:
            print(f"  [Build锚点] {item}")
        for item in missing_modify_anchors:
            print(f"  [Modify锚点] {item}")
        for item in local_step_issues:
            print(f"  [本地步骤] {item}")
        if ok:
            print("✅ 共享规格正文、来源标记与本地步骤来源检查通过（不代表行为完全一致）。")

    return 0 if ok else 1


def main() -> int:
    default_copilot, default_prod = default_paths()
    parser = argparse.ArgumentParser(description="hap-app-copilot 与 MDAgentService 同步及对齐校验器")
    parser.add_argument("--copilot-dir", type=Path, default=default_copilot, help="hap-app-copilot 根目录")
    parser.add_argument("--prod-dir", type=Path, default=default_prod, help="MDAgentService assets/agents/prod 目录")
    parser.add_argument("--sync-specs", action="store_true", help=f"将上游 {len(SHARED_SKILL_NAMES)} 个共享 Skill 镜像写入 references/，不覆盖本地适配步骤")
    parser.add_argument("--clean-legacy", action="store_true", help="同步时清理旧版 spec-*/guide-*/resource-* 文件")
    parser.add_argument("--check", action="store_true", help="检查双端规格与同源锚点一致性")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出检查报告")
    args = parser.parse_args()

    if not args.sync_specs and not args.check:
        parser.error("请至少指定 --sync-specs 或 --check")

    code = 0
    if args.sync_specs:
        code = sync_specs(args.copilot_dir.resolve(), args.prod_dir.resolve(), clean_legacy=args.clean_legacy)
        if code != 0:
            return code
    if args.check:
        code = check_alignment(args.copilot_dir.resolve(), args.prod_dir.resolve(), as_json=args.json)
    return code


if __name__ == "__main__":
    sys.exit(main())
