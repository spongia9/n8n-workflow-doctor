"""HTTP envelopes, separate from the canonical engine's diagnostic schema."""
from typing import Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DiagnosticRecord(BaseModel):
    """Additive typed fields; legacy keys remain in findings unchanged."""
    finding_id: str
    rule_id: str
    scope: Literal['workflow','node','connection','environment']
    category: str
    severity_level: Literal['critical','high','medium','low']
    diagnostic_status: Literal['pass','blocker','risk','unknown','not_applicable']
    confidence: Literal['high','medium','low']
    parameter_path: str
    workflow_fingerprint: str
    workflow_name: str | None
    workflow_source_file: str | None
    workflow_label: str
    node_id: str | None
    node_name: str | None
    node_type: str | None
    node_index: int | None = Field(ge=0)
    connection_source: str | None
    connection_target: str | None
    evidence: str
    message_zh: str
    recommendation_zh: str
    unknown_reason: str | None
    required_evidence: list[str]
    recommended_verification: list[str]
    model_config = {'extra':'allow'}


class DiagnosticStatistics(BaseModel):
    check_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    triggered_rule_count: int = Field(ge=0)
    unresolved_reference_count: int = Field(ge=0)
    unresolved_target_count: int = Field(ge=0)
    dynamic_dependency_count: int = Field(ge=0)
    graph_node_count: int = Field(ge=0)
    graph_edge_count: int = Field(ge=0)
    model_config = {'extra':'allow'}


class DiagnosticSummary(BaseModel):
    statistics: DiagnosticStatistics
    rules: list[dict]
    model_config = {'extra':'allow'}


class ScanResponse(BaseModel):
    scan_id: str
    status: Literal["completed"]
    file_count: int = Field(ge=0)
    workflow_count: int = Field(ge=0)
    node_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    structural_finding_count: int = Field(ge=0)
    findings: list[dict]
    diagnostic_records: list[DiagnosticRecord] = Field(default_factory=list)
    diagnostics: DiagnosticSummary | None = None
    dependencies: list[dict]
    report_formats: list[str]
    created_at: str
    expires_at: str


class ApiProblem(Exception):
    """Only fixed application text may be supplied; never exception payloads."""
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message

    def body(self):
        return ErrorResponse(error=ErrorDetail(code=self.code, message=self.message)).model_dump()
