"""CLI adapter for the reusable offline scan API."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import AnalysisLimits, ScanLimits
from .scanner import make_report, scan_path


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _text_report(result: dict) -> str:
    from .reporting import to_text
    return to_text(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow-doctor")
    commands = parser.add_subparsers(dest="command", required=True)
    defaults = ScanLimits()
    for command in ("scan", "analyze"):
        subparser = commands.add_parser(command, help="Offline structural scan" if command == "scan" else "Offline dependency and migration-risk analysis")
        subparser.add_argument("path", type=Path)
        subparser.add_argument("--recursive", action="store_true", help="Include nested directories (ZIPs always include nested members)")
        formats = ["text", "json", "markdown", "html"] + (["graph-json"] if command == "analyze" else [])
        subparser.add_argument("--format", choices=formats, default="text" if command == "scan" else "json")
        subparser.add_argument("--output", type=Path, help="Create a new report; existing paths are never overwritten")
        for field in vars(defaults):
            subparser.add_argument("--" + field.replace("_", "-"), type=_positive_int, default=getattr(defaults, field))
        if command == "analyze":
            for field, value in vars(AnalysisLimits()).items():
                subparser.add_argument("--analysis-" + field.replace("_", "-"), type=_positive_int, default=value)
    args = parser.parse_args(argv)
    limits = ScanLimits(**{field: getattr(args, field) for field in vars(defaults)})
    analysis_limits = (AnalysisLimits(**{field: getattr(args, "analysis_" + field) for field in vars(AnalysisLimits())})
                       if args.command == "analyze" else None)
    result = scan_path(args.path, recursive=args.recursive, limits=limits,
                       analyze=args.command == "analyze", analysis_limits=analysis_limits)
    if args.format == "graph-json":
        payload = result["analysis"]["graphs"] if "analysis" in result else result
        content = json.dumps(payload, ensure_ascii=True, indent=2)
    else:
        from .reporting import render_report
        content = render_report(result, args.format)
    try:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also rejects aliases, hard links and dangling links.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(content if content.endswith("\n") else content + "\n")
            print(f"Report written: {json.dumps(str(args.output), ensure_ascii=True)}")
        else:
            print(content)
    except (OSError, UnicodeError):
        failure = make_report(errors=[{
            "code": "OUTPUT_WRITE_ERROR", "severity": "error", "location": "$",
            "message": "Cannot create report; the output may already exist or be unwritable",
            "suggestion": "Choose a new writable output path distinct from all input files."}])
        print(json.dumps(failure) if args.format in ("json", "graph-json") else _text_report(failure), file=sys.stderr)
        return 2
    summary = result.get("analysis", {}).get("summary", {})
    risk_count = summary.get("total_risk_count", summary.get("risk_count", 0))
    unknown_count = result.get("analysis", {}).get("summary", {}).get("unknown_dependency_count", 0)
    return 2 if result["error_count"] else (1 if result["finding_count"] or risk_count or unknown_count else 0)
