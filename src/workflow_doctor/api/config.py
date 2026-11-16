"""Server-owned limits; clients cannot raise them through request parameters."""
from dataclasses import dataclass, field

from ..models import AnalysisLimits, ScanLimits


@dataclass(frozen=True)
class ApiConfig:
    max_request_bytes: int = 8 * 1024 * 1024
    upload_timeout_seconds: int = 15
    max_results: int = 8
    max_result_bytes: int = 4 * 1024 * 1024
    max_response_bytes: int = 16 * 1024 * 1024
    max_cache_bytes: int = 32 * 1024 * 1024
    result_ttl_seconds: int = 900
    cleanup_interval_seconds: int = 15
    scan_limits: ScanLimits = field(default_factory=lambda: ScanLimits(
        max_files=32, max_file_bytes=2 * 1024 * 1024, max_total_bytes=16 * 1024 * 1024,
        max_archive_bytes=8 * 1024 * 1024, max_json_depth=40, max_findings_per_file=128))
    analysis_limits: AnalysisLimits = field(default_factory=lambda: AnalysisLimits(
        max_workflows=32, max_graph_nodes=1024, max_graph_edges=4096,
        max_dependencies=2048, max_parameter_values=10000))
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    def __post_init__(self):
        for name, value in vars(self).items():
            if name not in ("scan_limits", "analysis_limits", "cors_origins") and (type(value) is not int or value <= 0):
                raise ValueError("API limits must be positive integers")
        if self.max_result_bytes > self.max_cache_bytes:
            raise ValueError("A result must fit within the cache budget")
        if any(origin not in ("http://localhost:5173", "http://127.0.0.1:5173") for origin in self.cors_origins):
            raise ValueError("Only explicit local development CORS origins are supported")
