"""Reusable offline scan API; public imports from the starter remain available."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .inputs import collect_files, read_file, read_zip, read_zip_bytes
from .models import AnalysisLimits, Finding, InputError, ScanLimits
from .parser import parse_json
from .rules import scan_object

NOTICE = "Static structural checks only; compatibility is unknown, not proof of successful import or execution."


def scan_bytes(raw: bytes, source: str = "<memory>", limits: ScanLimits | None = None) -> dict[str, Any]:
    """Scan supplied bytes without any file, server, credential or UI dependency."""
    return _scan_input(raw, source, limits or ScanLimits())[0]


def _scan_input(raw: bytes, source: str, limits: ScanLimits) -> tuple[dict, Any]:
    """Decode once; only opt-in analysis retains the original decoded object."""
    limits = limits or ScanLimits()
    if len(raw) > limits.max_file_bytes:
        raise InputError("INPUT_FILE_TOO_LARGE", "JSON file exceeds the single-file byte limit")
    data, findings = parse_json(raw, limits)
    if not findings:
        findings = scan_object(data, max_findings=limits.max_findings_per_file)
    statistics = None
    if not findings:
        statistics = {"node_count": len(data["nodes"]),
                      "connection_count": sum(len(port or []) for types in data["connections"].values()
                                              for ports in types.values() for port in ports)}
    return {"file": source, "workflow_name": None, "statistics": statistics,
            "structure_status": "failed" if findings else "passed",
            "compatibility": "unknown", "findings": [item.to_dict() for item in findings]}, data


def scan_file(path: Path, limits: ScanLimits | None = None) -> dict[str, Any]:
    limits = limits or ScanLimits()
    path = Path(path)
    return scan_bytes(read_file(path, limits.max_file_bytes), str(path), limits)


def make_report(results=None, skipped=None, errors=None, source=None) -> dict[str, Any]:
    results, skipped, errors = results or [], skipped or [], errors or []
    return {"schema_version": "0.2", "input": source, "file_count": len(results),
            "finding_count": sum(len(item["findings"]) for item in results),
            "error_count": len(errors), "skipped_count": len(skipped),
            "complete": not errors, "results": results, "skipped": skipped,
            "errors": errors, "notice": NOTICE}


def scan_path(target: Path, recursive: bool = False,
              limits: ScanLimits | None = None, *, analyze: bool = False,
              analysis_limits: AnalysisLimits | None = None) -> dict[str, Any]:
    """Scan JSON, a directory, or a ZIP; unsafe batches return structured errors."""
    target, limits = Path(target), limits or ScanLimits()
    skipped: list[dict] = []
    documents = []
    try:
        if target.suffix.lower() == ".zip" and not target.is_dir():
            members, skipped = read_zip(target, limits)
            results = []
            for source, raw in members:
                result, data = _scan_input(raw, source, limits)
                results.append(result)
                if analyze:
                    documents.append((source, data))
        else:
            files, skipped = collect_files(target, recursive, limits)
            results = []
            total = 0
            for path in files:
                raw = read_file(path, min(limits.max_file_bytes, limits.max_total_bytes - total))
                total += len(raw)
                result, data = _scan_input(raw, str(path), limits)
                results.append(result)
                if analyze:
                    documents.append((str(path), data))
        return _finish_report(results, skipped, documents, str(target), analyze, analysis_limits)
    except InputError as exc:
        return make_report(skipped=skipped, errors=[exc.to_dict()], source=str(target))


def analyze_path(target: Path, recursive: bool = False, limits: ScanLimits | None = None,
                 analysis_limits: AnalysisLimits | None = None) -> dict[str, Any]:
    """Convenience API; preserves scan_path's structured operational errors."""
    return scan_path(target, recursive, limits, analyze=True, analysis_limits=analysis_limits)


def _finish_report(results, skipped, documents, source, analyze, analysis_limits):
    if not results:
        return make_report(skipped=skipped, errors=[InputError(
            "INPUT_EMPTY", "No JSON files found").to_dict()], source=source)
    report = make_report(results, skipped, source=source)
    if analyze:
        try:
            from .analysis import analyze_documents
        except ModuleNotFoundError as exc:
            if exc.name != "networkx":
                raise
            raise InputError("ANALYSIS_DEPENDENCY_MISSING", "NetworkX is required for dependency analysis",
                             suggestion="Install the project's declared NetworkX dependency; basic scan remains available.") from None
        parse_findings = {item["file"]: [Finding(**finding) for finding in item["findings"]]
                          for item in results if any(finding["rule_id"] == "WF001" for finding in item["findings"])}
        report["analysis"] = analyze_documents(documents, limits=analysis_limits, parse_findings=parse_findings)
    return report


def scan_uploads(files: list[tuple[str, bytes]], limits: ScanLimits | None = None, *,
                 analyze: bool = True, analysis_limits: AnalysisLimits | None = None) -> dict:
    """Bounded memory batch; labels are caller-visible metadata, never paths to open.

    Accept JSON files or exactly one ZIP. Uses the same parsers, ZIP validator,
    analysis and report builder as scan_path. Does not retain or mutate inputs.
    """
    limits = limits or ScanLimits()
    source = files[0][0] if len(files) == 1 else "<uploads>"
    skipped = []
    try:
        if not files:
            raise InputError("INPUT_EMPTY", "No JSON files found")
        if len(files) > limits.max_files:
            raise InputError("INPUT_FILE_COUNT", "Upload file count exceeds the limit")
        suffixes = [Path(label).suffix.lower() for label, _ in files]
        if any(suffix not in (".json", ".zip") for suffix in suffixes):
            raise InputError("INPUT_UNSUPPORTED_TYPE", "Only JSON files or a ZIP archive are supported")
        if ".zip" in suffixes and len(files) != 1:
            raise InputError("INPUT_MIXED_ARCHIVE", "Upload one ZIP or one or more JSON files")
        if suffixes == [".zip"]:
            members, skipped = read_zip_bytes(files[0][1], source, limits)
        else:
            if sum(len(raw) for _, raw in files) > limits.max_total_bytes:
                raise InputError("INPUT_TOTAL_TOO_LARGE", "JSON total exceeds the available byte limit")
            members = files
        results, documents = [], []
        for label, raw in members:
            result, data = _scan_input(raw, label, limits)
            results.append(result)
            if analyze:
                documents.append((label, data))
        return _finish_report(results, skipped, documents, source, analyze, analysis_limits)
    except InputError as exc:
        return make_report(skipped=skipped, errors=[exc.to_dict()], source=source)
