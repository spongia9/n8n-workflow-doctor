"""Fabricated node risks, false-positive boundaries and additive contracts."""
import copy
import json
import unittest
from unittest.mock import patch

from test_graphs import node, workflow
from workflow_doctor.analysis import analyze_documents
from workflow_doctor.models import AnalysisLimits, InputError
from workflow_doctor.node_rules import diagnose_nodes
from workflow_doctor.scanner import scan_bytes


def http(parameters, version=4.5):
    return workflow(nodes=[node("http", "n8n-nodes-base.httpRequest", parameters, version)])


class NodeRuleTests(unittest.TestCase):
    def check(self, data, limits=None):
        return [item.to_dict() for item in diagnose_nodes(data, "workflow:synthetic", "synthetic.json", limits)]

    def test_modern_header_secret_has_ordinal_evidence_without_value(self):
        data = http({"headerParameters": {"parameters": [{"name": "Authorization", "value": "Bearer SYNTHETIC_PRIVATE"}]}})
        checks = self.check(data)
        self.assertEqual(len(checks), 1)
        check = checks[0]
        self.assertEqual((check["rule_id"], check["severity"], check["assessment"]), ("WF011", "warning", "risk"))
        self.assertEqual(check["evidence_location"], "$.nodes[0].parameters{member:0}{member:0}[0]{member:1}")
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(checks))
        self.assertIn("authenticity is unverified", check["message"])

    def test_legacy_headers_and_sensitive_body_fields(self):
        for version in (1, 2, 3, 4, 4.1, 4.2, 4.3, 4.4, 4.5):
            data = http({"headerParametersUi": {"parameter": [{"name": "X-API-Key", "value": "SYNTHETIC_ONLY"}]},
                         "bodyParameters": {"parameters": [{"name": "password", "value": "SYNTHETIC_ONLY"}]}}, version)
            with self.subTest(version=version):
                self.assertEqual(len(self.check(data)), 2)

    def test_cookie_password_token_authorization_and_secret(self):
        for key in ("Cookie", "password", "access_token", "Authorization", "client_secret", "Proxy-Authorization"):
            checks = self.check(http({key: "SYNTHETIC_ONLY"}))
            self.assertEqual(checks[0]["rule_id"], "WF011")
            self.assertNotIn(key, checks[0]["evidence_location"])

    def test_empty_placeholders_and_pure_variable_references_are_filtered(self):
        for value in (None, "", " ", "<token>", "Bearer <token>", "[REDACTED]", "********", "changeme",
                      "={{ $env.API_KEY }}", "={{ $vars['CONFIG'] }}", "={{ $credentials.apiKey }}"):
            with self.subTest(value=value):
                self.assertEqual(self.check(http({"Authorization": value})), [])

    def test_non_sensitive_headers_are_not_keys(self):
        self.assertEqual(self.check(http({"headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
                                         "tokenEndpoint": "synthetic", "passwordLength": 20})), [])

    def test_general_nodes_and_code_are_not_searched_for_tokens(self):
        data = workflow(nodes=[node("code", "n8n-nodes-base.code", {"password": "SYNTHETIC"})])
        self.assertEqual(self.check(data), [])

    def test_mixed_expressions_and_future_http_versions_remain_unknown(self):
        for value, version in (("={{ 'Bearer SYNTHETIC' + $json.suffix }}", 4.5), ("SYNTHETIC", 99), ({"nested": "value"}, 4)):
            check = self.check(http({"token": value}, version))[0]
            self.assertEqual(check["assessment"], "unknown")
            self.assertEqual(check["confidence"], "low")

    def test_serialized_http_configuration_is_unknown_not_a_confirmed_key(self):
        for key in ("jsonHeaders", "headerParametersJson", "bodyParametersJson", "jsonBody"):
            check = self.check(http({key: '{"token":"SYNTHETIC_ONLY"}'}))[0]
            self.assertEqual(check["status"], "Unknown")
            self.assertNotIn("SYNTHETIC_ONLY", json.dumps(check))

    def test_webhook_versions_and_dynamic_paths(self):
        for version, path, expected in ((1, "synthetic", "risk"), (2.2, "synthetic", "risk"),
                                        (99, "synthetic", "unknown"), (2, "={{ $json.path }}", "unknown")):
            check = self.check(workflow(nodes=[node("hook", "n8n-nodes-base.webhook", {"path": path}, version)]))[0]
            self.assertEqual((check["rule_id"], check["assessment"]), ("WF014", expected))
            self.assertEqual(check["evidence_location"], "$.nodes[0].parameters.path")

    def test_unrecognized_package_is_unknown_and_official_namespaces_are_not_installation_errors(self):
        for kind in ("community.synthetic", "@local/n8n-nodes-demo.node"):
            check = self.check(workflow(nodes=[node("n", kind)]))[0]
            self.assertEqual((check["rule_id"], check["assessment"]), ("WF015", "unknown"))
            self.assertNotIn(kind, json.dumps(check))
        for kind in ("n8n-nodes-base.futureNode", "@n8n/n8n-nodes-langchain.agent"):
            self.assertEqual(self.check(workflow(nodes=[node("n", kind)])), [])

    def test_node_checks_and_traversal_are_bounded(self):
        with self.assertRaises(InputError) as exc:
            self.check(http({"token": "a", "password": "b"}), AnalysisLimits(max_dependencies=1))
        self.assertEqual(exc.exception.code, "ANALYSIS_DIAGNOSTIC_LIMIT")
        with self.assertRaises(InputError) as exc:
            self.check(http({"value": [1, 2, 3]}), AnalysisLimits(max_parameter_values=2))
        self.assertEqual(exc.exception.code, "ANALYSIS_VALUE_LIMIT")

    def test_analysis_adds_checks_preserving_legacy_dependency_risks(self):
        data = http({"token": "SYNTHETIC"})
        report = analyze_documents([("synthetic.json", data)])
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["summary"]["risk_count"], 0)
        self.assertEqual(report["summary"]["total_risk_count"], 1)
        self.assertEqual(report["node_checks"][0]["rule_id"], "WF011")
        self.assertEqual(report["environment_checks"][0]["assessment"], "unknown")
        self.assertEqual(report["compatibility"], "unknown")
        self.assertEqual(report["summary"]["check_count"], len(report["checks"]))

    def test_rule_analysis_is_read_only_and_does_not_perform_io(self):
        data = http({"url": "https://never-access.invalid", "token": "SYNTHETIC"})
        original = copy.deepcopy(data)
        with patch("socket.socket", side_effect=AssertionError("network")), \
                patch("builtins.open", side_effect=AssertionError("file")), \
                patch("builtins.exec", side_effect=AssertionError("code")):
            self.check(data)
        self.assertEqual(data, original)


class StructuralStatisticsTests(unittest.TestCase):
    def test_valid_scan_statistics_are_additive(self):
        data = workflow(connections={"n1": {"main": [[], [{"node": "n2", "type": "main", "index": 1}]]}})
        report = scan_bytes(json.dumps(data).encode())
        self.assertEqual(report["statistics"], {"node_count": 2, "connection_count": 1})
        self.assertEqual(report["findings"], [])

    def test_invalid_json_and_invalid_workflow_have_unknown_counts(self):
        for raw in (b'{"nodes":', b'{"nodes":[],"connections":null}'):
            self.assertIsNone(scan_bytes(raw)["statistics"])
