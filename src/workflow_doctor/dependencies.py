"""Static reference extraction; values remain internal and never enter reports."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .adapters import AdapterRegistry, workflow_reference
from .models import AnalysisLimits, InputError, assessment_for_status
from .privacy import fingerprint, is_expression, static_id


@dataclass(frozen=True)
class CredentialReference:
    """Reference metadata only; no password, token, or credential data fields."""
    credential_type: str | None = field(default=None, repr=False)
    credential_id: str | int | None = field(default=None, repr=False)
    name: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        identifier = static_id(self.credential_id)
        return {"type_fingerprint": fingerprint("credential-type", self.credential_type) if self.credential_type else None,
                "id_fingerprint": fingerprint("credential", identifier) if identifier is not None else None,
                "name_fingerprint": fingerprint("credential-name", self.name) if self.name and not is_expression(self.name) else None,
                "name_present": bool(self.name), "id_present": self.credential_id is not None}


@dataclass
class Dependency:
    kind: str
    location: str
    node_id: str | None
    reference: str | None
    form: str
    reason: str
    confidence: str = "high"
    target: str | None = field(default=None, repr=False)
    status: str = "Requires Review"
    dependency_id: str = ""
    workflow_id: str = ""
    file: str = ""
    target_workflow_id: str | None = None
    source_kind: str | None = None
    credential: CredentialReference | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        # Explicit allowlist: target contains the raw lookup ID and must stay private.
        return {"id": self.dependency_id, "kind": self.kind, "evidence_location": self.location,
                "node_id": self.node_id, "reference_fingerprint": self.reference,
                "reference_form": self.form, "reason": self.reason, "confidence": self.confidence,
                "status": self.status, "workflow_id": self.workflow_id, "file": self.file,
                "target_workflow_id": self.target_workflow_id,
                "source_kind": self.source_kind,
                "assessment": assessment_for_status(self.status),
                "credential_reference": self.credential.to_dict() if self.credential else None}


SYMBOL = re.compile(r"(?<![\w$.])(?P<root>\$env|\$vars|process\.env|_env|_vars)(?![A-Za-z0-9_])"
                    r"(?:(?:\.(?P<dot>[A-Za-z_][A-Za-z0-9_]*))|(?:\[\s*(?P<quote>['\"])(?P<bracket>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)\s*\]))?")


def walk_values(value: Any, location: str, counter: list[int], limit: int):
    """Ordinal member paths preserve evidence without leaking arbitrary key names."""
    counter[0] += 1
    if counter[0] > limit:
        raise InputError("ANALYSIS_VALUE_LIMIT", "Parameter traversal exceeds the analysis value limit")
    if isinstance(value, dict):
        for index, item in enumerate(value.values()):
            yield from walk_values(item, f"{location}{{member:{index}}}", counter, limit)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_values(item, f"{location}[{index}]", counter, limit)
    elif isinstance(value, str):
        yield value, location


def _path_form(value: str) -> str | None:
    if value.startswith(("\\\\", "//")):
        return "unc_absolute"
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return "windows_absolute"
    if value.startswith("/"):
        return "posix_absolute"
    return None


def extract_dependencies(data: dict, limits: AnalysisLimits | None = None,
                         registry: AdapterRegistry | None = None) -> list[Dependency]:
    limits, registry = limits or AnalysisLimits(), registry or AdapterRegistry()
    records: list[Dependency] = []
    counter = [0]

    def add(record: Dependency):
        if len(records) >= limits.max_dependencies:
            raise InputError("ANALYSIS_DEPENDENCY_LIMIT", "Dependency count exceeds the analysis limit", record.location)
        records.append(record)

    settings = data.get("settings", {})
    error = settings.get("errorWorkflow")
    if error is not None and error != "" and error != "DEFAULT":
        ref = workflow_reference(error, "$.settings.errorWorkflow", locator_allowed=False)
        add(Dependency("error_workflow", ref.location, None,
                       fingerprint("workflow", ref.value) if ref.value is not None else None,
                       ref.form, ref.reason, target=ref.value,
                       confidence="high" if ref.value is not None else "low",
                       status="Static" if ref.value is not None else "Unknown"))

    for index, node in enumerate(data["nodes"]):
        node_id = fingerprint("node", node["id"])
        ref = registry.extract(node, index)
        if ref is not None:
            add(Dependency("sub_workflow", ref.location, node_id,
                           fingerprint("workflow", ref.value) if ref.value is not None else None,
                           ref.form, ref.reason, target=ref.value,
                           confidence="high" if ref.value is not None else "low",
                           status="Static" if ref.value is not None else "Unknown", source_kind=ref.source_kind))
        handled_path = None
        if ref is not None and ref.source_kind == "local_file":
            value = ref.resource_value
            static = isinstance(value, str) and bool(value) and not is_expression(value)
            add(Dependency("local_path", ref.location, node_id, fingerprint("local-path", value) if static else None,
                           (_path_form(value) or "relative_workflow_file") if static else "dynamic_or_missing_path",
                           "Explicit workflow file dependency; no file was read", status="Requires Review" if static else "Unknown"))
            handled_path = f"$.nodes[{index}].parameters{{member:{list(node['parameters']).index('workflowPath')}}}" if "workflowPath" in node["parameters"] else None
        credentials = node.get("credentials")
        if credentials is not None:
            if not isinstance(credentials, dict):
                add(Dependency("credential", f"$.nodes[{index}].credentials", node_id, None,
                               "unknown_shape", "Credential reference structure requires review", status="Unknown"))
            for credential_index, (credential_type, credential) in enumerate(credentials.items() if isinstance(credentials, dict) else []):
                loc = f"$.nodes[{index}].credentials{{member:{credential_index}}}"
                raw_id = credential.get("id") if isinstance(credential, dict) else None
                raw_name = credential.get("name") if isinstance(credential, dict) else credential
                metadata = CredentialReference(credential_type if isinstance(credential_type, str) else None,
                                               raw_id if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else None,
                                               raw_name if isinstance(raw_name, str) else None)
                credential_id = static_id(credential.get("id")) if isinstance(credential, dict) else None
                if credential_id is not None:
                    add(Dependency("credential", loc + ".id", node_id, fingerprint("credential", credential_id),
                                   "credential_id", "Credential ID reference extracted; destination mapping is unverified",
                                   status="Requires Reconfiguration", credential=metadata))
                elif isinstance(credential, str) or (isinstance(credential, dict) and isinstance(credential.get("name"), str)):
                    # Legacy names are deliberately not disclosed or used to assert identity.
                    add(Dependency("credential", loc, node_id, None, "name_only_or_dynamic",
                                   "Credential reference has no reliable static ID", "medium", status="Unknown", credential=metadata))
                else:
                    add(Dependency("credential", loc, node_id, None, "unknown_shape",
                                   "Credential reference requires manual inspection", "low", status="Unknown", credential=metadata))

        for value, loc in walk_values(node["parameters"], f"$.nodes[{index}].parameters", counter,
                                      limits.max_parameter_values):
            # Lexical evidence only. Code strings are never parsed as executable code.
            for match in SYMBOL.finditer(value):
                kind = "n8n_variable" if match["root"] in ("$vars", "_vars") else "environment_variable"
                symbol = match["dot"] or match["bracket"]
                add(Dependency(kind, loc, node_id, fingerprint(kind, symbol) if symbol else None,
                               "static_symbol" if symbol else "computed_symbol",
                               "Lexical variable access found; availability and value are unverified", "medium",
                               status="Requires Review" if symbol else "Unknown"))
            path_form = _path_form(value)
            if path_form and loc != handled_path:
                dynamic = is_expression(value)
                add(Dependency("local_path", loc, node_id, None if dynamic else fingerprint("local-path", value),
                               "dynamic_path" if dynamic else path_form,
                               "Path requires runtime evaluation" if dynamic else
                               "Absolute path literal found; destination filesystem was not inspected", "medium",
                               status="Unknown" if dynamic else "Requires Review"))
            if (value[:8].lower().startswith(("http://", "https://"))
                    or (is_expression(value) and re.search(r"https?://", value, re.IGNORECASE))):
                if is_expression(value):
                    add(Dependency("external_service", loc, node_id, None, "dynamic_endpoint",
                                   "Service endpoint depends on an expression", "low", status="Unknown"))
                    continue
                try:
                    parsed = urlsplit(value)
                    host, port = parsed.hostname, parsed.port
                    if not host:
                        raise ValueError("No hostname")
                    default_port = 443 if parsed.scheme == "https" else 80
                    origin = f"{parsed.scheme}://{host.lower()}:{port or default_port}"
                    add(Dependency("external_service", loc, node_id, fingerprint("service-origin", origin),
                                   "http_origin", "Static service origin found; access and shared-state semantics are unverified",
                                   "medium"))
                except ValueError:
                    add(Dependency("external_service", loc, node_id, None, "invalid_endpoint",
                                   "Service endpoint could not be interpreted statically", "low", status="Unknown"))
    return records
