import json
import tempfile
import unittest
from pathlib import Path
from workflow_doctor.cli import main
from workflow_doctor.scanner import scan_file, scan_object, scan_path

FIXTURES = Path(__file__).parent / "fixtures"


class ScannerTests(unittest.TestCase):
    def test_valid_sample_has_no_findings(self):
        result = scan_file(FIXTURES / "valid.json")
        self.assertEqual(result["findings"], [])

    def test_missing_target_detected(self):
        issues = scan_file(FIXTURES / "missing_target.json")["findings"]
        self.assertIn("WF005", {v["rule_id"] for v in issues})

    def test_duplicate_node_id_detected(self):
        issues = scan_file(FIXTURES / "duplicate_id.json")["findings"]
        self.assertIn("WF003", {v["rule_id"] for v in issues})

    def test_invalid_json_detected(self):
        issues = scan_file(FIXTURES / "invalid.json")["findings"]
        self.assertEqual(issues[0]["rule_id"], "WF001")

    def test_non_object_structure_detected(self):
        issues = scan_object([])
        self.assertEqual(issues[0].rule_id, "WF002")

    def test_unknown_source_detected(self):
        obj = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        obj["connections"]["unknown"] = {"main": [[]]}
        self.assertIn("WF005", {v.rule_id for v in scan_object(obj)})

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            code = main(["scan", str(FIXTURES / "valid.json"), "--format", "json", "--output", str(output)])
            self.assertEqual(code, 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["file_count"], 1)

    def test_scan_does_not_change_original_file(self):
        from hashlib import sha256
        path = FIXTURES / "missing_target.json"
        before = sha256(path.read_bytes()).hexdigest()
        scan_file(path)
        self.assertEqual(before, sha256(path.read_bytes()).hexdigest())

    def test_scan_directory(self):
        result = scan_path(FIXTURES)
        self.assertEqual(result["file_count"], 4)
        self.assertGreaterEqual(result["finding_count"], 3)


if __name__ == "__main__":
    unittest.main()
