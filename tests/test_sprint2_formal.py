"""Incremental formal Sprint 2 coverage, using fabricated inputs only."""
import copy
import json
import sys
import tomllib
import unittest
import io
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
from unittest.mock import patch
from pathlib import Path

from workflow_doctor.graphs import build_node_graph, export_graph, graph_from_json, node_metadata
from workflow_doctor.privacy import fingerprint
from test_graphs import node, workflow
from test_dependencies import caller
from workflow_doctor.adapters import workflow_reference
from workflow_doctor.dependencies import extract_dependencies
from workflow_doctor.analysis import analyze_documents
from workflow_doctor.reporting import to_markdown
from workflow_doctor.scanner import make_report
from workflow_doctor.scanner import analyze_path
from workflow_doctor.cli import main
from workflow_doctor.models import AnalysisLimits, InputError

FORMAL_FIXTURES = Path("examples/sprint2-formal/workflows")


class FormalFixtureTests(unittest.TestCase):
    def test_fresh_fixture_chain_cycle_and_missing_import_target(self):
        report = analyze_path(FORMAL_FIXTURES)
        self.assertTrue(report["complete"])
        self.assertEqual(report["finding_count"], 0)
        analysis = report["analysis"]
        self.assertEqual(analysis["summary"]["workflow_count"], 4)
        self.assertEqual(analysis["summary"]["node_count"], 13)
        self.assertEqual(analysis["summary"]["connection_count"], 6)
        self.assertEqual(analysis["summary"]["direct_dependency_count"], 5)
        self.assertEqual(analysis["summary"]["unknown_dependency_count"], 4)
        self.assertEqual(analysis["summary"]["missing_resource_count"], 1)
        self.assertTrue(analysis["graphs"]["workflow_dependencies"]["has_cycles"])
        self.assertTrue(analysis["indirect_dependencies"])
        self.assertEqual({risk["rule_id"] for risk in analysis["risks"]}, {"WF008", "WF009", "WF010", "WF012", "WF013", "WF018"})

    def test_dynamic_file_embedded_and_future_calls_have_no_fabricated_edges(self):
        analysis = analyze_path(FORMAL_FIXTURES)["analysis"]
        unknown = analysis["unknown_dependencies"]
        self.assertEqual({item["reference_form"] for item in unknown},
                         {"dynamic_expression", "local_file", "embedded_workflow", "unsupported_version"})
        self.assertTrue(all(item["target_workflow_id"] is None for item in unknown))
        self.assertEqual(analysis["assessment_counts"]["not_applicable"], 3)

    def test_unknown_community_node_type_is_preserved_locally(self):
        data = json.loads((FORMAL_FIXTURES / "A.json").read_text(encoding="utf-8"))
        graph = build_node_graph(data)
        metadata = node_metadata(graph, fingerprint("node", "future-A"))
        self.assertEqual(metadata.node_type, "community.syntheticFutureNode")
        self.assertNotIn("community.syntheticFutureNode", json.dumps(export_graph(graph)))

    def test_all_fixture_hashes_unchanged_and_references_never_opened(self):
        paths = sorted(FORMAL_FIXTURES.glob("*.json"))
        before = {path: sha256(path.read_bytes()).hexdigest() for path in paths}
        objects = [(str(path), json.loads(path.read_bytes())) for path in paths]
        original = copy.deepcopy(objects)
        with patch("pathlib.Path.open", side_effect=AssertionError("referenced file must not be read")), \
                patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            report = analyze_documents(objects)
        self.assertEqual(report["summary"]["workflow_count"], 4)
        self.assertEqual(objects, original)
        self.assertEqual(before, {path: sha256(path.read_bytes()).hexdigest() for path in paths})

    def test_four_cli_formats_default_to_private_metadata(self):
        for fmt in ("json", "markdown", "graph-json", "text"):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                code = main(["analyze", str(FORMAL_FIXTURES), "--format", fmt])
            self.assertEqual(code, 1)
            for sensitive in ("SYNTHETIC_FORMAL_VALUE", "FORMAL_REFERENCE_ONLY", "S2_CONFIG", "formal.example.invalid"):
                self.assertNotIn(sensitive, output.getvalue() + errors.getvalue())
            if fmt == "json":
                self.assertEqual(json.loads(output.getvalue())["analysis"]["schema_version"], "1.1")
            if fmt == "markdown":
                self.assertIn("Credential checklist", output.getvalue())
                self.assertIn("not\\_applicable", output.getvalue())


class AssessmentAndReportTests(unittest.TestCase):
    def test_blocking_diagnostics_are_bounded_without_partial_success(self):
        data = workflow()
        for item in data["nodes"]:
            item["type"] = None
        with self.assertRaises(InputError) as exc:
            analyze_documents([("invalid.json", data)], limits=AnalysisLimits(max_dependencies=1))
        self.assertEqual(exc.exception.code, "ANALYSIS_DIAGNOSTIC_LIMIT")

    def analyze(self, *values):
        return analyze_documents([(f"synthetic-{i}.json", value) for i, value in enumerate(values)])

    def test_all_five_assessments_have_scoped_evidence(self):
        data = caller("B")
        data["settings"] = {"errorWorkflow": "DEFAULT"}
        data["nodes"].extend([
            node("missing", "n8n-nodes-base.executeWorkflow", {"workflowId": "D"}),
            node("dynamic", "n8n-nodes-base.executeWorkflow", {"workflowId": "={{ $json.id }}"}),
            node("invalid", "n8n-nodes-base.executeWorkflow", {"workflowId": "C"}),
        ])
        bad = workflow("C")
        bad["nodes"][0].pop("type")
        report = self.analyze(data, workflow("B"), bad)
        self.assertEqual({item["assessment"] for item in report["checks"]},
                         {"verified", "blocked", "risk", "unknown", "not_applicable"})
        self.assertTrue(all(count > 0 for count in report["assessment_counts"].values()))
        self.assertTrue(all(item["evidence_location"] and item["verification_scope"] == "static_input_only" for item in report["checks"]))
        self.assertEqual(report["compatibility"], "unknown")
        self.assertEqual(report["missing_resources"][0]["status"], "Missing From Import Set")

    def test_default_is_not_a_workflow_id_or_migration_risk(self):
        report = self.analyze(workflow(settings={"errorWorkflow": "DEFAULT"}))
        self.assertEqual(report["dependencies"], [])
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["checks"][0]["assessment"], "not_applicable")
        self.assertEqual(report["checks"][0]["rule_id"], "WF009")

    def test_direct_indirect_and_configuration_checklists(self):
        a = caller("B")
        a["nodes"][0]["credentials"] = {"syntheticAuth": {"id": "ref-id", "name": "Ref name"}}
        a["nodes"][0]["parameters"]["value"] = "={{ $vars.BASE + $env.CONFIG }}"
        b = caller("C")
        b["id"] = "B"
        report = self.analyze(a, b, workflow("C"))
        self.assertEqual(report["summary"]["direct_dependency_count"], 2)
        self.assertEqual(report["summary"]["indirect_dependency_count"], 1)
        self.assertEqual(len(report["credential_checklist"]), 1)
        self.assertEqual(len(report["variable_checklist"]), 2)
        self.assertIsNotNone(report["credential_checklist"][0]["credential_reference"]["type_fingerprint"])
        envelope = make_report()
        envelope["analysis"] = report
        markdown = to_markdown(envelope)
        for heading in ("Direct cross-workflow dependencies", "Credential checklist", "Variable checklist", "Assessment checks"):
            self.assertIn(heading, markdown)

    def test_blocked_structure_is_separate_from_migration_risks(self):
        data = workflow()
        data["nodes"][0]["type"] = None
        report = self.analyze(data)
        self.assertEqual(report["risks"], [])
        self.assertEqual(report["blocking_issues"][0]["assessment"], "blocked")
        self.assertEqual(report["blocking_issues"][0]["rule_id"], "WF002")
        self.assertEqual(report["summary"]["blocking_issue_count"], 1)


class ReferenceDetailTests(unittest.TestCase):
    def test_credential_type_id_name_are_extracted_but_exported_as_fingerprints(self):
        data = workflow()
        data["nodes"][0]["credentials"] = {"syntheticAuth": {"id": "synthetic-id", "name": "Synthetic name", "token": "NEVER_EXPORT_TOKEN"}}
        dep = extract_dependencies(data)[0]
        self.assertEqual((dep.credential.credential_type, dep.credential.credential_id, dep.credential.name),
                         ("syntheticAuth", "synthetic-id", "Synthetic name"))
        details = dep.to_dict()["credential_reference"]
        self.assertEqual(details["type_fingerprint"], fingerprint("credential-type", "syntheticAuth"))
        self.assertEqual(details["id_fingerprint"], fingerprint("credential", "synthetic-id"))
        self.assertEqual(details["name_fingerprint"], fingerprint("credential-name", "Synthetic name"))
        for value in ("syntheticAuth", "synthetic-id", "Synthetic name", "NEVER_EXPORT_TOKEN"):
            self.assertNotIn(value, json.dumps(dep.to_dict()))
            self.assertNotIn(value, repr(dep))

    def test_name_only_credential_remains_unknown_with_name_evidence(self):
        data = workflow()
        data["nodes"][0]["credentials"] = {"legacyAuth": "Synthetic legacy name"}
        dep = extract_dependencies(data)[0]
        self.assertEqual(dep.status, "Unknown")
        self.assertIsNone(dep.reference)
        self.assertEqual(dep.credential.name, "Synthetic legacy name")
        self.assertIsNotNone(dep.to_dict()["credential_reference"]["name_fingerprint"])

    def test_file_workflow_relative_path_is_explicit_without_reading_it(self):
        data = caller("must-not-be-used", version=1, source="localFile")
        data["nodes"][0]["parameters"]["workflowPath"] = "private-child.json"
        deps = extract_dependencies(data)
        call = next(dep for dep in deps if dep.kind == "sub_workflow")
        path = next(dep for dep in deps if dep.kind == "local_path")
        self.assertEqual((call.source_kind, call.form, call.status), ("local_file", "local_file", "Unknown"))
        self.assertIsNone(call.target)
        self.assertEqual(path.form, "relative_workflow_file")
        self.assertEqual(path.location, "$.nodes[0].parameters.workflowPath")

    def test_absolute_workflow_file_is_not_counted_twice(self):
        data = caller(version=1.1, source="localFile")
        data["nodes"][0]["parameters"]["workflowPath"] = "/srv/synthetic.json"
        deps = extract_dependencies(data)
        self.assertEqual(len([dep for dep in deps if dep.kind == "local_path"]), 1)

    def test_embedded_workflow_never_becomes_database_id(self):
        for value in ('{"id":"B","nodes":[],"connections":{}}', "={{ $json.workflow }}"):
            data = caller("B", version=1.4, source="parameter")
            data["nodes"][0]["parameters"]["workflowJson"] = value
            dep = extract_dependencies(data)[0]
            self.assertEqual(dep.source_kind, "parameter")
            self.assertEqual(dep.status, "Unknown")
            self.assertIsNone(dep.target)
            self.assertTrue(dep.location.endswith(".workflowJson"))
            self.assertNotIn(value, json.dumps(dep.to_dict()))

    def test_remote_and_unsupported_sources_stay_unknown(self):
        old = extract_dependencies(caller(version=1, source="url"))[0]
        new = extract_dependencies(caller(version=1.4, source="localFile"))[0]
        self.assertEqual(old.source_kind, "remote_url")
        self.assertEqual(new.source_kind, "unsupported")
        self.assertEqual(old.status, "Unknown")
        self.assertEqual(new.status, "Unknown")

    def test_unconfigured_reference_never_becomes_static_id(self):
        for value in (None, "", "DEFAULT"):
            ref = workflow_reference(value, "$")
            self.assertIsNone(ref.value)
            self.assertEqual(ref.form, "unset")

    def test_variable_names_do_not_match_inside_other_identifiers(self):
        data = workflow(nodes=[node("code", parameters={"text": "custom_env.KEY myprocess.env.KEY custom_vars.NAME custom.process.env.KEY"})])
        self.assertEqual(extract_dependencies(data), [])

    def test_mismatched_quotes_do_not_create_a_static_variable(self):
        data = workflow(nodes=[node("code", parameters={"text": "={{ $env['NAME\"] }}"})])
        dep = extract_dependencies(data)[0]
        self.assertEqual(dep.status, "Unknown")
        self.assertIsNone(dep.reference)


class RuntimeAndMetadataTests(unittest.TestCase):
    def test_formal_runtime_and_declared_dependency_agree(self):
        project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["requires-python"], ">=3.12,<3.13")
        self.assertIn("networkx>=3.7,<4", project["dependencies"])
        self.assertEqual(sys.version_info[:2], (3, 12))

    def test_original_id_name_type_retained_in_memory(self):
        data = workflow(nodes=[node("source-id", "community.unknownNode", version=99)])
        data["nodes"][0]["name"] = "Synthetic display name"
        original = copy.deepcopy(data)
        graph = build_node_graph(data)
        metadata = node_metadata(graph, fingerprint("node", "source-id"))
        self.assertEqual((metadata.node_id, metadata.name, metadata.node_type),
                         ("source-id", "Synthetic display name", "community.unknownNode"))
        self.assertEqual(data, original)

    def test_default_graph_export_never_serializes_raw_metadata(self):
        secret = "SYNTHETIC_PRIVATE_GRAPH_VALUE"
        data = workflow(nodes=[node(secret, secret)])
        graph = build_node_graph(data)
        exported = export_graph(graph)
        self.assertNotIn(secret, json.dumps(exported))
        self.assertNotIn(secret, repr(graph.nodes[fingerprint("node", secret)]))
        self.assertEqual(exported["nodes"][0]["name_fingerprint"], fingerprint("node-name", secret))
        self.assertEqual(exported["nodes"][0]["type_fingerprint"], fingerprint("node-type", secret))
        restored = graph_from_json(exported)
        self.assertIsNone(node_metadata(restored, fingerprint("node", secret)))
        self.assertEqual(export_graph(restored), exported)
