"""Import-set resolution and migration-rule contracts using synthetic inputs."""
import copy
import json
import unittest

from workflow_doctor.analysis import analyze_documents
from workflow_doctor.graphs import downstream, graph_from_json, indirect_dependencies
from workflow_doctor.models import AnalysisLimits, Finding, InputError
from workflow_doctor.privacy import fingerprint
from test_dependencies import caller
from test_graphs import link, node, workflow


def analyze(*objects, limits=None):
    return analyze_documents([(f"file{index}.json", data) for index, data in enumerate(objects)], limits=limits)


class AnalysisTests(unittest.TestCase):
    def test_single_workflow_summary(self):
        report = analyze(workflow(connections={"n1": {"main": [[link("n2")]]}}))
        self.assertEqual(report["summary"]["workflow_count"], 1)
        self.assertEqual(report["summary"]["node_count"], 2)
        self.assertEqual(report["summary"]["connection_count"], 1)
        self.assertEqual(report["summary"]["risk_count"], 0)

    def test_A_calls_B_resolves_by_id_not_workflow_name(self):
        target = workflow("B")
        target["name"] = "a different arbitrary name"
        report = analyze(caller(), target)
        dep = report["dependencies"][0]
        self.assertEqual(dep["status"], "Found In Import Set")
        self.assertEqual(dep["target_workflow_id"], fingerprint("workflow", "B"))
        self.assertEqual(report["risks"][0]["rule_id"], "WF008")
        self.assertEqual(report["compatibility"], "unknown")

    def test_A_B_C_indirect_and_upstream_queries(self):
        middle = caller("C")
        middle["id"] = "B"
        report = analyze(caller("B"), middle, workflow("C"))
        graph = graph_from_json(report["graphs"]["workflow_dependencies"])
        self.assertEqual(indirect_dependencies(graph, fingerprint("workflow", "A")), [fingerprint("workflow", "C")])
        self.assertEqual(len(downstream(graph, fingerprint("workflow", "A"))), 2)
        self.assertEqual(report["summary"]["static_dependency_count"], 2)
        self.assertEqual(report["indirect_dependencies"], [{"workflow_id": fingerprint("workflow", "A"),
                                                          "targets": [fingerprint("workflow", "C")]}])

    def test_missing_is_only_missing_from_import_set(self):
        report = analyze(caller("absent"))
        self.assertEqual(report["missing_resources"][0]["status"], "Missing From Import Set")
        self.assertEqual(report["risks"][0]["status"], "Missing From Import Set")
        self.assertIn("destination existence is unknown", report["risks"][0]["message"])
        self.assertEqual(len(report["graphs"]["workflow_dependencies"]["nodes"]), 2)

    def test_dynamic_reference_has_no_invented_graph_target(self):
        report = analyze(caller("={{ $json.dynamicId }}"))
        self.assertEqual(report["summary"]["unknown_dependency_count"], 1)
        self.assertEqual(report["summary"]["static_dependency_count"], 0)
        self.assertEqual(report["graphs"]["workflow_dependencies"]["edges"], [])
        self.assertIsNone(report["dependencies"][0]["target_workflow_id"])

    def test_error_workflow_found_and_missing_rule(self):
        for objects, expected in (((workflow("A", settings={"errorWorkflow": "ERR"}), workflow("ERR")), "Found In Import Set"),
                                   ((workflow("A", settings={"errorWorkflow": "ERR"}),), "Missing From Import Set")):
            report = analyze(*objects)
            self.assertEqual(report["risks"][0]["rule_id"], "WF009")
            self.assertEqual(report["risks"][0]["status"], expected)
            self.assertIsNone(report["risks"][0]["node_id"])

    def test_all_six_risk_rules_have_required_fields(self):
        data = caller("B")
        data["settings"]["errorWorkflow"] = "ERR"
        data["nodes"][0]["credentials"] = {"test": {"id": "credential1", "name": "private"}}
        data["nodes"][0]["parameters"].update(env="={{ $env.TOKEN }}", file="/srv/private.csv", url="https://shared.invalid/one")
        other = workflow("B", nodes=[node("http", parameters={"url": "https://shared.invalid/two"})])
        report = analyze(data, other)
        self.assertEqual({risk["rule_id"] for risk in report["risks"]}, {"WF008", "WF009", "WF010", "WF012", "WF013", "WF018"})
        for risk in report["risks"]:
            self.assertIsInstance(risk, dict)
            for key in ("rule_id", "severity", "status", "workflow_id", "evidence_location", "message", "recommendation", "confidence"):
                self.assertTrue(risk[key])
            self.assertIn("node_id", risk)
            self.assertIn(risk["confidence"], ("high", "medium", "low"))
            self.assertTrue(risk["dependency_ids"])

    def test_n8n_variable_rule_and_unknown_version_reminder(self):
        data = caller("B", version=999)
        data["nodes"][0]["parameters"]["variable"] = "={{ $vars.BASE }}"
        report = analyze(data, workflow("B"))
        self.assertEqual(report["dependencies"][0]["status"], "Unknown")
        self.assertEqual(report["dependencies"][0]["reference_form"], "unsupported_version")
        self.assertIn("WF012", {risk["rule_id"] for risk in report["risks"]})

    def test_cycle_and_self_reference_are_not_structural_errors(self):
        middle = caller("A")
        middle["id"] = "B"
        report = analyze(caller("B"), middle)
        self.assertTrue(report["graphs"]["workflow_dependencies"]["has_cycles"])
        self.assertTrue(all(risk["severity"] != "error" for risk in report["risks"]))
        self.assertTrue(analyze(caller("A"))["graphs"]["workflow_dependencies"]["has_cycles"])

    def test_node_cycle_is_informational_without_risk_rule(self):
        data = workflow(connections={"n1": {"main": [[link("n2")]]}, "n2": {"main": [[link("n1")]]}})
        report = analyze(data)
        self.assertEqual(report["risks"], [])
        self.assertTrue(report["graphs"]["node_graphs"][0]["has_cycles"])
        self.assertEqual(report["manual_review_items"][0]["code"], "NODE_CYCLE_REVIEW")

    def test_missing_id_uses_explicit_file_identity(self):
        data = workflow()
        del data["id"]
        report = analyze(data)
        record = report["workflows"][0]
        self.assertEqual(record["identity_kind"], "temporary_file_fingerprint")
        self.assertTrue(record["workflow_id"].startswith("file:sha256:"))
        self.assertIsNone(record["n8n_id_fingerprint"])

    def test_duplicate_workflow_ids_are_ambiguous_without_node_collapse(self):
        report = analyze(caller("B"), workflow("B"), workflow("B"))
        self.assertEqual(report["summary"]["workflow_count"], 3)
        self.assertEqual(report["dependencies"][0]["status"], "Ambiguous In Import Set")
        self.assertEqual(len({record["workflow_id"] for record in report["workflows"]}), 3)
        self.assertEqual(report["missing_resources"], [])

    def test_invalid_target_file_is_distinguished_from_missing(self):
        bad = workflow("B")
        bad["nodes"][0]["typeVersion"] = None
        report = analyze(caller("B"), bad)
        self.assertEqual(report["dependencies"][0]["status"], "Invalid In Import Set")
        self.assertEqual(report["coverage"], "partial")
        self.assertEqual(report["summary"]["excluded_file_count"], 1)
        self.assertEqual(report["missing_resources"], [])

    def test_shared_origin_is_only_a_hint_not_proof_of_shared_state(self):
        left = workflow("A", nodes=[node("http1", parameters={"url": "https://shared.invalid/one"})])
        right = workflow("B", nodes=[node("http2", parameters={"url": "https://shared.invalid/two"})])
        report = analyze(left, right)
        risk = report["risks"][0]
        self.assertEqual(risk["rule_id"], "WF018")
        self.assertEqual(len(risk["dependency_ids"]), 2)
        self.assertIn("shared state is unverified", risk["message"])

    def test_unique_endpoint_does_not_trigger_shared_rule(self):
        report = analyze(workflow(nodes=[node("http", parameters={"url": "https://unique.invalid"})]))
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["summary"]["dependency_count"], 1)
        self.assertEqual(report["summary"]["manual_review_count"], 1)

    def test_all_sensitive_values_ids_urls_and_paths_are_opaque(self):
        secret = "SYNTHETIC_PRIVATE_VALUE"
        data = caller(secret)
        data["id"] = secret
        data["nodes"][0].update(id=secret, name=secret)
        data["nodes"][0]["credentials"] = {secret: {"id": secret, "name": secret, "password": secret}}
        data["nodes"][0]["parameters"].update(url=f"https://user:{secret}@{secret}.invalid/{secret}?token={secret}",
                                              path=f"/private/{secret}", header={secret: secret},
                                              env=f"={{ $env.{secret} }}")
        text = json.dumps(analyze(data))
        self.assertNotIn(secret, text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("/private/", text)

    def test_original_objects_and_unknown_fields_unchanged(self):
        data = caller()
        data["future"] = {"any": [1, 2, 3]}
        before = copy.deepcopy(data)
        analyze(data)
        self.assertEqual(data, before)

    def test_global_dependency_graph_and_workflow_budgets(self):
        with self.assertRaises(InputError) as exc:
            analyze(caller("B"), caller("C"), limits=AnalysisLimits(max_dependencies=1))
        self.assertEqual(exc.exception.code, "ANALYSIS_DEPENDENCY_LIMIT")
        with self.assertRaises(InputError):
            analyze(workflow(), limits=AnalysisLimits(max_graph_nodes=1))
        with self.assertRaises(InputError):
            analyze(workflow(), workflow("B"), limits=AnalysisLimits(max_workflows=1))

    def test_analysis_limits_validate_positive_integers(self):
        for field in vars(AnalysisLimits()):
            with self.subTest(field=field), self.assertRaises(ValueError):
                AnalysisLimits(**{field: 0})

    def test_duplicate_source_labels_are_rejected(self):
        with self.assertRaises(InputError) as exc:
            analyze_documents([("same.json", workflow("A")), ("same.json", workflow("B"))])
        self.assertEqual(exc.exception.code, "ANALYSIS_DUPLICATE_SOURCE")

    def test_indirect_report_is_bounded(self):
        objects = []
        for index in range(5):
            data = caller(str(index + 1)) if index < 4 else workflow(str(index))
            data["id"] = str(index)
            objects.append(data)
        with self.assertRaises(InputError) as exc:
            analyze(*objects, limits=AnalysisLimits(max_dependencies=4))
        self.assertEqual(exc.exception.code, "ANALYSIS_QUERY_LIMIT")

    def test_duplicate_id_with_invalid_file_still_ambiguous(self):
        invalid = workflow("B")
        invalid["nodes"] = "invalid"
        report = analyze(caller("B"), workflow("B"), invalid)
        self.assertEqual(report["dependencies"][0]["status"], "Ambiguous In Import Set")

    def test_duplicate_local_node_ids_excluded_without_false_edges(self):
        data = workflow()
        data["nodes"][1]["id"] = data["nodes"][0]["id"]
        report = analyze(data)
        self.assertEqual(report["graphs"]["node_graphs"], [])
        self.assertEqual(report["summary"]["excluded_file_count"], 1)

    def test_old_finding_constructor_and_serialization_unchanged(self):
        finding = Finding("WF002", "error", "reason", "$.nodes")
        self.assertEqual(set(finding.to_dict()), {"rule_id", "severity", "message", "location", "suggestion", "location_details"})
        self.assertEqual(finding.location, "$.nodes")
