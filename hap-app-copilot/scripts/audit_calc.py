#!/usr/bin/env python3
"""校验 Audit 逐项结果，并按 audit-checks.md 计算覆盖率和分数。"""

import json
import re
import sys
from collections import Counter
from pathlib import Path


WEIGHTS = {
    "structure": 25,
    "business": 25,
    "user_experience": 20,
    "performance": 15,
    "security": 15,
}
PREFIXES = {
    "STR": "structure",
    "BIZ": "business",
    "UX": "user_experience",
    "PRF": "performance",
    "SEC": "security",
}
DEDUCTIONS = {"P0": 10, "P1": 5, "P2": 2}
STATUSES = {"pass", "fail", "not_applicable", "not_evaluated"}
EVIDENCE_MODES = {"compact", "archive"}
ARCHIVE_REASONS = {"user_request", "external_approval", "retention_required"}
ROW = re.compile(
    r"^\| `(?P<id>CHK-(?P<prefix>[A-Z]+)-\d+)` \| "
    r"(?P<rule>.*?) \| .* \| (?P<severity>P[012]) \|$"
)
FINDING_FIELDS = {
    "findingId",
    "assetType",
    "assetId",
    "assetName",
    "actualEvidence",
    "expectedRule",
    "repairBoundary",
}
SOURCE_FIELDS = {"tool", "objectType", "objectId", "format", "capturedAt"}


def load_catalog(path):
    catalog = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if not match:
            continue
        prefix = match.group("prefix")
        if prefix not in PREFIXES:
            raise ValueError(f"未知检查项前缀：{prefix}")
        catalog[match.group("id")] = {
            "dimension": PREFIXES[prefix],
            "severity": match.group("severity"),
            "rule": match.group("rule").strip(),
        }
    if not catalog:
        raise ValueError("audit-checks.md 中未找到检查项")
    return catalog


def require_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")


def validate_sources(sources, evidence_mode, run_dir=None):
    """校验顶层 sources 对象。"""
    if not isinstance(sources, dict) or not sources:
        raise ValueError("sources 必须是非空对象")
    for source_id, source in sources.items():
        label = f"sources.{source_id}"
        if not isinstance(source, dict):
            raise ValueError(f"{label} 必须是对象")
        for field in SOURCE_FIELDS:
            require_text(source.get(field), f"{label}.{field}")
        if evidence_mode == "archive" and "rawPath" in source:
            raw_path = source["rawPath"]
            require_text(raw_path, f"{label}.rawPath")
            if run_dir is not None:
                relative = Path(raw_path)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"{label}.rawPath 必须是相对路径：{raw_path}")
                target = (run_dir / relative).resolve()
                try:
                    target.relative_to(run_dir)
                except ValueError as exc:
                    raise ValueError(f"{label}.rawPath 越界：{raw_path}") from exc
                if not target.exists():
                    raise ValueError(f"{label}.rawPath 文件不存在：{raw_path}")
                if not target.is_file():
                    raise ValueError(f"{label}.rawPath 不是普通文件：{raw_path}")


def validate_facts(check_id, facts, sources):
    """校验检查项的 facts 数组。"""
    if not isinstance(facts, list) or not facts:
        raise ValueError(f"{check_id} 的 facts 必须是非空数组")
    for index, fact in enumerate(facts):
        label = f"{check_id}.facts[{index}]"
        if not isinstance(fact, dict):
            raise ValueError(f"{label} 必须是对象")
        source_id = fact.get("sourceId")
        require_text(source_id, f"{label}.sourceId")
        if source_id not in sources:
            raise ValueError(f"{label}.sourceId 引用了不存在的来源：{source_id}")
        require_text(fact.get("path"), f"{label}.path")
        if "value" not in fact:
            raise ValueError(f"{label} 必须包含 value 字段")


def validate_coverage(check_id, status, coverage):
    """校验检查项的 coverage 对象。"""
    if not isinstance(coverage, dict):
        raise ValueError(f"{check_id} 的 coverage 必须是对象")
    inspected = coverage.get("inspected")
    total = coverage.get("total")
    if not isinstance(inspected, int) or inspected < 0:
        raise ValueError(f"{check_id}.coverage.inspected 必须是非负整数")
    if total is not None:
        if not isinstance(total, int) or total < 0:
            raise ValueError(f"{check_id}.coverage.total 必须是非负整数或 null")
        if inspected > total:
            raise ValueError(f"{check_id}.coverage.inspected ({inspected}) 不得大于 total ({total})")
    if status == "pass":
        if total is None:
            raise ValueError(f"{check_id} 覆盖总量未知时不得判定 pass")
        if inspected != total:
            raise ValueError(f"{check_id} pass 必须覆盖全部必要对象 (inspected={inspected}, total={total})")


def validate_source_ids(label, source_ids, sources, allowed_sources=None):
    """校验 sourceIds 数组引用的有效性。"""
    if not isinstance(source_ids, list) or not source_ids:
        raise ValueError(f"{label} 的 sourceIds 必须是非空数组")
    for sid in source_ids:
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError(f"{label}.sourceIds 包含无效值")
        if sid not in sources:
            raise ValueError(f"{label}.sourceIds 引用了不存在的来源：{sid}")
        if allowed_sources is not None and sid not in allowed_sources:
            raise ValueError(f"{label}.sourceIds 引用了父检查项未使用的来源：{sid}")


def validate_findings(check_id, findings, seen_finding_ids, expected_rule, sources, check_source_ids):
    if not isinstance(findings, list) or not findings:
        raise ValueError(f"{check_id} 为 fail 时必须包含非空 findings 数组")
    for index, finding in enumerate(findings):
        label = f"{check_id}.findings[{index}]"
        if not isinstance(finding, dict):
            raise ValueError(f"{label} 必须是对象")
        for field in FINDING_FIELDS:
            require_text(finding.get(field), f"{label}.{field}")
        if not isinstance(finding.get("requiresExternalApproval"), bool):
            raise ValueError(f"{label}.requiresExternalApproval 必须是布尔值")
        expected_id = f"{check_id}:{finding['assetType']}:{finding['assetId']}"
        if finding["findingId"] != expected_id:
            raise ValueError(f"{label}.findingId 应为 {expected_id}")
        if finding["expectedRule"].strip() != expected_rule:
            raise ValueError(f"{label}.expectedRule 必须逐字复制 audit-checks.md 的检查规则")
        if expected_id in seen_finding_ids:
            raise ValueError(f"findingId 重复：{expected_id}")
        seen_finding_ids.add(expected_id)
        validate_source_ids(label, finding.get("sourceIds"), sources, check_source_ids)


def calculate(data, catalog, run_dir=None):
    mode = data.get("mode")
    if mode not in {"full", "target"}:
        raise ValueError("mode 必须是 full 或 target；快速筛查不运行评分脚本")
    if not isinstance(data.get("repairIntent"), bool):
        raise ValueError("repairIntent 必须是布尔值")

    evidence_mode = data.get("evidenceMode")
    if evidence_mode not in EVIDENCE_MODES:
        raise ValueError(f"evidenceMode 必须是 {' 或 '.join(sorted(EVIDENCE_MODES))}")
    if evidence_mode == "archive":
        archive_reason = data.get("archiveReason")
        if archive_reason not in ARCHIVE_REASONS:
            raise ValueError(f"archiveReason 必须是 {' / '.join(sorted(ARCHIVE_REASONS))}")

    sources = data.get("sources", {})
    validate_sources(sources, evidence_mode, run_dir if evidence_mode == "archive" else None)

    selected = data.get("selectedCheckIds")
    checks = data.get("checks")
    if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
        raise ValueError("selectedCheckIds 必须是字符串数组")
    if not isinstance(checks, list) or any(not isinstance(item, dict) for item in checks):
        raise ValueError("checks 必须是对象数组")
    if len(selected) != len(set(selected)):
        raise ValueError("selectedCheckIds 包含重复项")

    unknown = sorted(set(selected) - set(catalog))
    if unknown:
        raise ValueError("未知检查项：" + ", ".join(unknown))

    results = {}
    seen_finding_ids = set()
    for item in checks:
        check_id = item.get("checkId")
        if check_id in results:
            raise ValueError(f"检查结果重复：{check_id}")
        if check_id not in catalog:
            raise ValueError(f"未知检查结果：{check_id}")
        if item.get("status") not in STATUSES:
            raise ValueError(f"{check_id} 的 status 无效")
        expected_dimension = catalog[check_id]["dimension"]
        if item.get("dimension") != expected_dimension:
            raise ValueError(f"{check_id} 的 dimension 应为 {expected_dimension}")
        status = item["status"]

        # facts 和 coverage 校验
        if status in {"pass", "fail"}:
            validate_facts(check_id, item.get("facts"), sources)
            validate_coverage(check_id, status, item.get("coverage", {}))
        elif status == "not_evaluated":
            # not_evaluated 也可能有部分 facts 和 coverage
            if "facts" in item and item["facts"]:
                validate_facts(check_id, item["facts"], sources)
            if "coverage" in item:
                validate_coverage(check_id, status, item["coverage"])

        # 收集本检查项使用的 sourceIds
        check_source_ids = set()
        if isinstance(item.get("facts"), list):
            for fact in item["facts"]:
                sid = fact.get("sourceId")
                if isinstance(sid, str):
                    check_source_ids.add(sid)

        if status == "fail":
            validate_findings(
                check_id,
                item.get("findings"),
                seen_finding_ids,
                catalog[check_id]["rule"],
                sources,
                check_source_ids,
            )
        elif item.get("findings"):
            raise ValueError(f"{check_id} 只有 fail 状态可以包含 findings")
        if status == "pass":
            require_text(item.get("actualEvidence"), f"{check_id}.actualEvidence")
        if status == "not_applicable":
            require_text(item.get("reason"), f"{check_id}.reason")
        if status == "not_evaluated":
            missing = item.get("missingEvidence")
            if not isinstance(missing, list) or not missing:
                raise ValueError(f"{check_id} 为 not_evaluated 时必须填写 missingEvidence")
            for index, value in enumerate(missing):
                require_text(value, f"{check_id}.missingEvidence[{index}]")
        results[check_id] = item

    missing = sorted(set(selected) - set(results))
    extra = sorted(set(results) - set(selected))
    if missing or extra:
        details = []
        if missing:
            details.append("缺少：" + ", ".join(missing))
        if extra:
            details.append("未选中：" + ", ".join(extra))
        raise ValueError("检查结果与选择范围不一致；" + "；".join(details))

    # observations 校验
    observations = data.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("observations 必须是数组")
    for index, obs in enumerate(observations):
        label = f"observations[{index}]"
        if not isinstance(obs, dict):
            raise ValueError(f"{label} 必须是对象")
        require_text(obs.get("title"), f"{label}.title")
        validate_source_ids(label, obs.get("sourceIds"), sources)
        require_text(obs.get("actualEvidence"), f"{label}.actualEvidence")
        require_text(obs.get("impact"), f"{label}.impact")
        require_text(obs.get("suggestion"), f"{label}.suggestion")
        if not isinstance(obs.get("requiresBusinessConfirmation"), bool):
            raise ValueError(f"{label}.requiresBusinessConfirmation 必须是布尔值")

    target_type = data.get("targetType")
    target_dimension = data.get("targetDimension")
    require_text(data.get("requestSummary"), "requestSummary")
    require_text(data.get("scopeReason"), "scopeReason")
    if mode == "full":
        if set(selected) != set(catalog):
            raise ValueError("全量审查必须选择全部检查项")
        scoped_fields = ("targetType", "targetAssetType", "targetScope", "targetDimension", "target")
        if any(data.get(field) not in {None, ""} for field in scoped_fields):
            raise ValueError("全量审查不得填写定向目标字段")
    if mode == "target":
        if target_type not in {"dimension", "asset", "finding"}:
            raise ValueError("targetType 必须是 dimension、asset 或 finding")
        require_text(data.get("target"), "target")
        if target_type == "dimension":
            if target_dimension not in WEIGHTS:
                raise ValueError("targetDimension 无效")
            expected = {
                check_id for check_id, rule in catalog.items()
                if rule["dimension"] == target_dimension
            }
            if set(selected) != expected:
                raise ValueError("定向维度审查必须选择该维度全部检查项")
        elif target_type == "asset":
            require_text(data.get("targetAssetType"), "targetAssetType")
            if data.get("targetScope") not in {"single", "selection", "category"}:
                raise ValueError("资产定向审查的 targetScope 必须是 single、selection 或 category")
            if target_dimension is not None and target_dimension not in WEIGHTS:
                raise ValueError("资产定向审查的 targetDimension 无效")

    applicable = [item for item in selected if results[item]["status"] != "not_applicable"]
    evaluated = [item for item in applicable if results[item]["status"] in {"pass", "fail"}]
    coverage = 100.0 if not applicable else round(len(evaluated) / len(applicable) * 100, 1)
    failed = [item for item in selected if results[item]["status"] == "fail"]
    severities = [catalog[item]["severity"] for item in failed]
    unevaluated_p0 = [
        item for item in selected
        if catalog[item]["severity"] == "P0"
        and results[item]["status"] == "not_evaluated"
    ]
    complete = coverage >= 90 and not unevaluated_p0

    output = {
        "status": "complete" if complete else "incomplete",
        "evidenceMode": evidence_mode,
        "coverage": coverage,
        "selected": len(selected),
        "evaluated": len(evaluated),
        "notApplicable": sum(results[item]["status"] == "not_applicable" for item in selected),
        "notEvaluated": sum(results[item]["status"] == "not_evaluated" for item in selected),
        "unevaluatedP0": unevaluated_p0,
        "failed": len(failed),
        "risk": (
            "高危" if "P0" in severities
            else "待核验" if unevaluated_p0
            else "警告" if "P1" in severities
            else "正常"
        ),
        "sourceInventory": {
            "totalSources": len(sources),
            "byTool": dict(Counter(s.get("tool", "") for s in sources.values())),
        },
    }

    if evidence_mode == "archive":
        raw_files = [
            s["rawPath"] for s in sources.values()
            if "rawPath" in s and isinstance(s["rawPath"], str) and s["rawPath"].strip()
        ]
        output["sourceInventory"]["rawFiles"] = len(raw_files)

    dimensions = []
    if output["status"] == "complete":
        dimensions = list(WEIGHTS) if mode == "full" else (
            [target_dimension] if target_type == "dimension" else []
        )
    if dimensions:
        output["dimensionScores"] = {
            dimension: {
                "score": max(0, WEIGHTS[dimension] - sum(
                    DEDUCTIONS[catalog[item]["severity"]]
                    for item in failed
                    if catalog[item]["dimension"] == dimension
                )),
                "weight": WEIGHTS[dimension],
            }
            for dimension in dimensions
        }
    if mode == "full" and dimensions:
        total = sum(item["score"] for item in output["dimensionScores"].values())
        output["totalScore"] = total
        output["stars"] = 5 if total >= 90 else 4 if total >= 75 else 3 if total >= 60 else 2 if total >= 40 else 1
    return output


def main():
    if len(sys.argv) != 2:
        print("用法：python3 audit_calc.py <results.json>", file=sys.stderr)
        return 2
    try:
        results_path = Path(sys.argv[1]).resolve()
        results = json.loads(results_path.read_text(encoding="utf-8"))
        if not isinstance(results, dict):
            raise ValueError("结果文件顶层必须是对象")
        checks_path = Path(__file__).resolve().parent.parent / "audit" / "audit-checks.md"
        evidence_mode = results.get("evidenceMode", "compact")
        run_dir = results_path.parent if evidence_mode == "archive" else None
        output = calculate(results, load_catalog(checks_path), run_dir)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"审查结果无效：{exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
