"""Real entry points, ZIP safety reuse, privacy and backwards compatibility."""
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

from workflow_doctor.cli import main
from workflow_doctor.models import AnalysisLimits
from workflow_doctor.scanner import analyze_path, scan_bytes, scan_path
from test_dependencies import caller
from test_graphs import node, workflow


class AnalysisCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "inputs"
        self.source.mkdir()

    def write(self, name, data):
        path = self.source / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_default_scan_report_exactly_preserves_old_contract(self):
        path = self.write("A.json", caller("B"))
        report = scan_path(path)
        self.assertNotIn("analysis", report)
        self.assertEqual(report["schema_version"], "0.2")
        self.assertEqual(set(report), {"schema_version", "input", "file_count", "finding_count", "error_count", "skipped_count", "complete", "results", "skipped", "errors", "notice"})
        self.assertEqual(report["results"][0], scan_bytes(path.read_bytes(), str(path)))
        code, stdout, _ = self.invoke(["scan", str(path), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), report)

    def test_analyze_api_and_cli_json_use_same_engine(self):
        self.write("A.json", caller("B"))
        self.write("B.json", workflow("B"))
        expected = analyze_path(self.source)
        code, stdout, stderr = self.invoke(["analyze", str(self.source)])
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), expected)
        self.assertEqual(expected["analysis"]["summary"]["workflow_count"], 2)

    def test_markdown_and_graph_json_export(self):
        self.write("A.json", caller("B"))
        for fmt, name in (("markdown", "report.md"), ("graph-json", "graphs.json"), ("json", "report.json")):
            output = self.root / name
            code, _, _ = self.invoke(["analyze", str(self.source), "--format", fmt, "--output", str(output)])
            self.assertEqual(code, 1)
            content = output.read_text(encoding="utf-8")
            if fmt == "markdown":
                for text in ("Missing From Import Set", "WF008", "Recommendation", "Human review", "Compatibility"):
                    self.assertIn(text, content)
            elif fmt == "graph-json":
                graphs = json.loads(content)
                self.assertTrue(graphs["workflow_dependencies"]["multigraph"])
                self.assertEqual(len(graphs["node_graphs"]), 1)
            else:
                self.assertIn("analysis", json.loads(content))

    def test_text_analysis_includes_status_confidence_and_recommendation(self):
        path = self.write("A.json", caller("missing"))
        code, stdout, _ = self.invoke(["analyze", str(path), "--format", "text"])
        self.assertEqual(code, 1)
        for text in ("WF008", "Missing From Import Set", "high", "Recommendation"):
            self.assertIn(text, stdout)

    def test_analysis_reuses_safe_zip_import_and_preserves_hash(self):
        archive = self.root / "batch.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("A.json", json.dumps(caller("B")))
            bundle.writestr("nested/B.json", json.dumps(workflow("B")))
            bundle.writestr("run.py", "raise AssertionError('must never execute')")
        before = sha256(archive.read_bytes()).hexdigest()
        report = analyze_path(archive)
        self.assertEqual(report["analysis"]["summary"]["workflow_count"], 2)
        self.assertEqual(report["skipped_count"], 1)
        self.assertEqual(before, sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(report["analysis"]["dependencies"][0]["status"], "Found In Import Set")

    def test_unsafe_zip_discards_analysis_and_results(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.json", json.dumps(workflow()))
        report = analyze_path(archive)
        self.assertFalse(report["complete"])
        self.assertEqual(report["errors"][0]["code"], "ZIP_UNSAFE_PATH")
        self.assertNotIn("analysis", report)
        self.assertEqual(report["results"], [])

    def test_invalid_json_is_preserved_and_excluded_from_graphs(self):
        self.write("A.json", workflow())
        (self.source / "broken.json").write_bytes(b"{")
        report = analyze_path(self.source)
        self.assertTrue(report["complete"])
        self.assertEqual(report["finding_count"], 1)
        self.assertEqual(report["analysis"]["coverage"], "partial")
        self.assertEqual(report["analysis"]["summary"]["workflow_count"], 1)

    def test_recursive_analysis_and_file_hashes_unchanged(self):
        a = self.write("A.json", caller())
        (self.source / "nested").mkdir()
        b = self.write("nested/B.json", workflow("B"))
        before = {path: sha256(path.read_bytes()).hexdigest() for path in (a, b)}
        self.assertEqual(analyze_path(self.source)["analysis"]["summary"]["missing_resource_count"], 1)
        report = analyze_path(self.source, recursive=True)
        self.assertEqual(report["analysis"]["summary"]["missing_resource_count"], 0)
        self.assertEqual(before, {path: sha256(path.read_bytes()).hexdigest() for path in before})

    def test_analysis_budget_failure_is_structured(self):
        self.write("A.json", workflow())
        report = analyze_path(self.source, analysis_limits=AnalysisLimits(max_graph_nodes=1))
        self.assertEqual(report["errors"][0]["code"], "ANALYSIS_GRAPH_LIMIT")
        self.assertFalse(report["complete"])
        self.assertNotIn("analysis", report)
        code, stdout, _ = self.invoke(["analyze", str(self.source), "--analysis-max-graph-nodes", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["errors"][0]["code"], "ANALYSIS_GRAPH_LIMIT")

    def test_no_network_no_execution_and_all_formats_are_private(self):
        secret = "SYNTHETIC_PRIVATE_VALUE"
        marker = self.root / "executed"
        data = caller("={{ $json.workflowId }}")
        data["nodes"].append(node("code", "n8n-nodes-base.code", {
            "jsCode": f"open({str(marker)!r}, 'w').write('executed')",
            "url": f"https://user:{secret}@private.invalid/api?token={secret}",
            "headers": {"Authorization": "Bearer " + secret}, "file": "/private/" + secret}))
        data["nodes"][0]["credentials"] = {"test": {"id": secret, "name": secret, "token": secret}}
        path = self.write("input.json", data)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            for fmt in ("json", "markdown", "graph-json", "text"):
                code, stdout, stderr = self.invoke(["analyze", str(path), "--format", fmt])
                self.assertEqual(code, 1)
                self.assertNotIn(secret, stdout + stderr)
                self.assertNotIn("private.invalid", stdout + stderr)
                self.assertNotIn("Authorization", stdout + stderr)
        self.assertFalse(marker.exists())

    def test_analyze_report_cannot_overwrite_original(self):
        path = self.write("A.json", caller())
        before = path.read_bytes()
        code, _, stderr = self.invoke(["analyze", str(path), "--output", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(json.loads(stderr)["errors"][0]["code"], "OUTPUT_WRITE_ERROR")

    def test_absent_networkx_does_not_break_basic_scan(self):
        path = self.write("A.json", workflow())
        loader = "import runpy, sys\nsys.path.insert(0, sys.argv.pop(1))\nrunpy.run_module('workflow_doctor', run_name='__main__')"
        # absolute() needs no Windows final-path handle or symlink privileges.
        source_root = str(Path(__file__).absolute().parents[1] / "src")
        for command, expected in (("scan", 0), ("analyze", 2)):
            process = subprocess.run([sys.executable, "-S", "-c", loader, source_root, command, str(path), "--format", "json"],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, expected, process.stderr)
            report = json.loads(process.stdout)
            if command == "analyze":
                self.assertEqual(report["errors"][0]["code"], "ANALYSIS_DEPENDENCY_MISSING")

    def test_new_cli_exit_codes_zero_one_two(self):
        clean = self.write("A.json", workflow())
        code, _, _ = self.invoke(["analyze", str(clean)])
        self.assertEqual(code, 0)
        code, stdout, _ = self.invoke(["analyze", str(self.root / "absent.json"), "--format", "graph-json"])
        self.assertEqual(code, 2)
        self.assertIn("errors", json.loads(stdout))

    def test_markdown_escapes_untrusted_source_metadata(self):
        from workflow_doctor.analysis import analyze_documents
        from workflow_doctor.reporting import to_markdown
        from workflow_doctor.scanner import make_report
        report = make_report()
        report["analysis"] = analyze_documents([("<script>alert(1)</script>|[x](https://bad.invalid).json", caller())])
        text = to_markdown(report)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("[x](https://bad.invalid)", text)
