"""Version-scoped, explicitly registered adapters. Never guess future schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .privacy import is_expression, static_id


@dataclass(frozen=True)
class WorkflowReference:
    value: str | None = field(repr=False)
    location: str
    form: str
    reason: str
    source_kind: str = "database"
    resource_value: Any = field(default=None, repr=False)


def workflow_reference(value: Any, location: str, locator_allowed: bool = True) -> WorkflowReference:
    form = "id"
    if isinstance(value, dict):
        if not locator_allowed or value.get("__rl") is not True or value.get("mode") not in ("id", "list", "url"):
            return WorkflowReference(None, location, "unknown_shape", "Unrecognized workflow selector structure")
        mode = value["mode"]
        value = value.get("value")
        location += ".value"
        form = "resource_locator"
        if mode == "url":
            # Parsing only; no requests. Query strings, credentials and origins are never reported.
            if not isinstance(value, str) or is_expression(value):
                return WorkflowReference(None, location, "dynamic_expression", "Workflow selector requires runtime evaluation")
            try:
                parsed = urlsplit(value)
                parts = parsed.path.strip("/").split("/")
                value = parts[-1] if parsed.scheme in ("http", "https") and parsed.hostname and len(parts) >= 2 and parts[-2] == "workflow" else None
            except ValueError:
                value = None
            form = "workflow_url"
    if value is None or value == "" or value == "DEFAULT":
        return WorkflowReference(None, location, "unset", "No explicit workflow reference is configured")
    if is_expression(value):
        return WorkflowReference(None, location, "dynamic_expression", "Workflow reference requires runtime evaluation")
    target = static_id(value)
    return WorkflowReference(target, location, form if target is not None else "unknown_shape",
                             "Static workflow ID extracted" if target is not None else "Workflow reference is absent or cannot be resolved statically")


@dataclass(frozen=True)
class ExecuteWorkflowAdapter:
    node_type: str = "n8n-nodes-base.executeWorkflow"
    versions: tuple = (1, 1.1, 1.2, 1.3, 1.4)

    def extract(self, node: dict, index: int) -> WorkflowReference:
        base = f"$.nodes[{index}].parameters"
        source = node["parameters"].get("source", "database")
        if source == "localFile" and node["typeVersion"] in (1, 1.1):
            return WorkflowReference(None, base + ".workflowPath", "local_file",
                                     "File-sourced workflow is not a database ID; file content was not read",
                                     "local_file", node["parameters"].get("workflowPath"))
        if source == "url" and node["typeVersion"] in (1, 1.1):
            return WorkflowReference(None, base + ".workflowUrl", "remote_workflow",
                                     "URL-sourced workflow is not a database ID; URL was not requested",
                                     "remote_url", node["parameters"].get("workflowUrl"))
        if source == "parameter":
            value = node["parameters"].get("workflowJson")
            return WorkflowReference(None, base + ".workflowJson",
                                     "dynamic_embedded_workflow" if is_expression(value) else "embedded_workflow",
                                     "Parameterized workflow is not a database ID; embedded content was not evaluated",
                                     "parameter")
        if source != "database":
            return WorkflowReference(None, base + ".source", "external_or_embedded_source",
                                     "Unsupported or dynamic workflow source requires manual review", "unsupported")
        return workflow_reference(node["parameters"].get("workflowId"), base + ".workflowId",
                                  locator_allowed=node["typeVersion"] != 1)


class AdapterRegistry:
    def __init__(self, adapters=None):
        self.adapters = list(adapters) if adapters is not None else [ExecuteWorkflowAdapter()]

    def register(self, adapter):
        """Register trusted application code, never an adapter from workflow JSON."""
        self.adapters.append(adapter)

    def extract(self, node: dict, index: int) -> WorkflowReference | None:
        candidates = [adapter for adapter in self.adapters if adapter.node_type == node["type"]]
        for adapter in candidates:
            if node["typeVersion"] in adapter.versions:
                return adapter.extract(node, index)
        if candidates:
            return WorkflowReference(None, f"$.nodes[{index}].typeVersion", "unsupported_version",
                                     "Node version is not covered by a registered workflow-call adapter")
        return None
