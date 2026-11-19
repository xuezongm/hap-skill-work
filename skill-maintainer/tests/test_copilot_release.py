"""原文切片、跨领域约束及独立发布包回归。"""
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

MAINTAINER = Path(__file__).resolve().parents[1]
COPILOT = MAINTAINER.parent / "hap-mcp-app-builder"
if not COPILOT.exists() and (MAINTAINER.parent / "hap-app-copilot").exists():
    COPILOT = MAINTAINER.parent / "hap-app-copilot"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolver = load("release_resolver", COPILOT / "scripts/resolve_context.py")
packager = load("package_copilot", MAINTAINER / "scripts/package_copilot.py")


def source(rel):
    return (COPILOT / rel).read_text()


def chapter(text, prefix):
    return next(p.strip() for p in re.split(r"(?=^## )", text, flags=re.MULTILINE)
                if p.startswith(prefix))


def row(text, prefix):
    return next(line for line in text.splitlines() if line.startswith(prefix))


class PolicySliceTests(unittest.TestCase):
    def render(self, assets, scenarios=()):
        return resolver.render_modify_policy_bundle(
            resolver.resolve_files("modify", list(assets), list(scenarios)), list(assets), list(scenarios))

    def test_every_alias_preserves_all_common_rules_verbatim(self):
        safety = source("modify/safety-rules.md")
        boundaries = source("modify/execution-boundaries.md")
        impact = source("modify/impact-map.md")
        required = [chapter(safety, "## " + title) for title in ("一、", "三、", "五、")]
        required += [chapter(boundaries, "## " + title) for title in ("二、", "三、")]
        required += [chapter(impact, "## 二、"), chapter(impact, "## 八、")]
        for alias in resolver.MODIFY_GUIDE_SECTION_MAPPING:
            with self.subTest(alias=alias):
                body = self.render([alias])
                for block in required:
                    self.assertIn(block, body)

    def test_role_slice_keeps_role_rules_and_omits_unrelated_table_rows(self):
        body = self.render(["role_permission"])
        self.assertIn(row(source("modify/safety-rules.md"), "| **12."), body)
        self.assertIn(row(source("modify/execution-boundaries.md"), "| **角色合并**"), body)
        self.assertIn(row(source("modify/impact-map.md"), "| 新建、修改、排序、删除或合并角色"), body)
        self.assertNotIn(row(source("modify/impact-map.md"), "| 新建、修改或删除打印模板"), body)
        self.assertNotIn(row(source("modify/execution-boundaries.md"), "| **AI 智能助手**"), body)
        self.assertNotIn("## 四、 记录数据修订硬约束", body)

    def test_public_form_does_not_load_navigation_or_portal_rows(self):
        body = self.render(["public_form"])
        impact = source("modify/impact-map.md")
        self.assertIn(row(impact, "| 原生公开表单启停与配置"), body)
        self.assertNotIn(row(impact, "| 修改应用名称"), body)
        self.assertNotIn(row(impact, "| 启用并交付可用外部门户"), body)

    def test_linked_domains_combine_without_losing_rules(self):
        body = self.render(["role_permission", "template", "view"])
        impact = source("modify/impact-map.md")
        for prefix in ("| 新建、修改、排序、删除或合并角色", "| 新建、修改或删除打印模板", "| 新建或修改视图"):
            self.assertIn(row(impact, prefix), body)
        self.assertNotIn(source("modify/print-template-file.md").strip(), body)
        self.assertIn("modify/print-template-file.md", body)

    def test_record_domains_and_data_scenarios_keep_all_data_limits(self):
        data_rules = chapter(source("modify/safety-rules.md"), "## 四、")
        for alias in ("record", "data", "record_data", "sample_data"):
            self.assertIn(data_rules, self.render([alias]))
        for scenario in resolver.MODIFY_DATA_SCENARIOS:
            with self.subTest(scenario=scenario):
                body = self.render(["field"], [scenario])
                self.assertIn(data_rules, body)
                self.assertIn("references/hap-domain-record-data-spec.md", body)
                self.assertIn(chapter(source("modify/modify_guide.md"), "## 13."), body)

    def test_workflow_scenario_also_loads_workflow_rules_and_reference(self):
        body = self.render(["field"], ["published_workflow"])
        self.assertIn("references/hap-domain-workflow-spec.md", body)
        self.assertIn(row(source("modify/safety-rules.md"), "| **10."), body)
        self.assertIn(chapter(source("modify/modify_guide.md"), "## 12."), body)

    def test_unspecified_or_broad_scope_loads_complete_original_documents(self):
        for assets in ([], ["design"], ["view", "style"]):
            body = self.render(assets)
            for rel in ("modify/safety-rules.md", "modify/execution-boundaries.md", "modify/impact-map.md"):
                self.assertIn(source(rel).strip(), body)
            for number in range(1, 14):
                self.assertIn(chapter(source("modify/modify_guide.md"), f"## {number}."), body)

    def test_table_rows_are_selected_without_rewriting(self):
        originals = {line for rel in ("modify/safety-rules.md", "modify/execution-boundaries.md",
                                      "modify/impact-map.md", "modify/modify_guide.md")
                     for line in source(rel).splitlines() if line.startswith("|")}
        for domain in resolver.POLICY_DOMAIN_BY_GUIDE_SECTION.values():
            body = self.render([domain])
            self.assertTrue(all(line in originals for line in body.splitlines() if line.startswith("|")))

    def test_new_unmapped_rule_cannot_be_silently_dropped(self):
        original = open
        def changed_open(path, *args, **kwargs):
            if str(path).endswith("modify/execution-boundaries.md"):
                text = source("modify/execution-boundaries.md")
                return io.StringIO(text.replace("| **角色合并**", "| **新增领域** | 新约束 | 规则 |\n| **角色合并**"))
            return original(path, *args, **kwargs)
        with patch.object(resolver, "open", changed_open, create=True):
            with contextlib.redirect_stderr(io.StringIO()) as messages:
                body = self.render(["role"])
            self.assertIn("| **新增领域** | 新约束 | 规则 |", body)
            # 未知条目可能影响任意领域；保留原表中的其余行，不丢规则也不阻断加载。
            for line in source("modify/execution-boundaries.md").splitlines():
                if line.startswith("|"):
                    self.assertIn(line, body)
            self.assertIn("已保留整张原表", messages.getvalue())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(resolver.validate_all_mappings())

    def test_missing_guide_heading_loads_full_source_but_validation_reports_drift(self):
        original = open
        changed = source("modify/modify_guide.md").replace("## 2.", "## 应用操作：", 1)
        def changed_open(path, *args, **kwargs):
            if str(path).endswith("modify/modify_guide.md"):
                return io.StringIO(changed)
            return original(path, *args, **kwargs)
        with patch.object(resolver, "open", changed_open, create=True):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertIn(changed.strip(), self.render(["app"]))
                self.assertFalse(resolver.validate_all_mappings())

    def test_missing_impact_heading_loads_full_source(self):
        changed = source("modify/impact-map.md").replace("统一分类与交互原则", "公共分类规则")
        with contextlib.redirect_stderr(io.StringIO()):
            result = resolver.extract_impact_map_sections(changed, ["view"], [])
        self.assertEqual(changed.rstrip(), result)

    def test_policy_without_h2_headings_loads_full_source(self):
        for kind, path in [("safety", "modify/safety-rules.md"),
                           ("boundary", "modify/execution-boundaries.md")]:
            changed = source(path).replace("\n## ", "\n### ")
            with contextlib.redirect_stderr(io.StringIO()):
                result = resolver.extract_policy_sections(changed, {"view"}, kind)
            self.assertEqual(changed.rstrip(), result)

    def test_representative_bundles_are_smaller_than_previous_full_load(self):
        # 固定已核实的旧规则包字节数；约束实际输出体积，避免只检查映射实现。
        before = {"view": 26182, "role_permission": 26453, "print_template": 26656, "external_portal": 26982}
        for domain, size in before.items():
            self.assertLess(len(self.render([domain]).encode()), size * 0.8)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.root = self.parent / "source"
        shutil.copytree(COPILOT, self.root, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        self.output = self.parent / "copilot.zip"

    def test_archive_contains_runtime_and_license_but_no_machine_artifacts(self):
        for rel in (".DS_Store", "build/.DS_Store", "scripts/__pycache__/cached.pyc",
                    "modify/._notes.md", ".hap-copilot/apps/run.json", ".git/config"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("本机杂项")
        report = packager.package(self.root, self.output)
        self.assertGreater(report["fileCount"], 50)
        self.assertIn("build/.DS_Store", report["excluded"])
        with ZipFile(self.output) as archive:
            self.assertIn("hap-mcp-app-builder/LICENSE", archive.namelist())
            self.assertIn("hap-mcp-app-builder/MCP_SETUP.md", archive.namelist())
            self.assertTrue(all(name.startswith("hap-mcp-app-builder/") for name in archive.namelist()))
            self.assertFalse(any(packager.excluded(Path(name)) for name in archive.namelist()))
            for name in archive.namelist():
                self.assertEqual((self.root / Path(name).relative_to("hap-mcp-app-builder")).read_bytes(), archive.read(name))

    def test_check_mode_does_not_create_archive(self):
        report = packager.package(self.root)
        self.assertNotIn("output", report)
        self.assertFalse(self.output.exists())

    def test_missing_license_or_required_runtime_blocks_package(self):
        for rel in ("LICENSE", "MCP_SETUP.md", "scripts/build_runtime.py"):
            path = self.root / rel
            original = path.read_bytes()
            path.unlink()
            with self.assertRaises(ValueError):
                packager.package(self.root, self.output)
            self.assertFalse(self.output.exists())
            path.write_bytes(original)

    def test_undeclared_file_and_symlink_are_rejected(self):
        extra = self.root / ".env"
        extra.write_text("local configuration")
        with self.assertRaisesRegex(ValueError, "未声明"):
            packager.package(self.root, self.output)
        extra.unlink()
        link = self.root / "references/external.md"
        link.symlink_to(self.root / "README.md")
        with self.assertRaisesRegex(ValueError, "软链接"):
            packager.package(self.root, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_archive_is_preserved_and_in_tree_output_is_rejected(self):
        self.output.write_bytes(b"existing package")
        with self.assertRaises(FileExistsError):
            packager.package(self.root, self.output)
        self.assertEqual(b"existing package", self.output.read_bytes())
        with self.assertRaisesRegex(ValueError, "目录之外"):
            packager.package(self.root, self.root / "release.zip")

    def test_missing_policy_file_fails_cli_without_partial_bundle(self):
        (self.root / "modify/safety-rules.md").unlink()
        result = subprocess.run([sys.executable, "-B", str(self.root / "scripts/resolve_context.py"),
                                 "--assets", "role", "--render"], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("必读规则文件不存在", result.stderr)

    def test_skill_update_readonly_version_check_cache_and_source_skip(self):
        import json
        import threading
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        updater = load("skill_update", COPILOT / "scripts/skill_update.py")
        serve_dir = self.parent / "server"
        serve_dir.mkdir(parents=True, exist_ok=True)
        (serve_dir / "version.json").write_text(json.dumps({
            "name": "hap-mcp-app-builder",
            "version": "2.1.0",
            "releaseNotes": "只读版本检查测试",
        }, ensure_ascii=False), encoding="utf-8")

        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(serve_dir), **kwargs)
            def log_message(self, format, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        version_url = f"http://127.0.0.1:{port}/version.json"
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        # 1. 独立安装目录应执行只读检查、发现新版并给出升级提示，且绝不修改本地文件
        install_entry = self.parent / "skills_host" / "hap-mcp-app-builder"
        shutil.copytree(self.root, install_entry)
        before_ver = (install_entry / "version.json").read_text(encoding="utf-8")

        chk = updater.cmd_check(str(install_entry), version_url=version_url, force=True, allow_http=True)
        self.assertTrue(chk["checked"])
        self.assertTrue(chk["updateAvailable"])
        self.assertEqual("2.1.0", chk["remoteVersion"])
        self.assertIn("升级 HAP 应用助手", chk["upgradeHint"])
        self.assertFalse(install_entry.is_symlink())
        self.assertEqual(before_ver, (install_entry / "version.json").read_text(encoding="utf-8"))

        # 2. 第二次无 force 检查命中 24 小时缓存
        chk_cached = updater.cmd_check(str(install_entry), version_url=version_url, force=False, allow_http=True)
        self.assertTrue(chk_cached["fromCache"])
        self.assertTrue(chk_cached["updateAvailable"])

        # 3. 符号链接/源码目录默认跳过检查
        symlink_entry = self.parent / "skills_host" / "hap-mcp-app-builder-link"
        symlink_entry.symlink_to(install_entry)
        chk_skip = updater.cmd_check(str(symlink_entry))
        self.assertFalse(chk_skip["checked"])
        self.assertTrue(chk_skip["isSourceWorkspace"])

    def test_export_as_hap_mcp_app_builder_and_cleanup_legacy_v1_files(self):
        import json
        export_target = self.parent / "hap-skills" / "skills" / "mcp" / "hap-mcp-app-builder"
        report = packager.package(self.root, export_dir=export_target, skill_name="hap-mcp-app-builder")
        self.assertEqual("hap-mcp-app-builder", report["name"])
        self.assertTrue((export_target / "version.json").is_file())
        self.assertFalse((export_target / "release.json").exists())
        self.assertIn("name: hap-mcp-app-builder\n", (export_target / "SKILL.md").read_text(encoding="utf-8"))
        ver_meta = json.loads((export_target / "version.json").read_text(encoding="utf-8"))
        self.assertEqual("hap-mcp-app-builder", ver_meta["name"])
        self.assertEqual("2.0.0", ver_meta["version"])

        # 模拟 1.0.0 覆盖安装后残留的旧文件，运行 scan_apps.py 应自动清理
        (export_target / "plan" / "SKILL.md").write_text("legacy v1", encoding="utf-8")
        (export_target / "build" / "SKILL.md").write_text("legacy v1", encoding="utf-8")
        (export_target / "build" / "steps" / "12_cli_refinement.md").write_text("legacy v1", encoding="utf-8")
        res = subprocess.run([sys.executable, "-B", str(export_target / "scripts" / "scan_apps.py"), str(self.parent)],
                             capture_output=True, text=True)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertFalse((export_target / "plan" / "SKILL.md").exists())
        self.assertFalse((export_target / "build" / "SKILL.md").exists())
        self.assertFalse((export_target / "build" / "steps" / "12_cli_refinement.md").exists())


if __name__ == "__main__":
    unittest.main()
