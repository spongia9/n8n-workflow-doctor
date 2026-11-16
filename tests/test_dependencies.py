"""Version-adapter and reference-extraction regressions, no real credentials."""
import copy
import json
import unittest
from dataclasses import replace

from workflow_doctor.adapters import AdapterRegistry, ExecuteWorkflowAdapter, workflow_reference
from workflow_doctor.dependencies import extract_dependencies
from workflow_doctor.models import AnalysisLimits, InputError
from workflow_doctor.privacy import fingerprint
from test_graphs import node, workflow


def caller(target="B", version=1, source="database"):
    return workflow(nodes=[node("call", "n8n-nodes-base.executeWorkflow",
                                {"source": source, "workflowId": target}, version)])


class DependencyTests(unittest.TestCase):
    def test_legacy_static_subworkflow_and_modern_locator(self):
        for version in (1, 1.1, 1.2, 1.3, 1.4):
            target = "B" if version == 1 else {"__rl": True, "mode": "list", "value": "B", "cachedResultName": "private"}
            with self.subTest(version=version):
                ref = extract_dependencies(caller(target, version))[0]
                self.assertEqual((ref.kind, ref.target, ref.status), ("sub_workflow", "B", "Static"))
                self.assertNotIn("private", json.dumps(ref.to_dict()))

    def test_numeric_ids_and_boolean_not_confused(self):
        self.assertEqual(workflow_reference(7, "$").value, "7")
        self.assertIsNone(workflow_reference(True, "$").value)

    def test_dynamic_reference_is_unknown_and_value_not_serialized(self):
        for target in ("={{ $json.workflowId }}", "{{ 'B' }}", "${PRIVATE}",
                       {"__rl": True, "mode": "id", "value": "={{ $env.PRIVATE }}"}):
            with self.subTest(target=target):
                ref = extract_dependencies(caller(target, 1.2))[0]
                self.assertEqual(ref.status, "Unknown")
                self.assertIsNone(ref.target)
                self.assertIsNone(ref.to_dict()["reference_fingerprint"])

    def test_selector_modes_and_url_parsing_are_local(self):
        for mode in ("id", "list", "url"):
            value = "https://user:synthetic-secret@example.invalid/workflow/B?token=secret" if mode == "url" else "B"
            dep = extract_dependencies(caller({"__rl": True, "mode": mode, "value": value}, 1.4))[0]
            self.assertEqual(dep.target, "B")
            self.assertNotIn("synthetic-secret", json.dumps(dep.to_dict()))

    def test_unknown_version_and_malformed_selector_not_guessed(self):
        for data in (caller("B", 99), caller({"value": "B"}, 1.2),
                     caller({"__rl": True, "mode": "future", "value": "B"}, 1.2),
                     caller({"__rl": True, "mode": "id", "value": "B"}, 1)):
            dep = extract_dependencies(data)[0]
            self.assertEqual(dep.status, "Unknown")
            self.assertIsNone(dep.target)

    def test_non_database_source_not_interpreted_as_workflow_id(self):
        for source in ("localFile", "url", "parameter", "={{ $json.source }}"):
            dep = extract_dependencies(caller("B", 1, source))[0]
            self.assertEqual(dep.status, "Unknown")
            self.assertIsNone(dep.target)

    def test_default_database_source_supported(self):
        data = caller()
        del data["nodes"][0]["parameters"]["source"]
        self.assertEqual(extract_dependencies(data)[0].target, "B")

    def test_registry_extensible_without_assuming_all_node_parameters(self):
        registry = AdapterRegistry([])
        data = caller()
        self.assertEqual(extract_dependencies(data, registry=registry), [])
        registry.register(replace(ExecuteWorkflowAdapter(), versions=(1,)))
        self.assertEqual(extract_dependencies(data, registry=registry)[0].target, "B")

    def test_error_workflow_and_default_sentinel(self):
        data = workflow(settings={"errorWorkflow": "ERR"})
        dep = extract_dependencies(data)[0]
        self.assertEqual((dep.kind, dep.target, dep.location), ("error_workflow", "ERR", "$.settings.errorWorkflow"))
        for sentinel in ("DEFAULT", "", None):
            self.assertEqual(extract_dependencies(workflow(settings={"errorWorkflow": sentinel})), [])

    def test_dynamic_error_workflow_is_unknown(self):
        dep = extract_dependencies(workflow(settings={"errorWorkflow": "={{ $json.errorId }}"}))[0]
        self.assertEqual(dep.status, "Unknown")
        self.assertIsNone(dep.target)

    def test_credential_ids_legacy_names_and_unrecognized_shapes(self):
        data = workflow()
        data["nodes"][0]["credentials"] = {
            "httpHeaderAuth": {"id": "cred1", "name": "synthetic-private-name", "token": "synthetic-private-token"},
            "old": "synthetic-old-name", "missing": {"id": None, "name": "private"}, "invalid": []}
        deps = extract_dependencies(data)
        self.assertEqual(len(deps), 4)
        self.assertEqual(deps[0].reference, fingerprint("credential", "cred1"))
        self.assertEqual(deps[0].status, "Requires Reconfiguration")
        self.assertTrue(all(dep.status == "Unknown" for dep in deps[1:]))
        text = json.dumps([dep.to_dict() for dep in deps])
        for private in ("synthetic-private-name", "synthetic-private-token", "synthetic-old-name", "cred1"):
            self.assertNotIn(private, text)

    def test_environment_and_n8n_variable_syntaxes(self):
        data = workflow(nodes=[node("env", parameters={"value": "={{ $env.API_KEY + $env['SECOND'] + $vars.BASE + _vars.BASE + process.env.THIRD + _env.FOURTH }}"})])
        deps = extract_dependencies(data)
        self.assertEqual([dep.kind for dep in deps].count("environment_variable"), 4)
        self.assertEqual([dep.kind for dep in deps].count("n8n_variable"), 2)
        self.assertTrue(all(dep.reference for dep in deps))
        self.assertNotIn("API_KEY", json.dumps([dep.to_dict() for dep in deps]))

    def test_dynamic_variable_key_not_guessed(self):
        deps = extract_dependencies(workflow(nodes=[node("env", parameters={"value": "={{ $env[$json.key] }}"})]))
        self.assertEqual(deps[0].status, "Unknown")
        self.assertIsNone(deps[0].reference)

    def test_absolute_paths_posix_windows_unc_and_dynamic(self):
        values = ["/srv/private/data.csv", "C:\\private\\data.csv", "\\\\host\\share\\data.csv", "/srv/{{ $json.file }}"]
        deps = extract_dependencies(workflow(nodes=[node("files", parameters={"files": values})]))
        self.assertEqual([dep.form for dep in deps], ["posix_absolute", "windows_absolute", "unc_absolute", "dynamic_path"])
        self.assertEqual(deps[-1].status, "Unknown")
        self.assertNotIn("private", json.dumps([dep.to_dict() for dep in deps]))

    def test_static_services_group_by_origin_without_url_or_headers(self):
        data = workflow(nodes=[node("http", parameters={"url": "https://user:synthetic-secret@example.invalid/private?token=secret#x",
                                                         "other": "https://example.invalid:443/other",
                                                         "headers": {"Authorization": "Bearer synthetic-secret"}})])
        deps = extract_dependencies(data)
        self.assertEqual(len(deps), 2)
        self.assertEqual(deps[0].reference, deps[1].reference)
        text = json.dumps([dep.to_dict() for dep in deps])
        for value in ("synthetic-secret", "example.invalid", "Authorization", "/private"):
            self.assertNotIn(value, text)

    def test_dynamic_and_malformed_endpoint_are_unknown(self):
        for url in ("=https://{{ $json.host }}/api", "https://host.invalid:bad/api"):
            deps = extract_dependencies(workflow(nodes=[node("http", parameters={"url": url})]))
            endpoint = next(dep for dep in deps if dep.kind == "external_service")
            self.assertEqual(endpoint.status, "Unknown")
            self.assertIsNone(endpoint.reference)

    def test_service_scheme_case_and_default_ports_are_normalized(self):
        data = workflow(nodes=[node("http", parameters={"one": "HTTPS://EXAMPLE.INVALID/path",
                                                         "two": "https://example.invalid:443/other"})])
        deps = extract_dependencies(data)
        self.assertEqual(len(deps), 2)
        self.assertEqual(deps[0].reference, deps[1].reference)

    def test_extraction_does_not_modify_input(self):
        data = caller({"__rl": True, "mode": "id", "value": "B"}, 1.2)
        data["unknown"] = {"future": [1, 2]}
        before = copy.deepcopy(data)
        extract_dependencies(data)
        self.assertEqual(before, data)

    def test_dependency_and_parameter_budgets_are_explicit(self):
        data = workflow(nodes=[node("env", parameters={"values": ["$env.ONE", "$env.TWO"]})])
        with self.assertRaises(InputError) as exc:
            extract_dependencies(data, limits=AnalysisLimits(max_dependencies=1))
        self.assertEqual(exc.exception.code, "ANALYSIS_DEPENDENCY_LIMIT")
        with self.assertRaises(InputError) as exc:
            extract_dependencies(data, limits=AnalysisLimits(max_parameter_values=1))
        self.assertEqual(exc.exception.code, "ANALYSIS_VALUE_LIMIT")
