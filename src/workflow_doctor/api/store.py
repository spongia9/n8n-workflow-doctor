"""Byte/count/TTL-bounded redacted results. No raw upload bytes are cached."""
import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ..reporting import report_view
from .config import ApiConfig
from .models import ApiProblem, ScanResponse

FORMATS = ("text", "json", "markdown", "html")


@dataclass(frozen=True)
class StoredScan:
    scan_id: str
    created_at: str
    expires_at: str
    deadline: float
    raw: bytes = field(repr=False)

    def report(self) -> dict:
        return json.loads(self.raw)

    def summary(self) -> ScanResponse:
        result = self.report()
        view = report_view(result)
        counts = view["summary"]
        return ScanResponse(scan_id=self.scan_id, status="completed", file_count=result["file_count"],
                            workflow_count=counts["workflow_count"], node_count=counts["node_count"],
                            finding_count=len(view["issues"]), structural_finding_count=result["finding_count"],
                            findings=view["issues"], dependencies=view["dependencies"], report_formats=list(FORMATS),
                            diagnostic_records=view['issues'], diagnostics=result.get('analysis',{}).get('diagnostics'),
                            created_at=self.created_at, expires_at=self.expires_at)


class ResultStore:
    def __init__(self, config: ApiConfig, clock=time.monotonic):
        self.config, self.clock = config, clock
        self._items = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()

    def purge(self):
        with self._lock:
            for key in [key for key, value in self._items.items() if value.deadline <= self.clock()]:
                self._bytes -= len(self._items.pop(key).raw)

    def clear(self):
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def put(self, report: dict) -> StoredScan:
        raw = json.dumps(report, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        if len(raw) > self.config.max_result_bytes:
            raise ApiProblem(413, "RESULT_TOO_LARGE", "Diagnostic result exceeds the server result limit")
        now = datetime.now(timezone.utc)
        item = StoredScan(uuid4().hex, now.isoformat(), (now + timedelta(seconds=self.config.result_ttl_seconds)).isoformat(),
                          self.clock() + self.config.result_ttl_seconds, raw)
        with self._lock:
            self.purge()
            while self._items and (len(self._items) >= self.config.max_results or self._bytes + len(raw) > self.config.max_cache_bytes):
                _, old = self._items.popitem(last=False)
                self._bytes -= len(old.raw)
            self._items[item.scan_id] = item
            self._bytes += len(raw)
        return item

    def get(self, scan_id: str) -> StoredScan:
        with self._lock:
            self.purge()
            if not re.fullmatch(r"[0-9a-f]{32}", scan_id) or scan_id not in self._items:
                raise ApiProblem(404, "SCAN_NOT_FOUND", "Scan is absent, expired, evicted or lost after restart")
            return self._items[scan_id]
