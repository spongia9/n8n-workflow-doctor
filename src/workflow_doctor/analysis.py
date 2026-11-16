"""Offline import-set analysis, with explicit ambiguity and coverage boundaries."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import networkx as nx

from .adapters import AdapterRegistry
from .dependencies import extract_dependencies
from .graphs import build_node_graph, check_graph_budget, export_graph, indirect_dependencies
from .migration_rules import diagnose_dependencies
from .models import AnalysisLimits, Finding, InputError, RiskFinding
from .node_rules import diagnose_nodes, environment_check
from .privacy import fingerprint, static_id
from .rules import scan_object


def analyze_documents(documents: list[tuple[str, Any]], limits: AnalysisLimits | None = None,
                      registry: AdapterRegistry | None = None, *,
                      parse_findings: dict[str, list[Finding]] | None = None) -> dict:
    """Return serializable analysis; sources are visible caller-provided metadata.

    Raw IDs are used only to resolve references internally. Exported stable IDs
    are fingerprints, and file fallbacks are explicitly marked temporary.
    """
    limits = limits or AnalysisLimits()
    if len(documents) > limits.max_workflows:
        raise InputError("ANALYSIS_WORKFLOW_LIMIT", "Workflow input count exceeds the analysis limit")
    if len({source for source, _ in documents}) != len(documents):
        raise InputError("ANALYSIS_DUPLICATE_SOURCE", "Analysis sources must have unique file identifiers")
    declared_ids = [static_id(data.get("id")) if isinstance(data, dict) else None for _, data in documents]
    id_counts = Counter(value for value in declared_ids if value is not None)
    records, excluded, lookup = [], [], defaultdict(list)
    cross_graph = nx.MultiDiGraph()
    node_graphs, dependencies = [], []
    total_nodes = total_edges = total_ports = 0
    manual = []
    blocking, not_applicable = [], []
    node_checks, environment_checks = [], []

    for (source, data), declared_id in zip(documents, declared_ids):
        findings = (parse_findings or {}).get(source) or scan_object(data)
        if findings:
            if len(blocking) + len(findings) > limits.max_dependencies:
                raise InputError("ANALYSIS_DIAGNOSTIC_LIMIT", "Structural analysis checks exceed the diagnostic limit")
            workflow_key = fingerprint("workflow", declared_id) if declared_id is not None and id_counts[declared_id] == 1 else fingerprint("file", source)
            for finding in findings:
                blocking.append(RiskFinding(finding.rule_id, "error", "Invalid Structure", workflow_key, None,
                                            finding.location, finding.message, finding.suggestion, "high", source,
                                            assessment="blocked").to_dict())
            excluded.append({"file": source, "reason": "Invalid workflow structure; analysis omitted"})
            if declared_id is not None:
                lookup[declared_id].append(None)
            continue
        unique = declared_id is not None and id_counts[declared_id] == 1
        key = fingerprint("workflow", declared_id) if unique else fingerprint("file", source)
        identity_kind = "n8n_id_fingerprint" if unique else "temporary_file_fingerprint"
        identity_status = "unique" if unique else ("duplicate_id" if declared_id is not None else "missing_or_dynamic_id")
        record = {"workflow_id": key, "identity_kind": identity_kind, "identity_status": identity_status,
                  "n8n_id_fingerprint": fingerprint("workflow", declared_id) if declared_id is not None else None,
                  "file": source}
        records.append(record)
        extracted_checks = diagnose_nodes(data, key, source, limits)
        if len(node_checks) + len(extracted_checks) > limits.max_dependencies:
            raise InputError("ANALYSIS_DIAGNOSTIC_LIMIT", "Import-set node checks exceed the diagnostic limit")
        node_checks.extend(check.to_dict() for check in extracted_checks)
        environment_checks.append(environment_check(key, source).to_dict())
        if data.get("settings", {}).get("errorWorkflow") in (None, "", "DEFAULT"):
            not_applicable.append(RiskFinding("WF009", "info", "Not Applicable", key, None,
                                             "$.settings.errorWorkflow", "No explicit external Error Workflow is configured",
                                             "No external Error Workflow ID mapping is applicable to this setting.",
                                             "high", source, assessment="not_applicable").to_dict())
        if declared_id is not None:
            lookup[declared_id].append(key)
        cross_graph.add_node(key, **record, import_status="Included")
        if not unique:
            manual.append({"code": "WORKFLOW_IDENTITY_REVIEW", "workflow_id": key, "file": source,
                           "evidence_location": "$.id", "status": "Unknown",
                           "message": "Workflow has a missing, dynamic or duplicate ID; temporary file identity is used."})
        graph = build_node_graph(data, limits.max_graph_nodes, limits.max_graph_edges)
        exported = export_graph(graph)
        total_nodes += len(graph)
        total_edges += graph.number_of_edges()
        total_ports += len(exported["output_ports"])
        check_graph_budget(total_nodes, total_edges + total_ports, limits.max_graph_nodes, limits.max_graph_edges)
        node_graphs.append({"workflow_id": key, "file": source, **exported})
        if exported["has_cycles"]:
            manual.append({"code": "NODE_CYCLE_REVIEW", "workflow_id": key, "file": source,
                           "evidence_location": "$.connections", "status": "Informational",
                           "message": "Node graph contains a cyclic component; cycles can be intentional and are not errors."})
        extracted = extract_dependencies(data, limits, registry)
        if len(dependencies) + len(extracted) > limits.max_dependencies:
            raise InputError("ANALYSIS_DEPENDENCY_LIMIT", "Import-set dependency count exceeds the analysis limit")
        for dep in extracted:
            dep.dependency_id = f"dependency:{len(dependencies)}"
            dep.workflow_id, dep.file = key, source
            dependencies.append(dep)

    for dep in dependencies:
        if dep.kind not in ("sub_workflow", "error_workflow") or dep.target is None:
            continue
        candidates = lookup[dep.target]
        if len(candidates) == 1 and candidates[0] is not None:
            dep.status, target_key = "Found In Import Set", candidates[0]
        else:
            dep.status = ("Missing From Import Set" if not candidates else
                          "Ambiguous In Import Set" if len(candidates) > 1 else "Invalid In Import Set")
            target_key = fingerprint("unresolved-workflow", dep.target)
            cross_graph.add_node(target_key, workflow_id=target_key, identity_kind="n8n_reference_fingerprint",
                                 import_status=dep.status)
        dep.target_workflow_id = target_key
        cross_graph.add_edge(dep.workflow_id, target_key, key=dep.dependency_id, kind=dep.kind,
                             dependency_id=dep.dependency_id, node_id=dep.node_id,
                             evidence_location=dep.location, status=dep.status, confidence=dep.confidence)
        check_graph_budget(total_nodes + len(cross_graph), total_edges + total_ports + cross_graph.number_of_edges(),
                           limits.max_graph_nodes, limits.max_graph_edges)

    # This check also covers workflows without any cross-workflow edges.
    check_graph_budget(total_nodes + len(cross_graph), total_edges + total_ports + cross_graph.number_of_edges(),
                       limits.max_graph_nodes, limits.max_graph_edges)
    cross_export = export_graph(cross_graph)
    indirect, reachability_count = [], 0
    for record in records:
        targets = indirect_dependencies(cross_graph, record["workflow_id"])
        reachability_count += len(targets)
        if reachability_count > limits.max_dependencies:
            raise InputError("ANALYSIS_QUERY_LIMIT", "Indirect dependency result count exceeds the analysis dependency limit",
                             suggestion="Split the import set or raise the analysis dependency limit.")
        if targets:
            indirect.append({"workflow_id": record["workflow_id"], "targets": targets})
    if cross_export["has_cycles"]:
        manual.append({"code": "WORKFLOW_CYCLE_REVIEW", "workflow_id": None, "evidence_location": "$",
                       "status": "Informational", "message": "Workflow references contain a cycle; review intended recursion and termination without assuming an error."})
    risks = [risk.to_dict() for risk in diagnose_dependencies(dependencies)]
    serialized = [dep.to_dict() for dep in dependencies]
    unknown = [dep for dep in serialized if dep["status"] in ("Unknown", "Ambiguous In Import Set")]
    missing = [dep for dep in serialized if dep["status"] == "Missing From Import Set"]
    direct = [dep for dep in serialized if dep["target_workflow_id"] is not None]
    credential_checklist = [dep for dep in serialized if dep["kind"] == "credential"]
    variable_checklist = [dep for dep in serialized if dep["kind"] in ("environment_variable", "n8n_variable")]
    checks = risks + blocking + not_applicable + node_checks + environment_checks
    assessments = {kind: 0 for kind in ("verified", "blocked", "risk", "unknown", "not_applicable")}
    for check in checks:
        assessments[check["assessment"]] += 1
    for dep in serialized:
        manual.append({"code": "DEPENDENCY_REVIEW", "dependency_id": dep["id"], "workflow_id": dep["workflow_id"],
                       "node_id": dep["node_id"], "file": dep["file"], "evidence_location": dep["evidence_location"],
                       "status": dep["status"], "message": dep["reason"]})
    additional_review = [{"code": "NODE_OR_ENVIRONMENT_REVIEW", "workflow_id": check["workflow_id"],
                          "node_id": check["node_id"], "file": check["file"],
                          "evidence_location": check["evidence_location"], "status": check["status"],
                          "message": check["message"], "recommendation": check["recommendation"]}
                         for check in node_checks + environment_checks]
    result = {"schema_version": "1.1", "compatibility": "unknown",
            "identity_policy": "Stable fingerprints of n8n IDs; explicitly temporary file fingerprints when unavailable or ambiguous",
            "coverage": "partial" if excluded else "structurally_valid_import_set",
            "summary": {"workflow_count": len(records), "excluded_file_count": len(excluded),
                        "node_count": total_nodes, "connection_count": total_edges,
                        "dependency_count": len(serialized),
                        "static_dependency_count": sum(dep.reference is not None for dep in dependencies),
                        "unknown_dependency_count": len(unknown), "missing_resource_count": len(missing),
                        "risk_count": len(risks), "manual_review_count": len(manual),
                        "direct_dependency_count": len(direct),
                        "indirect_dependency_count": reachability_count,
                        "blocking_issue_count": len(blocking), "check_count": len(checks),
                        "node_risk_count": len(node_checks), "total_risk_count": len(risks) + len(node_checks),
                        "additional_review_count": len(additional_review), "total_manual_review_count": len(manual) + len(additional_review)},
            "workflows": records, "excluded_files": excluded, "dependencies": serialized,
            "unknown_dependencies": unknown, "missing_resources": missing, "risks": risks,
            "indirect_dependencies": indirect,
            "direct_dependencies": direct, "credential_checklist": credential_checklist,
            "variable_checklist": variable_checklist, "blocking_issues": blocking,
            "checks": checks, "assessment_counts": assessments,
            "node_checks": node_checks, "environment_checks": environment_checks,
            "additional_review_items": additional_review,
            "manual_review_items": manual,
            "graphs": {"schema_version": "1.1", "workflow_dependencies": cross_export, "node_graphs": node_graphs},
            "notice": "Offline lexical and structural evidence only. Missing From Import Set does not mean missing on the destination. Cycles are informational. Unrecognized node semantics and runtime-computed dependencies remain unverified."}
    from .diagnostics import enrich
    return enrich(result, documents)
