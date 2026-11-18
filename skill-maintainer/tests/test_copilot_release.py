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
            self.assertIn("hap-app-copilot/LICENSE", archive.namelist())
            self.assertIn("hap-app-copilot/MCP_SETUP.md", archive.namelist())
            self.assertTrue(all(name.startswith("hap-app-copilot/") for name in archive.namelist()))
            self.assertFalse(any(packager.excluded(Path(name)) for name in archive.namelist()))
            for name in archive.namelist():
                self.assertEqual((self.root / Path(name).relative_to("hap-app-copilot")).read_bytes(), archive.read(name))

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

    def test_skill_update_check_atomic_upgrade_dirty_guard_and_rollback(self):
        import json
        import threading
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        updater = load("skill_update", COPILOT / "scripts/skill_update.py")
        # 1. 构造 v1.0.1 远端发布包与 manifest.json
        v2_src = self.parent / "v2_src"
        shutil.copytree(self.root, v2_src)
        (v2_src / "release.json").write_text(json.dumps({
            "name": "hap-app-copilot", "version": "1.0.1", "schemaVersion": 1, "minToolsCount": 170
        }), encoding="utf-8")

        serve_dir = self.parent / "server"
        api_skills = serve_dir / "api" / "skills"
        api_skills.mkdir(parents=True, exist_ok=True)
        packager.package(v2_src, api_skills / "hap-app-copilot.zip", api_skills / "hap-app-copilot.manifest.json")

        # 2. 启动本地测试 HTTP Server
        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(serve_dir), **kwargs)
            def log_message(self, format, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        server_url = f"http://127.0.0.1:{port}"
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

        # 3. 准备初始 v1.0.0 受管理目录并执行 check -> update -> rollback
        install_entry = self.parent / "skills_host" / "hap-app-copilot"
        shutil.copytree(self.root, install_entry)
        updater.cmd_auto_update(str(install_entry), enable=True, server=server_url, allow_http=True)

        chk = updater.cmd_check(str(install_entry), server=server_url, force=True, allow_http=True)
        self.assertTrue(chk["checked"])
        self.assertTrue(chk["updateAvailable"])
        self.assertEqual("1.0.1", chk["remoteVersion"])

        upd = updater.cmd_update(str(install_entry), server=server_url, allow_http=True)
        self.assertTrue(upd["updated"])
        self.assertEqual("1.0.1", upd["version"])
        self.assertTrue(install_entry.is_symlink())

        # 4. 本地修改文件后应触发 Dirty Check 保护
        (install_entry / "README.md").write_text("user customized", encoding="utf-8")
        st_dirty = updater.cmd_status(str(install_entry))
        self.assertTrue(any("README.md" in item for item in st_dirty["dirtyFiles"]))
        with self.assertRaisesRegex(ValueError, "本地定制修改"):
            updater.cmd_update(str(install_entry), server=server_url, allow_http=True)

        # 5. 回滚至上一版本 1.0.0 并自动关闭 autoUpdate
        rb = updater.cmd_rollback(str(install_entry))
        self.assertTrue(rb["rolledBack"])
        self.assertEqual("1.0.0", rb["version"])
        self.assertFalse(rb["autoUpdate"])


if __name__ == "__main__":
    unittest.main()
