"""Public, value-free diagnostic records shared by all entry points."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    location: str = "$"
    suggestion: str = "Review the indicated structure in a copy of the workflow."
    location_details: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class InputError(ValueError):
    """An operational failure with safe, fixed text, never exception payloads."""

    def __init__(self, code: str, message: str, location: str = "$",
                 suggestion: str = "Check the input and scan it again.", source: str | None = None):
        super().__init__(message)
        self.code = code
        self.location = location
        self.suggestion = suggestion
        self.source = source

    def to_dict(self) -> dict:
        record = {"code": self.code, "severity": "error", "message": str(self),
                  "location": self.location, "suggestion": self.suggestion}
        if self.source is not None:
            record["file"] = self.source
        return record


@dataclass(frozen=True)
class ScanLimits:
    max_files: int = 1000
    max_file_bytes: int = 10 * 1024 * 1024
    max_total_bytes: int = 100 * 1024 * 1024
    max_archive_bytes: int = 100 * 1024 * 1024
    max_json_depth: int = 100
    max_findings_per_file: int = 1000

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise ValueError("Scan limits must be positive integers")


@dataclass(frozen=True)
class AnalysisLimits:
    max_workflows: int = 1000
    max_graph_nodes: int = 100_000
    max_graph_edges: int = 200_000
    max_dependencies: int = 10_000
    max_parameter_values: int = 100_000

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise ValueError("Analysis limits must be positive integers")


@dataclass(frozen=True)
class RiskFinding:
    rule_id: str
    severity: str
    status: str
    workflow_id: str
    node_id: str | None
    evidence_location: str
    message: str
    recommendation: str
    confidence: str
    file: str
    dependency_ids: list[str] = field(default_factory=list)
    assessment: str = "risk"
    verification_scope: str = "static_input_only"

    def to_dict(self) -> dict:
        return asdict(self)


def assessment_for_status(status: str) -> str:
    """Assessment scope is the current input set, never the destination account."""
    if status == "Found In Import Set":
        return "verified"
    if status in ("Invalid In Import Set", "Ambiguous In Import Set", "Invalid Structure"):
        return "blocked"
    if status == "Unknown":
        return "unknown"
    if status == "Not Applicable":
        return "not_applicable"
    return "risk"
