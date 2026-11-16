"""CLI and safety regressions using only temporary fabricated inputs."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from test_graphs import node, workflow
from workflow_doctor.cli import main
from workflow_doctor.html_report import to_html
from workflow_doctor.reporting import to_markdown
from workflow_doctor.scanner import analyze_path
from tools.review_public_files import review_blob


FORMATS = ("text", "json", "markdown", "html")


class CliSecurityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "模拟.json"
        self.path.write_text(json.dumps(workflow()), encoding="utf-8")

    def invoke(self, command, path, fmt, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([command, str(path), "--format", fmt, *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_all_formats_keep_scan_exit_codes_zero_one_two(self):
        bad = self.root / "bad.json"
        bad.write_text('{"PRIVATE_SENTINEL":', encoding="utf-8")
        for fmt in FORMATS:
            for path, expected in ((self.path, 0), (bad, 1), (self.root / "missing.json", 2)):
                code, stdout, stderr = self.invoke("scan", path, fmt)
                self.assertEqual(code, expected)
                self.assertNotIn("Traceback", stdout + stderr)
                self.assertNotIn("PRIVATE_SENTINEL", stdout + stderr)

    def test_new_node_risk_gates_analyze_without_changing_structural_scan(self):
        data = workflow(nodes=[node("n", "n8n-nodes-base.httpRequest", {"token": "SYNTHETIC_PRIVATE"}, 4.5)])
        self.path.write_text(json.dumps(data), encoding="utf-8")
        for fmt in FORMATS:
            code, stdout, stderr = self.invoke("analyze", self.path, fmt)
            self.assertEqual(code, 1)
            self.assertIn("WF011", stdout)
            self.assertNotIn("SYNTHETIC_PRIVATE", stdout + stderr)
            self.assertEqual(self.invoke("scan", self.path, fmt)[0], 0)

    def test_html_and_markdown_scan_output_files_and_no_overwrite(self):
        before = sha256(self.path.read_bytes()).hexdigest()
        for fmt, suffix in (("html", "html"), ("markdown", "md")):
            output = self.root / ("report." + suffix)
            code, _, _ = self.invoke("scan", self.path, fmt, "--output", str(output))
            self.assertEqual(code, 0)
            content = output.read_bytes()
            self.assertTrue(content.decode("utf-8"))
            code, _, stderr = self.invoke("scan", self.path, fmt, "--output", str(output))
            self.assertEqual(code, 2)
            self.assertIn("OUTPUT_WRITE_ERROR", stderr)
            self.assertEqual(output.read_bytes(), content)
        self.assertEqual(sha256(self.path.read_bytes()).hexdigest(), before)

    def test_all_formats_refuse_overwriting_the_input(self):
        before = self.path.read_bytes()
        for fmt in FORMATS:
            self.assertEqual(self.invoke("scan", self.path, fmt, "--output", str(self.path))[0], 2)
            self.assertEqual(self.path.read_bytes(), before)

    def test_recursive_zip_multifile_and_hashes(self):
        nested = self.root / "nested"
        nested.mkdir()
        second = nested / "B.json"
        second.write_text(json.dumps(workflow("B")), encoding="utf-8")
        archive = self.root / "synthetic.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(self.path, "A.json")
            zf.write(second, "nested/B.json")
            zf.writestr("ignored.py", "raise Exception('NEVER_EXECUTE')")
        before = {path: sha256(path.read_bytes()).hexdigest() for path in (self.path, second, archive)}
        for fmt in FORMATS:
            for path, extra in ((self.root, ("--recursive",)), (archive, ())):
                code, text, _ = self.invoke("analyze", path, fmt, *extra)
                self.assertEqual(code, 0)
                if fmt == "json":
                    self.assertEqual(json.loads(text)["analysis"]["summary"]["workflow_count"], 2)
                self.assertNotIn("NEVER_EXECUTE", text)
        self.assertEqual(before, {path: sha256(path.read_bytes()).hexdigest() for path in before})

    def test_zip_traversal_is_blocked_in_all_formats(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../SYNTHETIC_PRIVATE.json", self.path.read_bytes())
        for fmt in FORMATS:
            code, text, errors = self.invoke("analyze", archive, fmt)
            self.assertEqual(code, 2)
            self.assertNotIn("SYNTHETIC_PRIVATE", text + errors)
            self.assertNotIn("Traceback", text + errors)
        self.assertFalse((self.root.parent / "SYNTHETIC_PRIVATE.json").exists())

    def test_input_and_archive_limits_remain_enforced(self):
        archive = self.root / "limits.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("A.json", self.path.read_bytes())
            zf.writestr("B.json", self.path.read_bytes())
        for fmt in FORMATS:
            for path, flag in ((self.path, "--max-file-bytes"), (archive, "--max-files"),
                               (archive, "--max-file-bytes"), (archive, "--max-total-bytes"), (archive, "--max-archive-bytes")):
                self.assertEqual(self.invoke("analyze", path, fmt, flag, "1")[0], 2)

    def test_corrupt_zip_is_structured_without_exception_payloads(self):
        archive = self.root / "broken.zip"
        archive.write_bytes(b"PK\x03\x04PRIVATE_SENTINEL")
        for fmt in FORMATS:
            code, text, errors = self.invoke("scan", archive, fmt)
            self.assertEqual(code, 2)
            self.assertNotIn("PRIVATE_SENTINEL", text + errors)
            self.assertNotIn("Traceback", text + errors)

    def test_code_network_and_logging_are_not_used_by_any_report_format(self):
        data = workflow(nodes=[node("code", "n8n-nodes-base.code", {"jsCode": "throw new Error('PRIVATE_SENTINEL')"}),
                               node("http", "n8n-nodes-base.httpRequest", {"url": "https://never-request.invalid/PRIVATE_SENTINEL"}, 4.5)])
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("URL forbidden")), \
                patch("os.system", side_effect=AssertionError("code forbidden")), \
                patch("builtins.eval", side_effect=AssertionError("code forbidden")), \
                patch("logging.Logger._log", side_effect=AssertionError("logging forbidden")):
            for fmt in FORMATS:
                code, text, errors = self.invoke("analyze", self.path, fmt)
                self.assertEqual(code, 0)
                self.assertNotIn("PRIVATE_SENTINEL", text + errors)

    def test_parse_failure_does_not_add_spurious_workflow_structure_error(self):
        self.path.write_text('{"SYNTHETIC_PRIVATE":', encoding="utf-8")
        report = analyze_path(self.path)
        self.assertEqual({c["rule_id"] for c in report["analysis"]["blocking_issues"]}, {"WF001"})
        self.assertEqual(report["analysis"]["summary"]["workflow_count"], 0)
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(report))

    def test_unknown_environment_alone_does_not_change_legacy_exit_zero(self):
        for fmt in FORMATS:
            code, text, _ = self.invoke("analyze", self.path, fmt)
            self.assertEqual(code, 0)
            self.assertIn("WF016", text)
        report = analyze_path(self.path)["analysis"]
        self.assertEqual(report["summary"]["manual_review_count"], 0)
        self.assertEqual(report["summary"]["additional_review_count"], 1)

    def test_public_html_requires_exact_review_allowlist(self):
        self.assertEqual(review_blob("examples/sprint3/migration-report.html", b"<!doctype html>"), [])
        self.assertEqual(review_blob("private-report.html", b"<!doctype html>")[0]["code"], "UNREVIEWED_HTML")
        for path in ("output/playwright/snapshot.md", ".playwright-cli/page.yml", ".tmp/script.py"):
            self.assertEqual(review_blob(path, b"synthetic")[0]["code"], "PRIVATE_PATH")

    def test_actual_cli_subprocess_writes_utf8_html_without_traceback(self):
        output = self.root / "实际报告.html"
        process = subprocess.run([sys.executable, "-m", "workflow_doctor", "scan", str(self.path), "--format", "html", "--output", str(output)], capture_output=True)
        self.assertEqual(process.returncode, 0)
        self.assertIn("工作流迁移诊断报告", output.read_text(encoding="utf-8"))
        self.assertNotIn(b"Traceback", process.stderr)

    def test_renderer_can_consume_previous_analysis_report_versions(self):
        report = json.loads(Path("examples/sprint2/migration-report.json").read_text(encoding="utf-8"))
        self.assertIn("Workflow", to_html(report))
        self.assertIn("WF008", to_markdown(report))
