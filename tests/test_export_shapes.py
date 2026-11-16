"""Fabricated export-shape coverage; deliberately not a real-export claim."""
import copy
import json
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from workflow_doctor.scanner import scan_file, scan_object

FIXTURE = Path(__file__).parent / "fixtures_compat" / "synthetic_export_shape.json"


class SyntheticExportShapeTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_combined_agent_http_subworkflow_shape_is_structurally_accepted(self):
        result = scan_file(FIXTURE)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["compatibility"], "unknown")

    def test_ai_connection_types_and_multiple_output_ports_preserved(self):
        data = self.load()
        before = copy.deepcopy(data)
        self.assertEqual(scan_object(data), [])
        self.assertEqual(data, before)
        self.assertEqual(len(data["connections"]["route"]["main"]), 4)
        self.assertIsNone(data["connections"]["route"]["main"][2])
        self.assertEqual(data["connections"]["route"]["main"][1][0]["index"], 1)
        self.assertIn("ai_languageModel", data["connections"]["model"])
        self.assertIn("ai_tool", data["connections"]["tool"])

    def test_missing_ai_target_detected_with_location(self):
        data = self.load()
        data["connections"]["model"]["ai_languageModel"][0][0]["node"] = "absent"
        findings = [finding for finding in scan_object(data) if finding.rule_id == "WF005"]
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].location.endswith("[0][0].node"))

    def test_malformed_ai_link_type_detected(self):
        data = self.load()
        data["connections"]["tool"]["ai_tool"][0][0]["type"] = False
        findings = scan_object(data)
        self.assertTrue(any(item.rule_id == "WF002" and item.location.endswith(".type") for item in findings))

    def test_hash_unknown_fields_and_sensitive_placeholders_unchanged(self):
        before = sha256(FIXTURE.read_bytes()).hexdigest()
        data = self.load()
        original = copy.deepcopy(data)
        scan_object(data)
        report = scan_file(FIXTURE)
        self.assertEqual(data, original)
        self.assertEqual(before, sha256(FIXTURE.read_bytes()).hexdigest())
        for value in ("SYNTHETIC_SHAPE_ONLY", "synthetic-credential-id", "example.invalid"):
            self.assertNotIn(value, json.dumps(report))

    def test_synthetic_scan_never_uses_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(scan_file(FIXTURE)["findings"], [])
