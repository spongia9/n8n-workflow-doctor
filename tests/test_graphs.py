"""Graph regressions use wholly fabricated workflows."""
import copy
import json
import unittest

import networkx as nx

from workflow_doctor.graphs import (build_node_graph, cycle_components, dependency_path,
                                   downstream, export_graph, indirect_dependencies, upstream)
from workflow_doctor.models import InputError
from workflow_doctor.privacy import fingerprint


def node(node_id, kind="n8n-nodes-base.noOp", parameters=None, version=1):
    return {"id": node_id, "name": node_id, "type": kind, "typeVersion": version,
            "position": [0, 0], "parameters": parameters or {}}


def workflow(workflow_id="A", nodes=None, connections=None, settings=None):
    return {"id": workflow_id, "nodes": nodes if nodes is not None else [node("n1"), node("n2")],
            "connections": connections or {}, "settings": settings or {}}


def link(target, index=0, kind="main"):
    return {"node": target, "index": index, "type": kind}


class GraphTests(unittest.TestCase):
    def test_normal_node_graph_and_json_export(self):
        data = workflow(connections={"n1": {"main": [[link("n2")]]}})
        graph = build_node_graph(data)
        self.assertIsInstance(graph, nx.MultiDiGraph)
        self.assertEqual((len(graph), graph.number_of_edges()), (2, 1))
        self.assertEqual(len(json.loads(json.dumps(export_graph(graph)))["edges"]), 1)

    def test_multibranch_parallel_edges_null_and_unused_ports(self):
        graph = build_node_graph(workflow(connections={"n1": {"main": [None, [], [link("n2"), link("n2", 3)], [link("n2", 1)]]}}))
        edges = list(graph.edges(data=True))
        self.assertEqual([edge[2]["output_index"] for edge in edges], [2, 2, 3])
        self.assertEqual([edge[2]["input_index"] for edge in edges], [0, 3, 1])
        self.assertEqual(len(export_graph(graph)["output_ports"]), 4)

    def test_connection_type_metadata_survives(self):
        graph = build_node_graph(workflow(connections={"n1": {"ai_tool": [[link("n2", kind="ai_tool")]],
                                                              "unknown-private-type": [[link("n2", kind="unknown-private-type")]]}}))
        exported = export_graph(graph)
        self.assertEqual(exported["edges"][0]["source_type"], "ai_tool")
        self.assertTrue(exported["edges"][1]["source_type"].startswith("connection-type:sha256:"))
        self.assertNotIn("unknown-private-type", json.dumps(exported))

    def test_upstream_downstream_indirect_and_path(self):
        graph = nx.MultiDiGraph([("A", "B"), ("B", "C")])
        self.assertEqual(downstream(graph, "A"), ["B", "C"])
        self.assertEqual(downstream(graph, "A", False), ["B"])
        self.assertEqual(upstream(graph, "C"), ["A", "B"])
        self.assertEqual(upstream(graph, "C", False), ["B"])
        self.assertEqual(indirect_dependencies(graph, "A"), ["C"])
        self.assertEqual(dependency_path(graph, "A", "C"), ["A", "B", "C"])
        self.assertEqual(dependency_path(graph, "C", "A"), [])

    def test_cycles_self_loops_and_queries_terminate(self):
        graph = nx.MultiDiGraph([("A", "B"), ("B", "A"), ("C", "C")])
        self.assertEqual(cycle_components(graph), [["A", "B"], ["C"]])
        self.assertEqual(downstream(graph, "A"), ["B"])
        self.assertEqual(upstream(graph, "C"), [])
        self.assertTrue(export_graph(graph)["has_cycles"])

    def test_invalid_graph_not_silently_approximated(self):
        with self.assertRaises(InputError):
            build_node_graph(workflow(connections={"n1": {"main": [[link("absent")]]}}))

    def test_graph_budgets_include_empty_ports(self):
        with self.assertRaises(InputError):
            build_node_graph(workflow(), max_nodes=1)
        with self.assertRaises(InputError):
            build_node_graph(workflow(connections={"n1": {"main": [[], [], []]}}), max_edges=2)

    def test_graph_does_not_modify_objects_or_echo_names(self):
        data = workflow()
        data["nodes"][0]["name"] = "synthetic-private-name"
        data["nodes"][0]["parameters"] = {"token": "synthetic-secret"}
        before = copy.deepcopy(data)
        exported = export_graph(build_node_graph(data))
        self.assertEqual(data, before)
        self.assertNotIn("synthetic-private-name", json.dumps(exported))
        self.assertNotIn("synthetic-secret", json.dumps(exported))
        self.assertEqual(exported["nodes"][0]["node_id"], fingerprint("node", "n1"))

    def test_unknown_query_node_is_explicit(self):
        graph = nx.MultiDiGraph()
        for query in (upstream, downstream, indirect_dependencies):
            with self.assertRaises(ValueError):
                query(graph, "missing")
        with self.assertRaises(ValueError):
            dependency_path(graph, "missing", "also missing")
