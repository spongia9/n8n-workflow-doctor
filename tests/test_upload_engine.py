"""Memory uploads share structural, ZIP, graph and rendering implementations."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from test_graphs import node, workflow
from workflow_doctor.models import ScanLimits
from workflow_doctor.reporting import render_report
from workflow_doctor.scanner import scan_path, scan_uploads


def archive(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as value:
        for name, raw in entries:
            value.writestr(name, raw)
    return buffer.getvalue()


class UploadEngineTests(unittest.TestCase):
    def test_memory_json_matches_path_engine_except_visible_source_metadata(self):
        raw = json.dumps(workflow()).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upload.json"
            path.write_bytes(raw)
            expected = scan_path(path, analyze=True)
        actual = scan_uploads([(str(path), raw)])
        self.assertEqual(actual, expected)

    def test_memory_zip_matches_path_engine_including_multi_output_metadata(self):
        raw = archive([("A.json", json.dumps(workflow())), ("ignored.py", "NEVER_EXECUTE")])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upload.zip"
            path.write_bytes(raw)
            expected = scan_path(path, analyze=True)
        actual = scan_uploads([(str(path), raw)])
        self.assertEqual(actual, expected)
        self.assertEqual(actual["skipped_count"], 1)

    def test_batch_calls_resolve_across_files(self):
        a = workflow("A", nodes=[node("call", "n8n-nodes-base.executeWorkflow", {"workflowId": "B"})])
        result = scan_uploads([("A.json", json.dumps(a).encode()), ("B.json", json.dumps(workflow("B")).encode())])
        self.assertEqual(result["analysis"]["dependencies"][0]["status"], "Found In Import Set")
        self.assertEqual(result["analysis"]["summary"]["workflow_count"], 2)

    def test_parse_failure_remains_diagnostic_not_input_error(self):
        report = scan_uploads([("A.json", b'{"PRIVATE":')])
        self.assertTrue(report["complete"])
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["analysis"]["blocking_issues"][0]["rule_id"], "WF001")
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_type_empty_mixed_count_and_total_rejection_are_atomic(self):
        cases = [([], ScanLimits(), "INPUT_EMPTY"),
                 ([("x.txt", b"x")], ScanLimits(), "INPUT_UNSUPPORTED_TYPE"),
                 ([("x.zip", b"x"), ("y.json", b"{}")], ScanLimits(), "INPUT_MIXED_ARCHIVE"),
                 ([("a.json", b"{}"), ("b.json", b"{}")], ScanLimits(max_files=1), "INPUT_FILE_COUNT"),
                 ([("a.json", b"{}")], ScanLimits(max_total_bytes=1), "INPUT_TOTAL_TOO_LARGE")]
        for files, limits, code in cases:
            report = scan_uploads(files, limits)
            self.assertEqual(report["errors"][0]["code"], code)
            self.assertEqual(report["results"], [])

    def test_zip_traversal_corruption_and_limits_use_existing_validator(self):
        cases = [(b"broken", ScanLimits(), "ZIP_INVALID"),
                 (archive([("../private.json", "{}")]), ScanLimits(), "ZIP_UNSAFE_PATH"),
                 (archive([("a.json", "{}"), ("b.json", "{}")]), ScanLimits(max_files=1), "ZIP_FILE_COUNT"),
                 (archive([("a.json", "{}")]), ScanLimits(max_archive_bytes=1), "ZIP_ARCHIVE_TOO_LARGE")]
        for raw, limits, code in cases:
            report = scan_uploads([("data.zip", raw)], limits)
            self.assertEqual(report["errors"][0]["code"], code)

    def test_memory_scan_does_not_read_paths_or_modify_inputs(self):
        raw = json.dumps(workflow()).encode()
        files = [("not-a-real-file.json", raw)]
        with patch("pathlib.Path.open", side_effect=AssertionError("disk read forbidden")):
            report = scan_uploads(files)
        self.assertTrue(report["complete"])
        self.assertEqual(files, [("not-a-real-file.json", raw)])

    def test_shared_render_dispatch_and_unknown_format(self):
        report = scan_uploads([("A.json", json.dumps(workflow()).encode())])
        for format in ("text", "json", "markdown", "html"):
            self.assertTrue(render_report(report, format))
        with self.assertRaises(ValueError):
            render_report(report, "xml")
