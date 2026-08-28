#!/usr/bin/env python3
"""
merge_worksheet_context.py
HAP 工作表结构分片合并与多维度强校验引擎。

功能：
  1. 读取 .build/artifacts/worksheet-{worksheetId}.json 各表分片数据；
  2. 字段类型标准化（数字枚举 → 统一英文类型）；
  3. 执行 10 项强校验规则（关系完整性、字段合法性、自洽性检查）；
  4. 生成 schema-validation.json 检验报告；
  5. 校验通过后原子输出 worksheetContext.json。

用法：
  python3 merge_worksheet_context.py <app_dir> [--shards-dir <shards_dir>]
示例：
  python3 merge_worksheet_context.py apps/个人读书与笔记
"""

import argparse
import json
import os
import sys
from pathlib import Path

# HAP 数值类型到标准英文类型的映射字典
TYPE_ID_TO_NAME = {
    1: "Text",
    2: "Text",
    3: "PhoneNumber",
    4: "Email",
    5: "Number",
    6: "Number",
    8: "Currency",
    9: "SingleSelect",
    10: "MultipleSelect",
    11: "Dropdown",
    14: "Attachment",
    15: "Date",
    16: "DateTime",
    19: "Region",
    20: "Formula",
    21: "Relation",
    24: "Location",
    25: "Formula",
    26: "Collaborator",
    27: "Department",
    28: "Rating",
    29: "Relation",
    30: "SubTable",
    31: "Formula",
    32: "Concatenate",
    33: "AutoNumber",
    34: "SubTable",
    36: "Checkbox",
    37: "Lookup",
    38: "Rollup",
    41: "RichText",
    42: "Signature",
    46: "Time",
    48: "Role",
    50: "Cascader",
}

SYSTEM_FIELD_IDS = {"rowid", "ownerid", "caid", "ctime", "utime", "uaid"}


def normalize_field_type(raw_type):
    """将数字或字符串字段类型标准化为统一的英文类型字符串"""
    if isinstance(raw_type, int):
        return TYPE_ID_TO_NAME.get(raw_type, f"Unknown_{raw_type}")
    if isinstance(raw_type, str):
        if raw_type.isdigit():
            return TYPE_ID_TO_NAME.get(int(raw_type), f"Unknown_{raw_type}")
        return raw_type
    return "Unknown"


def normalize_worksheet_shard(raw_data, expected_id, expected_name):
    """标准化单个分片数据结构"""
    # 支持 raw_data 直接是数组 (fields)、包含 data/template 或标准的 dict
    ws_id = raw_data.get("worksheetId") or raw_data.get("id") or expected_id
    ws_name = raw_data.get("worksheetName") or raw_data.get("name") or expected_name

    raw_fields = []
    if "fields" in raw_data and isinstance(raw_data["fields"], list):
        raw_fields = raw_data["fields"]
    elif "template" in raw_data and isinstance(raw_data["template"], dict):
        raw_fields = raw_data["template"].get("controls", [])
    elif "controls" in raw_data and isinstance(raw_data["controls"], list):
        raw_fields = raw_data["controls"]
    elif isinstance(raw_data, list):
        raw_fields = raw_data

    normalized_fields = []
    for f in raw_fields:
        if not isinstance(f, dict):
            continue
        field_id = f.get("controlId") or f.get("id") or f.get("fieldId") or ""
        field_name = f.get("controlName") or f.get("name") or f.get("fieldName") or ""
        raw_type = f.get("type") or f.get("fieldType") or 2
        field_type = normalize_field_type(raw_type)
        alias = f.get("alias") or ""
        is_title = bool(f.get("attribute") == 1 or f.get("isTitle") or f.get("is_title"))

        norm_field = {
            "id": field_id,
            "name": field_name,
            "type": field_type,
            "alias": alias,
            "isTitle": is_title,
            "required": bool(f.get("required") or f.get("notNull")),
        }

        # 提取选项
        options = f.get("options")
        if options and isinstance(options, list):
            norm_options = []
            for opt in options:
                if isinstance(opt, dict):
                    val = opt.get("value") or opt.get("name") or opt.get("key") or ""
                    norm_options.append({"value": val, "isDelete": bool(opt.get("isDelete", False))})
                elif isinstance(opt, str):
                    norm_options.append({"value": opt, "isDelete": False})
            norm_field["options"] = norm_options

        # 提取关联元数据
        data_source = f.get("dataSource") or f.get("relationWorksheetId") or ""
        if data_source:
            norm_field["dataSource"] = data_source

        relation_field = f.get("relationField") or f.get("relationControlId") or ""
        if relation_field:
            norm_field["relationField"] = relation_field

        source_field = f.get("sourceField") or f.get("sourceControlId") or ""
        if source_field:
            norm_field["sourceField"] = source_field

        # 保留辅助信息
        if "desc" in f and f["desc"]:
            norm_field["desc"] = f["desc"]
        if "remark" in f and f["remark"]:
            norm_field["remark"] = f["remark"]
        if "placeholder" in f and f["placeholder"]:
            norm_field["placeholder"] = f["placeholder"]

        normalized_fields.append(norm_field)

    return {
        "worksheetId": ws_id,
        "worksheetName": ws_name,
        "fields": normalized_fields,
    }


def validate_schema(worksheets, id_to_name, name_to_id, plan_data):
    """
    执行 10 项强校验规则
    返回: (passed: bool, errors: list, warnings: list)
    """
    errors = []
    warnings = []

    # 建立全局表与字段索引
    ws_map = {}
    for ws in worksheets:
        ws_id = ws["worksheetId"]
        ws_name = ws["worksheetName"]
        fields_by_id = {}
        fields_by_alias = {}
        title_fields = []

        for f in ws.get("fields", []):
            fid = f.get("id")
            falias = f.get("alias")
            ftype = f.get("type")

            # 1. 字段 ID 重复检查
            if fid:
                if fid in fields_by_id:
                    errors.append({
                        "worksheet": ws_name,
                        "field": f.get("name"),
                        "code": "DUPLICATE_FIELD_ID",
                        "message": f"工作表【{ws_name}】中存在重复的字段 ID: {fid}"
                    })
                fields_by_id[fid] = f

            if falias:
                if falias in fields_by_alias:
                    errors.append({
                        "worksheet": ws_name,
                        "field": f.get("name"),
                        "code": "DUPLICATE_FIELD_ALIAS",
                        "message": f"工作表【{ws_name}】中存在重复的字段别名: {falias}"
                    })
                fields_by_alias[falias] = f

            # 2. 标题字段记录
            if f.get("isTitle"):
                title_fields.append(f)

            # 3. 非法类型检查
            if ftype.startswith("Unknown"):
                warnings.append({
                    "worksheet": ws_name,
                    "field": f.get("name"),
                    "code": "UNKNOWN_FIELD_TYPE",
                    "message": f"工作表【{ws_name}】字段【{f.get('name')}】类型未识别: {ftype}"
                })

            # 4. 选项重复性与有效性检查
            if ftype in ("SingleSelect", "MultipleSelect", "Dropdown") and "options" in f:
                seen_vals = set()
                for opt in f["options"]:
                    val = opt["value"]
                    if not val:
                        errors.append({
                            "worksheet": ws_name,
                            "field": f.get("name"),
                            "code": "EMPTY_OPTION_VALUE",
                            "message": f"工作表【{ws_name}】字段【{f.get('name')}】存在空的选项值"
                        })
                    elif val in seen_vals:
                        warnings.append({
                            "worksheet": ws_name,
                            "field": f.get("name"),
                            "code": "DUPLICATE_OPTION_VALUE",
                            "message": f"工作表【{ws_name}】字段【{f.get('name')}】存在重复的选项值: {val}"
                        })
                    seen_vals.add(val)

        # 5. 标题字段有且仅有一个检查
        if len(title_fields) == 0:
            warnings.append({
                "worksheet": ws_name,
                "code": "NO_TITLE_FIELD",
                "message": f"工作表【{ws_name}】未检测到显式的标题字段(isTitle)"
            })
        elif len(title_fields) > 1:
            warnings.append({
                "worksheet": ws_name,
                "code": "MULTIPLE_TITLE_FIELDS",
                "message": f"工作表【{ws_name}】存在多个标题字段: {[tf.get('name') for tf in title_fields]}"
            })

        ws_map[ws_id] = {
            "name": ws_name,
            "fields_by_id": fields_by_id,
            "fields_by_alias": fields_by_alias,
            "fields": ws.get("fields", [])
        }

    # 跨表关联与 Lookup/Rollup 数据源强校验
    for ws in worksheets:
        ws_id = ws["worksheetId"]
        ws_name = ws["worksheetName"]
        local_fields_by_id = ws_map[ws_id]["fields_by_id"]
        local_fields_by_alias = ws_map[ws_id]["fields_by_alias"]

        def get_local_field(key):
            return local_fields_by_id.get(key) or local_fields_by_alias.get(key)

        for f in ws.get("fields", []):
            ftype = f.get("type")
            fname = f.get("name")

            # 6. Relation dataSource 校验
            if ftype in ("Relation", "SubTable"):
                ds = f.get("dataSource")
                if ds and ds not in ws_map:
                    errors.append({
                        "worksheet": ws_name,
                        "field": fname,
                        "code": "RELATION_DATASOURCE_NOT_FOUND",
                        "message": f"工作表【{ws_name}】的关联字段【{fname}】指向的目标工作表不存在 (dataSource={ds})"
                    })

            # 7. Lookup / Rollup 校验
            if ftype in ("Lookup", "Rollup"):
                rf_key = f.get("relationField")
                sf_key = f.get("sourceField")

                rf = get_local_field(rf_key) if rf_key else None
                if not rf:
                    errors.append({
                        "worksheet": ws_name,
                        "field": fname,
                        "code": "LOOKUP_RELATION_NOT_FOUND",
                        "message": f"工作表【{ws_name}】的衍生字段【{fname}】所引用的关联字段不存在 (relationField={rf_key})"
                    })
                else:
                    target_ws_id = rf.get("dataSource")
                    if not target_ws_id or target_ws_id not in ws_map:
                        errors.append({
                            "worksheet": ws_name,
                            "field": fname,
                            "code": "LOOKUP_TARGET_WORKSHEET_NOT_FOUND",
                            "message": f"工作表【{ws_name}】的衍生字段【{fname}】目标工作表不存在 (targetWs={target_ws_id})"
                        })
                    elif sf_key:
                        target_ws = ws_map[target_ws_id]
                        tf = target_ws["fields_by_id"].get(sf_key) or target_ws["fields_by_alias"].get(sf_key)
                        if not tf:
                            warnings.append({
                                "worksheet": ws_name,
                                "field": fname,
                                "code": "LOOKUP_SOURCE_FIELD_NOT_FOUND",
                                "message": f"工作表【{ws_name}】的【{fname}】在目标表【{target_ws['name']}】中未直接匹配到源字段 (sourceField={sf_key})"
                            })

    passed = len(errors) == 0
    return passed, errors, warnings


def main():
    parser = argparse.ArgumentParser(description="HAP 工作表结构分片合并与多维度强校验引擎")
    parser.add_argument("app_dir", help="应用所在目录（如 apps/个人读书与笔记）")
    parser.add_argument("--shards-dir", help="分片文件所在目录，默认为 <app_dir>/.build/artifacts")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).resolve()
    if not app_dir.exists():
        print(f"❌ 错误: 应用目录不存在: {app_dir}", file=sys.stderr)
        sys.exit(1)

    context_path = app_dir / "hap-context.json"
    plan_path = app_dir / "hap-plan.json"

    # 分片文件统一位于 .build/artifacts 目录
    if args.shards_dir:
        shards_dir = Path(args.shards_dir).resolve()
    else:
        shards_dir = app_dir / ".build" / "artifacts"

    if not context_path.exists():
        print(f"❌ 错误: hap-context.json 不存在: {context_path}", file=sys.stderr)
        sys.exit(1)

    with open(context_path, "r", encoding="utf-8") as f:
        context_data = json.load(f)

    plan_data = {}
    if plan_path.exists():
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_data = json.load(f)

    worksheet_id_by_name = context_data.get("worksheetIdByName", {})
    if not worksheet_id_by_name:
        print("❌ 错误: hap-context.json 中未找到任何 worksheetIdByName 映射", file=sys.stderr)
        sys.exit(1)

    id_to_name = {v: k for k, v in worksheet_id_by_name.items()}
    name_to_id = dict(worksheet_id_by_name)

    print(f"🔍 启动分片收集，预期工作表数量: {len(worksheet_id_by_name)}")
    print(f"📂 分片存储目录: {shards_dir}")

    # 1. 检查并读取所有分片
    normalized_shards = []
    missing_shards = []

    # 按照 plan 中的表顺序或 context 字典顺序合并
    ordered_ws_names = []
    if "worksheets" in plan_data and isinstance(plan_data["worksheets"], list):
        ordered_ws_names = [ws.get("name") for ws in plan_data["worksheets"] if ws.get("name") in worksheet_id_by_name]
    for name in worksheet_id_by_name:
        if name not in ordered_ws_names:
            ordered_ws_names.append(name)

    for ws_name in ordered_ws_names:
        ws_id = worksheet_id_by_name[ws_name]
        shard_file = shards_dir / f"worksheet-{ws_id}.json"

        if not shard_file.exists():
            missing_shards.append({"worksheetName": ws_name, "worksheetId": ws_id, "expectedFile": str(shard_file)})
            continue

        raw_shard = None
        last_err = None
        for attempt in range(4):
            try:
                with open(shard_file, "r", encoding="utf-8") as f:
                    raw_shard = json.load(f)
                if raw_shard is not None:
                    break
            except (json.JSONDecodeError, OSError) as e:
                last_err = e
                import time
                time.sleep(0.3)

        if raw_shard is not None:
            norm_shard = normalize_worksheet_shard(raw_shard, ws_id, ws_name)
            normalized_shards.append(norm_shard)
        else:
            print(f"❌ 读取分片文件失败 [{shard_file}]: {last_err}", file=sys.stderr)
            missing_shards.append({"worksheetName": ws_name, "worksheetId": ws_id, "error": str(last_err)})

    # 2. 执行 10 项强校验
    passed, errors, warnings = validate_schema(normalized_shards, id_to_name, name_to_id, plan_data)

    if missing_shards:
        passed = False
        for ms in missing_shards:
            errors.append({
                "worksheet": ms.get("worksheetName"),
                "code": "MISSING_SHARD_FILE",
                "message": f"缺失工作表分片文件: {ms}"
            })

    # 3. 输出 schema-validation.json
    validation_report = {
        "passed": passed,
        "expectedWorksheetCount": len(worksheet_id_by_name),
        "actualWorksheetCount": len(normalized_shards),
        "errorsCount": len(errors),
        "warningsCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }

    validation_path = app_dir / "schema-validation.json"
    with open(validation_path, "w", encoding="utf-8") as f:
        json.dump(validation_report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print("📋 HAP 工作表结构校验与合并报告")
    print("=" * 50)
    print(f"• 预期工作表数: {len(worksheet_id_by_name)}")
    print(f"• 实际采集分片: {len(normalized_shards)}")
    print(f"• 校验状态: {'✅ 通过 (PASSED)' if passed else '❌ 拦截未通过 (FAILED)'}")
    print(f"• 阻断错误 (Errors): {len(errors)}")
    print(f"• 优化告警 (Warnings): {len(warnings)}")

    if errors:
        print("\n⛔ 阻断错误详情 (Errors):")
        for err in errors:
            print(f"  - [{err.get('code')}] 表【{err.get('worksheet')}】: {err.get('message')}")

    if warnings:
        print("\n⚠️ 优化告警详情 (Warnings):")
        for warn in warnings:
            print(f"  - [{warn.get('code')}] 表【{warn.get('worksheet')}】: {warn.get('message')}")

    print("=" * 50)

    # 4. 若通过，原子写入 worksheetContext.json
    if passed:
        target_context_path = app_dir / "worksheetContext.json"
        temp_context_path = app_dir / "worksheetContext.json.tmp"

        with open(temp_context_path, "w", encoding="utf-8") as f:
            json.dump(normalized_shards, f, ensure_ascii=False, indent=2)
        
        # 原子替换
        temp_context_path.replace(target_context_path)
        print(f"✨ 成功原子生成全量结构上下文: {target_context_path}")
        print(f"📄 检验报告已保存至: {validation_path}\n")
        sys.exit(0)
    else:
        print(f"\n❌ 校验未通过，已生成体检报告至 {validation_path}，禁止推进状态！\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
