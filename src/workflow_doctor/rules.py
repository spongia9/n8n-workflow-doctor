"""WF002-WF005: pure structural checks, independent of I/O and n8n services."""
from __future__ import annotations

import math
from typing import Any

from .models import Finding, InputError


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: Any) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def scan_object(data: Any, max_findings: int = 1000) -> list[Finding]:
    """Check one workflow without changing known or unknown fields.

    Object-member ordinals locate connections without echoing names or key values.
    """
    if type(max_findings) is not int or max_findings <= 0:
        raise ValueError("Finding limit must be a positive integer")
    findings: list[Finding] = []

    def issue(rule, message, location, suggestion, details=None):
        if len(findings) >= max_findings:
            raise InputError("SCAN_FINDING_LIMIT", "Workflow exceeds the diagnostic finding limit", location,
                             "Review the structure or explicitly raise the per-file finding limit.")
        findings.append(Finding(rule, "error", message, location, suggestion, details or {}))

    if not isinstance(data, dict):
        issue("WF002", "Workflow must be a JSON object", "$",
              "Provide one exported workflow object per JSON file.")
        return findings

    nodes, connections = data.get("nodes"), data.get("connections")
    if not isinstance(nodes, list):
        issue("WF002", "Workflow requires nodes (array)", "$.nodes",
              "Export a workflow with a nodes array.")
    if not isinstance(connections, dict):
        issue("WF002", "Workflow requires connections (object)", "$.connections",
              "Export a workflow with a connections object; use {} for no connections.")
    # Server-assigned metadata is optional for clipboard fragments.
    if "name" in data and not _text(data["name"]):
        issue("WF002", "Workflow name must be a non-empty string", "$.name",
              "Supply a non-empty workflow name or omit optional metadata.")
    if "settings" in data and not isinstance(data["settings"], dict):
        issue("WF002", "Workflow settings must be an object", "$.settings",
              "Use a settings object or omit optional settings.")

    names: set[str] = set()
    ids: set[str] = set()
    for index, node in enumerate(nodes if isinstance(nodes, list) else []):
        loc = f"$.nodes[{index}]"
        details = {"node_index": index}
        if not isinstance(node, dict):
            issue("WF002", "Node must be an object", loc,
                  "Replace this entry with an exported node object.", details)
            continue
        for key, seen, duplicate_rule in (("name", names, "WF004"), ("id", ids, "WF003")):
            value = node.get(key)
            if not _text(value):
                issue("WF002", f"Node {key} must be a non-empty string", f"{loc}.{key}",
                      f"Supply a non-empty node {key}.", details)
            elif value in seen:
                issue(duplicate_rule, f"Duplicate node {key}", f"{loc}.{key}",
                      "Assign a unique value and review affected connection references.", details)
            else:
                seen.add(value)
        if not _text(node.get("type")):
            issue("WF002", "Node type must be a non-empty string", loc + ".type",
                  "Supply the exported node type identifier.", details)
        version = node.get("typeVersion")
        if not _number(version) or version <= 0:
            issue("WF002", "Node typeVersion must be a positive finite number", loc + ".typeVersion",
                  "Supply the exported node version; fractional versions are allowed.", details)
        position = node.get("position")
        if not isinstance(position, list) or len(position) != 2 or not all(_number(v) for v in position):
            issue("WF002", "Node position must contain two finite numbers", loc + ".position",
                  "Supply the exported [x, y] canvas position.", details)
        if not isinstance(node.get("parameters"), dict):
            issue("WF002", "Node parameters must be an object", loc + ".parameters",
                  "Use an object for parameters; {} is valid.", details)

    if not isinstance(connections, dict):
        return findings
    for source_index, (source_name, types) in enumerate(connections.items()):
        loc = f"$.connections{{source:{source_index}}}"
        details = {"source_index": source_index}
        if isinstance(nodes, list) and source_name not in names:
            issue("WF005", "Connection source node does not exist", loc,
                  "Remove the stale source or reference an existing unique node name.", details)
        if not isinstance(types, dict):
            issue("WF002", "Connection source must map connection types", loc,
                  "Use an object mapping output types to arrays of output ports.", details)
            continue
        for type_index, (conn_type, ports) in enumerate(types.items()):
            type_loc = f"{loc}{{type:{type_index}}}"
            type_details = dict(details, connection_type_index=type_index)
            if not _text(conn_type):
                issue("WF002", "Connection type key must be a non-empty string", type_loc,
                      "Use an exported connection type identifier.", type_details)
            if not isinstance(ports, list):
                issue("WF002", "Connection type requires an array of output ports", type_loc,
                      "Use one array entry per output port, including empty ports.", type_details)
                continue
            for port_index, links in enumerate(ports):
                port_loc = f"{type_loc}[{port_index}]"
                port_details = dict(type_details, output_index=port_index)
                if links is None:
                    continue
                if not isinstance(links, list):
                    issue("WF002", "Output port must contain an array of links or null", port_loc,
                          "Use a link array, [] or null for this output port.", port_details)
                    continue
                for link_index, link in enumerate(links):
                    link_loc = f"{port_loc}[{link_index}]"
                    link_details = dict(port_details, link_index=link_index)
                    if not isinstance(link, dict):
                        issue("WF002", "Connection link must be an object", link_loc,
                              "Use an object containing node, type and index.", link_details)
                        continue
                    if not _text(link.get("node")):
                        issue("WF002", "Connection target must contain a non-empty node name", link_loc + ".node",
                              "Supply the destination node name.", link_details)
                    elif isinstance(nodes, list) and link["node"] not in names:
                        issue("WF005", "Connection target node does not exist", link_loc + ".node",
                              "Reference an existing unique node name or remove the stale link.", link_details)
                    if not _text(link.get("type")):
                        issue("WF002", "Connection target type must be a non-empty string", link_loc + ".type",
                              "Supply the exported destination input type.", link_details)
                    if type(link.get("index")) is not int or link["index"] < 0:
                        issue("WF002", "Connection input index must be a nonnegative integer", link_loc + ".index",
                              "Use a zero-based destination input index; booleans are invalid.", link_details)
    return findings
