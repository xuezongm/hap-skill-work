"""打印本地步骤的同步隔离、来源检查与按需加载回归。"""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MAINTAINER = Path(__file__).resolve().parents[1]
COPILOT = MAINTAINER.parent / "hap-app-copilot"
spec = importlib.util.spec_from_file_location("copilot_sync", MAINTAINER / "scripts/sync_hap_copilot.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
STEP = "modify/print-template-file.md"
OLD_MIRROR = "references/hap-domain-print-template-spec.md"


class PrintStepSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prod = self.root / "prod"
        self.local = self.root / "copilot"
        for name in sync.SHARED_SKILL_NAMES:
            self.put(self.prod / "skills" / name / "SKILL.md", f"---\nname: {name}\n---\n\n# {name}\n")
        for path, sources in sync.BUILD_STEP_YAML_MAP.items():
            self.put(self.local / path, "\n".join(sources))
        self.put(self.local / "modify/modify_guide.md", "\n".join(sync.MODIFY_YAML_LIST))
        for path, sources in sync.LOCAL_STEP_SOURCE_MAP.items():
            self.put(self.local / path, "本地步骤正文\n" + "\n".join(sources))
            for source in sources:
                self.put(self.prod / source, "服务端原文，不写入公开包\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, sync.sync_specs(self.local, self.prod))

    @staticmethod
    def put(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def check(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = sync.check_alignment(self.local, self.prod, as_json=True)
        return code, json.loads(output.getvalue())

    def test_valid_sync_keeps_print_out_of_mirrors(self):
        code, report = self.check()
        self.assertEqual(0, code)
        self.assertEqual(19, report["sharedSpecsCount"])
        self.assertFalse((self.local / OLD_MIRROR).exists())

    def test_repeated_sync_preserves_local_step_and_upstream(self):
        path = self.local / STEP
        path.write_text(path.read_text() + "\n本地适配更新\n")
        expected = path.read_bytes()
        sources = {p: p.read_bytes() for p in self.prod.rglob("*") if p.is_file()}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, sync.sync_specs(self.local, self.prod, clean_legacy=True))
        self.assertEqual(expected, path.read_bytes())
        self.assertFalse((self.local / OLD_MIRROR).exists())
        for source, original in sources.items():
            self.assertEqual(original, source.read_bytes())

    def test_missing_step_is_reported(self):
        (self.local / STEP).unlink()
        code, report = self.check()
        self.assertEqual(1, code)
        self.assertTrue(report["localStepIssues"])

    def test_missing_source_is_reported(self):
        (self.prod / sync.LOCAL_STEP_SOURCE_MAP[STEP][0]).unlink()
        code, report = self.check()
        self.assertEqual(1, code)
        self.assertTrue(report["localStepIssues"])

    def test_missing_source_anchor_is_reported(self):
        self.put(self.local / STEP, "丢失来源标记的步骤")
        code, report = self.check()
        self.assertEqual(1, code)
        self.assertTrue(report["localStepIssues"])

    def test_obsolete_print_mirror_is_reported(self):
        self.put(self.local / OLD_MIRROR, "旧版打印镜像")
        code, report = self.check()
        self.assertEqual(1, code)
        self.assertIn(Path(OLD_MIRROR).name, report["extraReferenceFiles"])

    def test_other_shared_specs_still_require_exact_alignment(self):
        path = self.local / "references/hap-domain-role-spec.md"
        path.write_text(path.read_text() + "意外变更\n")
        code, report = self.check()
        self.assertEqual(1, code)
        self.assertEqual("hap-domain-role-spec", report["driftedSpecs"][0]["name"])


class PrintStepLoadingTests(unittest.TestCase):
    def resolve(self, *args):
        return subprocess.check_output(
            [sys.executable, str(COPILOT / "scripts/resolve_context.py"), *args], text=True
        )

    def test_print_aliases_resolve_local_step_with_safety_rules(self):
        for domain in ("print_template", "template"):
            with self.subTest(domain=domain):
                data = json.loads(self.resolve("--mode", "modify", "--domains", domain, "--json"))
                self.assertIn(STEP, data["files"])
                self.assertIn("modify/safety-rules.md", data["files"])
                self.assertNotIn(OLD_MIRROR, data["files"])

    def test_configuration_context_does_not_inline_file_making(self):
        body = self.resolve("--mode", "modify", "--domains", "print_template", "--render")
        self.assertIn(STEP, body)
        self.assertIn("纯配置和删除跳过", body)
        self.assertIn("update_file_print_template", body)
        self.assertIn("delete_print_template", body)
        self.assertNotIn("## HAP 占位符速查", body)
        self.assertNotIn(OLD_MIRROR, body)

    def test_file_task_can_read_step_sections(self):
        syntax = self.resolve("--file", STEP, "--section", "HAP 占位符速查")
        checks = self.resolve("--file", STEP, "--section", "交付检查")
        self.assertIn("#Relation.Repeat[start]#", syntax)
        self.assertIn("sharedStrings.xml", checks)

    def test_unrelated_domain_does_not_load_print_step(self):
        data = json.loads(self.resolve("--mode", "modify", "--domains", "role_permission", "--json"))
        self.assertNotIn(STEP, data["files"])
        self.assertIn("references/hap-domain-role-spec.md", data["files"])


if __name__ == "__main__":
    unittest.main()
