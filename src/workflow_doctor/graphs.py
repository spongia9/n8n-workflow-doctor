"""NetworkX multigraphs, cycle facts and bounded graph JSON without raw inputs."""
from __future__ import annotations

import networkx as nx
from dataclasses import dataclass, field

from .models import InputError
from .privacy import connection_type, fingerprint
from .rules import scan_object


@dataclass(frozen=True)
class NodeMetadata:
    """Exact source identity for local queries, excluded from default exports/repr."""
    node_id: str = field(repr=False)
    name: str = field(repr=False)
    node_type: str = field(repr=False)


def node_metadata(graph: nx.MultiDiGraph, node: str) -> NodeMetadata | None:
    """Local inspection only; a restored redacted graph has no raw metadata."""
    if node not in graph:
        raise ValueError("Query node is not in the graph")
    return graph.nodes[node].get("_metadata")


def check_graph_budget(node_count: int, edge_count: int, max_nodes: int, max_edges: int):
    if node_count > max_nodes or edge_count > max_edges:
        raise InputError("ANALYSIS_GRAPH_LIMIT", "Graph exceeds the node or edge limit",
                         suggestion="Split the import set or explicitly raise the analysis graph limits.")


def build_node_graph(data: dict, max_nodes: int = 100_000, max_edges: int = 200_000) -> nx.MultiDiGraph:
    """Build only validated graphs. Parallel edges and unconnected ports survive."""
    if scan_object(data):
        raise InputError("ANALYSIS_INVALID_STRUCTURE", "Node graph requires a structurally valid workflow")
    check_graph_budget(len(data["nodes"]), 0, max_nodes, max_edges)
    graph = nx.MultiDiGraph()
    names = {}
    for index, node in enumerate(data["nodes"]):
        key = fingerprint("node", node["id"])
        graph.add_node(key, node_id=key, node_index=index, location=f"$.nodes[{index}]",
                       _metadata=NodeMetadata(node["id"], node["name"], node["type"]))
        names[node["name"]] = key
    graph.graph["output_ports"] = []
    edge_count = 0
    for source_index, (name, types) in enumerate(data["connections"].items()):
        for type_index, (kind, ports) in enumerate(types.items()):
            for output_index, links in enumerate(ports):
                loc = f"$.connections{{source:{source_index}}}{{type:{type_index}}}[{output_index}]"
                graph.graph["output_ports"].append({
                    "source": names[name], "source_type": connection_type(kind), "output_index": output_index,
                    "empty_form": "null" if links is None else ("array" if not links else None), "location": loc})
                # Port records consume graph budget too, even for null ports.
                check_graph_budget(len(graph), len(graph.graph["output_ports"]), max_nodes, max_edges)
                for link_index, link in enumerate(links or []):
                    edge_count += 1
                    check_graph_budget(len(graph), edge_count, max_nodes, max_edges)
                    graph.add_edge(names[name], names[link["node"]], key=edge_count - 1,
                                   source_type=connection_type(kind), target_type=connection_type(link["type"]),
                                   output_index=output_index, input_index=link["index"],
                                   location=f"{loc}[{link_index}]")
    return graph


def cycle_components(graph: nx.MultiDiGraph) -> list[list[str]]:
    """Strongly connected groups, not exponential enumeration of simple cycles."""
    return sorted(sorted(group) for group in nx.strongly_connected_components(graph)
                  if len(group) > 1 or any(graph.has_edge(node, node) for node in group))


def upstream(graph: nx.MultiDiGraph, node: str, transitive: bool = True) -> list[str]:
    if node not in graph:
        raise ValueError("Query node is not in the graph")
    values = nx.ancestors(graph, node) if transitive else set(graph.predecessors(node))
    return sorted(set(values) - {node})


def downstream(graph: nx.MultiDiGraph, node: str, transitive: bool = True) -> list[str]:
    if node not in graph:
        raise ValueError("Query node is not in the graph")
    values = nx.descendants(graph, node) if transitive else set(graph.successors(node))
    return sorted(set(values) - {node})


def indirect_dependencies(graph: nx.MultiDiGraph, node: str) -> list[str]:
    """Reachable nodes excluding self and direct neighbors."""
    return sorted(set(downstream(graph, node)) - set(downstream(graph, node, False)))


def dependency_path(graph: nx.MultiDiGraph, source: str, target: str) -> list[str]:
    if source not in graph or target not in graph:
        raise ValueError("Query node is not in the graph")
    try:
        return nx.shortest_path(graph, source, target)
    except nx.NetworkXNoPath:
        return []


def export_graph(graph: nx.MultiDiGraph) -> dict:
    cycles = cycle_components(graph)
    nodes = []
    for node, attrs in graph.nodes(data=True):
        public = {key: value for key, value in attrs.items() if not key.startswith("_")}
        metadata = attrs.get("_metadata")
        if metadata is not None:
            public["name_fingerprint"] = fingerprint("node-name", metadata.name)
            public["type_fingerprint"] = fingerprint("node-type", metadata.node_type)
            public["metadata_policy"] = "source identity retained locally; exported as fingerprints"
        nodes.append({"id": node, **public})
    return {"directed": True, "multigraph": True,
            "nodes": nodes,
            "edges": [{"source": source, "target": target, "key": key, **attrs}
                      for source, target, key, attrs in graph.edges(keys=True, data=True)],
            "output_ports": graph.graph.get("output_ports", []),
            "cyclic_components": cycles, "has_cycles": bool(cycles)}


def graph_from_json(data: dict) -> nx.MultiDiGraph:
    """Restore our exported graph for queries; not a sanitizer for arbitrary JSON."""
    graph = nx.MultiDiGraph()
    for node in data["nodes"]:
        graph.add_node(node["id"], **{key: value for key, value in node.items() if key != "id"})
    for edge in data["edges"]:
        graph.add_edge(edge["source"], edge["target"], key=edge["key"],
                       **{key: value for key, value in edge.items() if key not in ("source", "target", "key")})
    graph.graph["output_ports"] = data.get("output_ports", [])
    return graph
