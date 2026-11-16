"""WF008/009/010/012/013/018: reminders supported by static evidence only."""
from __future__ import annotations

from collections import defaultdict

from .dependencies import Dependency
from .models import RiskFinding, assessment_for_status


RULES = {
    "sub_workflow": ("WF008", "Sub-workflow dependency requires migration review",
                     "Map the workflow ID after import; check caller permissions, inputs and publication state manually."),
    "error_workflow": ("WF009", "Error Workflow reference requires migration review",
                       "Map the error workflow after import and verify its Error Trigger and permissions manually."),
    "credential": ("WF010", "Credential reference requires reconfiguration",
                   "Recreate or securely map credentials on the destination; verify permissions without disclosing secrets."),
    "environment_variable": ("WF012", "Environment variable dependency requires review",
                             "Provision the required environment variable and check access policy; never copy its value into the report."),
    "n8n_variable": ("WF012", "n8n variable dependency requires review",
                     "Provision the n8n variable and verify feature availability and environment scope manually."),
    "local_path": ("WF013", "Local filesystem dependency requires review",
                   "Review destination mounts, file availability and permissions; do not read the path during analysis."),
}


def diagnose_dependencies(dependencies: list[Dependency]) -> list[RiskFinding]:
    findings = []
    for dep in dependencies:
        if dep.kind not in RULES:
            continue
        rule, message, recommendation = RULES[dep.kind]
        severity = "info" if dep.status == "Found In Import Set" else "warning"
        if dep.status == "Missing From Import Set":
            message += ": Missing From Import Set; destination existence is unknown"
        findings.append(RiskFinding(rule, severity, dep.status, dep.workflow_id, dep.node_id, dep.location,
                                    message, recommendation, dep.confidence, dep.file, [dep.dependency_id],
                                    assessment=assessment_for_status(dep.status)))

    shared = defaultdict(list)
    for dep in dependencies:
        if dep.kind in ("external_service", "credential", "local_path") and dep.reference is not None:
            shared[(dep.kind, dep.reference)].append(dep)
    for group in shared.values():
        if len({(dep.workflow_id, dep.node_id) for dep in group}) < 2:
            continue
        first = group[0]
        findings.append(RiskFinding("WF018", "info", "Shared Resource Reference", first.workflow_id,
                                    first.node_id, first.location,
                                    "Multiple nodes reference the same external resource identity; shared state is unverified",
                                    "Review all linked references for shared quotas, ownership, state and migration sequencing.",
                                    "medium", first.file, [dep.dependency_id for dep in group]))
    return findings
