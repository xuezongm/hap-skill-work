#!/usr/bin/env python3
"""对 Skill 目录执行只读结构检查，不判断业务语义。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}
RESOURCE_DIRS = {"references", "scripts", "assets"}
IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
PATH_TOKEN_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.{}-]+\.(?:md|json|py|ya?ml|txt))"
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TODO_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\s*[:：]|\[(?:TODO|待补充|待完善)[^\]]*\]", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    path: str
    message: str


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def read_text(path: Path, findings: list[Finding], root: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        findings.append(
            Finding("error", "READ_ERROR", str(path.relative_to(root)), f"无法读取 UTF-8 文本：{exc}")
        )
        return None


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def resolve_reference(source: Path, token: str, root: Path) -> Path | None:
    token = token.strip().split("#", 1)[0]
    if not token or "{" in token or "}" in token:
        return None
    if token.startswith("file://"):
        return Path(token[7:]).resolve()
    if token.startswith(("http://", "https://", "mailto:", "#")):
        return None
    candidate = Path(token)
    if candidate.is_absolute():
        return candidate.resolve()
    local = (source.parent / candidate).resolve()
    rooted = (root / candidate).resolve()
    if local.exists():
        return local
    if rooted.exists():
        return rooted
    return rooted if "/" in token else local


def extract_references(source: Path, text: str, root: Path) -> set[Path]:
    link_tokens = {match.group(1).strip("<>") for match in MARKDOWN_LINK_RE.finditer(text)}
    path_tokens = {match.group("path") for match in PATH_TOKEN_RE.finditer(text)}
    root_entries = {path.name for path in root.iterdir()}
    tokens = set(link_tokens)
    for token in path_tokens:
        first_part = Path(token).parts[0]
        # 只检查指向 Skill 已有源码目录的路径。运行产物、URL 片段和示例路径不属于源码引用。
        if first_part in root_entries or token == "SKILL.md" or ("/" not in token and token.endswith(".py")):
            tokens.add(token)
    references: set[Path] = set()
    for token in tokens:
        if token in path_tokens and token not in link_tokens and "/" not in token and token.endswith(".py"):
            matches = [
                path
                for path in root.rglob(token)
                if path.is_file() and not any(part in IGNORED_DIRS for part in path.parts)
            ]
            if len(matches) == 1:
                references.add(matches[0].resolve())
            continue
        resolved = resolve_reference(source, token, root)
        if resolved is not None:
            references.add(resolved)
    return references


def prose_blocks(text: str) -> Iterable[str]:
    in_code = False
    buffer: list[str] = []

    def flush() -> Iterable[str]:
        if not buffer:
            return []
        value = " ".join(line.strip() for line in buffer)
        buffer.clear()
        normalized = re.sub(r"\s+", " ", value).strip()
        return [normalized] if len(normalized) >= 100 else []

    for line in text.splitlines() + [""]:
        if line.strip().startswith("```"):
            yield from flush()
            in_code = not in_code
            continue
        if in_code or line.startswith(("#", "|", "- ", "* ", ">", "    ")) or re.match(r"^\d+\. ", line):
            yield from flush()
            continue
        if not line.strip():
            yield from flush()
        else:
            buffer.append(line)


def audit(root: Path) -> tuple[list[Finding], dict[str, object]]:
    findings: list[Finding] = []
    skill_file = root / "SKILL.md"
    if not root.is_dir():
        return [Finding("error", "NOT_DIRECTORY", ".", "目标路径不是目录")], {}
    if not skill_file.is_file():
        return [Finding("error", "MISSING_SKILL", ".", "缺少根 SKILL.md")], {}

    files = list(iter_files(root))
    text_files: dict[Path, str] = {}
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = read_text(path, findings, root)
        if content is not None:
            text_files[path.resolve()] = content

    skill_text = text_files.get(skill_file.resolve(), "")
    frontmatter = parse_frontmatter(skill_text)
    for key in ("name", "description"):
        if not frontmatter.get(key):
            findings.append(Finding("error", "FRONTMATTER", "SKILL.md", f"frontmatter 缺少 {key}"))
    if frontmatter.get("name") and frontmatter["name"] != root.name:
        findings.append(
            Finding("warning", "NAME_MISMATCH", "SKILL.md", "name 与目录名不一致")
        )
    skill_lines = len(skill_text.splitlines())
    if skill_lines > 500:
        findings.append(
            Finding("warning", "LONG_ENTRY", "SKILL.md", f"入口已有 {skill_lines} 行，建议把细节渐进下沉")
        )

    graph: dict[Path, set[Path]] = defaultdict(set)
    duplicate_blocks: dict[str, list[str]] = defaultdict(list)
    for path, text in text_files.items():
        relative = str(path.relative_to(root))
        if TODO_RE.search(text):
            findings.append(Finding("warning", "PLACEHOLDER", relative, "包含 TODO/FIXME/TBD 或待补充占位"))
        for ref in extract_references(path, text, root):
            try:
                ref.relative_to(root)
            except ValueError:
                findings.append(
                    Finding("warning", "EXTERNAL_PATH", relative, f"引用 Skill 目录外路径：{ref}")
                )
                continue
            if ref.exists():
                graph[path].add(ref)
            elif path.suffix.lower() == ".md":
                findings.append(
                    Finding("error", "BROKEN_REFERENCE", relative, f"引用不存在：{ref.relative_to(root)}")
                )
        if path.suffix.lower() == ".md":
            for block in prose_blocks(text):
                duplicate_blocks[block].append(relative)

    reachable = {skill_file.resolve()}
    queue = deque(reachable)
    while queue:
        current = queue.popleft()
        for linked in graph.get(current, set()):
            linked = linked.resolve()
            if linked.exists() and linked not in reachable:
                reachable.add(linked)
                queue.append(linked)

    for path in files:
        if not any(part in RESOURCE_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.resolve() not in reachable:
            findings.append(
                Finding("warning", "ORPHAN_RESOURCE", str(path.relative_to(root)), "未从 SKILL.md 引用链到达")
            )

    for block, paths in duplicate_blocks.items():
        unique_paths = sorted(set(paths))
        if len(unique_paths) > 1:
            preview = block[:70] + ("…" if len(block) > 70 else "")
            findings.append(
                Finding(
                    "warning",
                    "DUPLICATE_PROSE",
                    ", ".join(unique_paths),
                    f"发现跨文件相同长段落：{preview}",
                )
            )

    findings.sort(key=lambda item: ({"error": 0, "warning": 1, "info": 2}[item.level], item.code, item.path))
    summary = {
        "root": str(root),
        "fileCount": len(files),
        "markdownCount": sum(path.suffix.lower() == ".md" for path in files),
        "skillLines": skill_lines,
        "reachableCount": len(reachable),
        "errors": sum(item.level == "error" for item in findings),
        "warnings": sum(item.level == "warning" for item in findings),
    }
    return findings, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="只读检查 Skill 的结构、引用、占位和明显重复")
    parser.add_argument("target", help="目标 Skill 根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="存在 warning 时也返回失败")
    args = parser.parse_args()

    root = Path(args.target).expanduser().resolve()
    findings, summary = audit(root)
    if args.json:
        print(json.dumps({"summary": summary, "findings": [asdict(item) for item in findings]}, ensure_ascii=False, indent=2))
    else:
        print(f"Skill: {summary.get('root', root)}")
        print(
            f"文件 {summary.get('fileCount', 0)}，Markdown {summary.get('markdownCount', 0)}，"
            f"错误 {summary.get('errors', 0)}，警告 {summary.get('warnings', 0)}"
        )
        for item in findings:
            label = "错误" if item.level == "error" else "警告"
            print(f"[{label}] {item.code} {item.path}: {item.message}")

    has_errors = any(item.level == "error" for item in findings)
    has_warnings = any(item.level == "warning" for item in findings)
    return 1 if has_errors or (args.strict and has_warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
