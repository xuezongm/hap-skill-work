#!/usr/bin/env python3
"""
scan_apps.py — 扫描 apps/ 目录，输出每个应用的名称和搭建状态。

用法：python scan_apps.py <projectRoot>
示例：python scan_apps.py /Users/user/应用搭建测试
输出：JSON 对象 { "apps": [...] }
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 优先从命令行参数获取项目根目录，否则 fallback 到脚本目录向上 4 级
project_root = (
    os.path.abspath(sys.argv[1])
    if len(sys.argv) > 1
    else os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
)
apps_dir = os.path.join(project_root, "apps")


def scan_apps():
    """扫描 apps/ 目录下的应用"""
    results = []
    if not os.path.isdir(apps_dir):
        return results

    for entry in sorted(os.listdir(apps_dir)):
        entry_path = os.path.join(apps_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        plan_path = os.path.join(entry_path, "hap-plan.json")
        if not os.path.isfile(plan_path):
            continue

        # 读取应用名
        app_name = entry
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
            if plan.get("appName"):
                app_name = plan["appName"]
        except Exception:
            pass

        # 读取搭建进度
        ctx_path = os.path.join(entry_path, "hap-context.json")
        progress = None
        status = "planned"

        if os.path.isfile(ctx_path):
            try:
                with open(ctx_path, "r", encoding="utf-8") as f:
                    ctx = json.load(f)
                progress = ctx.get("progress")
                status = "completed" if progress == "completed" else "in_progress"
            except Exception:
                pass

        results.append({
            "dir": entry,
            "appName": app_name,
            "progress": progress,
            "status": status,
        })

    return results


if __name__ == "__main__":
    output = {"apps": scan_apps()}
    print(json.dumps(output, ensure_ascii=False, indent=2))
