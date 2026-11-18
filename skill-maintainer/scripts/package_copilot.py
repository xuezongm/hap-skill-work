#!/usr/bin/env python3
"""检查并生成独立 Copilot 发布包；不复制维护工具或本机运行产物。"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT_FILES = {"SKILL.md", "README.md", "HOST_ADAPTER.md", "MCP_SETUP.md", "LICENSE", "release.json", ".gitignore"}
DIRECTORY_SUFFIXES = {
    "agents": {".yaml", ".yml"},
    "workflows": {".md"}, "plan": {".md"}, "build": {".md"},
    "modify": {".md"}, "references": {".md"},
    "scripts": {".py"},
}
EXCLUDED_PARTS = {
    ".DS_Store", "__MACOSX", ".git", ".hg", ".svn", ".hap-copilot", ".installation.json",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", ".idea", ".vscode",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def excluded(path: Path) -> bool:
    return (any(p in EXCLUDED_PARTS or p.startswith("._") for p in path.parts)
            or path.suffix in {".pyc", ".pyo"})


def collect_files(root: Path):
    """白名单决定可发布文件；额外文件和软链接必须由维护者处理。"""
    if not root.is_dir():
        raise ValueError(f"Skill 目录不存在：{root}")
    files, skipped, errors = [], [], []

    def visit(directory: Path):
        for path in sorted(directory.iterdir()):
            rel = path.relative_to(root)
            if excluded(rel):
                skipped.append(rel.as_posix())
            elif path.is_symlink():
                errors.append(f"发布内容不能包含软链接：{rel}")
            elif path.is_dir():
                if rel.parts[0] not in DIRECTORY_SUFFIXES or any(p.startswith(".") for p in rel.parts):
                    errors.append(f"未声明的发布目录：{rel}")
                else:
                    visit(path)
            elif path.is_file():
                if len(rel.parts) == 1:
                    allowed = rel.name in ROOT_FILES
                else:
                    allowed = (path.suffix in DIRECTORY_SUFFIXES.get(rel.parts[0], set())
                               and not any(p.startswith(".") for p in rel.parts))
                if allowed:
                    files.append(rel)
                else:
                    errors.append(f"未声明的发布文件：{rel}")
            else:
                errors.append(f"不支持的文件类型：{rel}")

    visit(root)
    missing = ROOT_FILES - {p.as_posix() for p in files}
    if missing:
        errors.append("缺少必需文件：" + ", ".join(sorted(missing)))
    # 复用运行时的文件清单和章节校验，避免维护另一份完整业务文件清单。
    if not errors:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-B", str(root / "scripts" / "resolve_context.py"), "--validate"],
            capture_output=True, text=True,
        )
        if result.returncode:
            errors.append("运行文件或章节校验失败：" + (result.stderr or result.stdout).strip())
    if errors:
        raise ValueError("\n".join(errors))
    return sorted(files), skipped


def package(root: Path, output: Path = None, manifest_output: Path = None):
    root = root.resolve()
    if output is not None:
        output = output.expanduser().resolve()
        if root == output or root in output.parents:
            raise ValueError("发布包必须写到 Skill 目录之外")
        if output.suffix.lower() != ".zip":
            raise ValueError("输出文件必须使用 .zip 扩展名")
    files, skipped = collect_files(root)
    release_meta = json.loads((root / "release.json").read_text(encoding="utf-8"))
    version = str(release_meta.get("version", "")).strip()
    if not version:
        raise ValueError("release.json 缺少有效的 version 字段")
    file_hashes = {rel.as_posix(): sha256_bytes((root / rel).read_bytes()) for rel in files}
    report = {
        "name": release_meta.get("name", "hap-app-copilot"),
        "version": version,
        "fileCount": len(files),
        "files": [p.as_posix() for p in files],
        "excluded": skipped,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        # x 模式保护已有包；统一包内根目录，不依赖来源目录名或安装软链接。
        with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
            for rel in files:
                archive.write(root / rel, "hap-app-copilot/" + rel.as_posix())
        with ZipFile(output) as archive:
            expected = {"hap-app-copilot/" + p.as_posix() for p in files}
            if set(archive.namelist()) != expected or archive.testzip() is not None:
                raise ValueError("发布包清单或 ZIP 完整性校验失败")
        archive_sha = sha256_bytes(output.read_bytes())
        report["output"] = str(output)
        report["archiveSHA256"] = archive_sha
        if manifest_output is not None:
            manifest_output = manifest_output.expanduser().resolve()
            manifest_data = {
                "schemaVersion": release_meta.get("schemaVersion", 1),
                "name": release_meta.get("name", "hap-app-copilot"),
                "version": version,
                "minToolsCount": release_meta.get("minToolsCount", 170),
                "archivePath": "/api/skills/hap-app-copilot.zip",
                "archiveSHA256": archive_sha,
                "files": file_hashes,
            }
            manifest_output.parent.mkdir(parents=True, exist_ok=True)
            manifest_output.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report["manifestOutput"] = str(manifest_output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path,
                        default=Path(__file__).resolve().parents[2] / "hap-app-copilot")
    parser.add_argument("--output", type=Path, help="生成 ZIP；省略时只检查并打印发布清单")
    parser.add_argument("--manifest", type=Path, help="可选：生成配套 hap-app-copilot.manifest.json 的输出路径")
    args = parser.parse_args()
    print(json.dumps(package(args.skill_dir, args.output, args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f"发布包检查失败：{exc}", file=sys.stderr)
        sys.exit(1)
