"""Markdown rendering of safe structural and dependency report records."""
from __future__ import annotations

import html
import json

from .privacy import display_text
from .models import assessment_for_status


ASSESSMENTS = ("verified", "blocked", "risk", "unknown", "not_applicable")


def report_view(report: dict) -> dict:
    """Pure presentation projection of the canonical scanner result; no I/O."""
    analysis = report.get("analysis", {})
    issues = [{**item, "assessment": item.get("assessment", assessment_for_status(item["status"])),
               "verification_scope": item.get("verification_scope", "static_input_only")}
              for item in analysis.get("checks", analysis.get("risks", []))]
    seen = {(item["rule_id"], item.get("file"), item["evidence_location"]) for item in issues}
    by_key = {(item["rule_id"], item.get("file"), item["evidence_location"]): item for item in issues}
    for result in report["results"]:
        for finding in result["findings"]:
            key = (finding["rule_id"], result["file"], finding["location"])
            if key not in seen:
                issues.append({"rule_id": finding["rule_id"], "file": result["file"], "workflow_id": None,
                               "node_id": None, "evidence_location": finding["location"],
                               "severity": finding["severity"], "status": "Invalid Structure", "assessment": "blocked",
                               "message": finding["message"], "recommendation": finding["suggestion"],
                               "confidence": "high", "verification_scope": "static_input_only"})
                seen.add(key)
                by_key[key] = issues[-1]
            by_key[key]["location_details"] = finding.get("location_details", {})
    counts = {kind: sum(item.get("assessment", "risk") == kind for item in issues) for kind in ASSESSMENTS}
    from .diagnostics import decorate
    issues = [item if 'finding_id' in item else decorate(item) for item in issues]
    stats = [item["statistics"] for item in report["results"] if item.get("statistics") is not None]
    summary = {"file_count": report["file_count"], "error_count": report["error_count"],
               "skipped_count": report["skipped_count"], "structural_finding_count": report["finding_count"],
               "workflow_count": len(stats), "node_count": sum(item["node_count"] for item in stats),
               "connection_count": sum(item["connection_count"] for item in stats),
               "risk_count": analysis.get("summary", {}).get("total_risk_count", analysis.get("summary", {}).get("risk_count", 0))}
    for key in ("workflow_count", "node_count", "connection_count"):
        if analysis:
            summary[key] = analysis["summary"][key]
        elif any("statistics" not in item for item in report["results"]):
            summary[key] = None  # Historical records or invalid files are not fabricated zeros.
    return {"summary": summary, "assessment_counts": counts, "issues": issues,
            "severity_counts": {level: sum(item["severity"] == level for item in issues) for level in ("error", "warning", "info")},
            "workflows": analysis.get("workflows", [{"file": item["file"], "workflow_id": None, "identity_kind": "not_analyzed"}
                                                       for item in report["results"] if item.get("statistics")]),
            "dependencies": analysis.get("dependencies", []),
            "manual_review_items": analysis.get("manual_review_items", []) + analysis.get("additional_review_items", [])}


def _escape(value) -> str:
    text = html.escape(display_text(value), quote=True)
    for char in ("\\", "`", "*", "_", "[", "]", "|", "#"):
        text = text.replace(char, "\\" + char)
    return text


def to_markdown(report: dict) -> str:
    lines = ["# n8n Workflow Doctor — Migration dependency report", "",
             f"Input: {_escape(report.get('input'))}", "",
             f"Batch complete: {_escape(report['complete'])}; structural findings: {report['finding_count']}; input errors: {report['error_count']}.", ""]
    for error in report["errors"]:
        lines.extend([f"- {_escape(error['code'])}: {_escape(error['message'])} ({_escape(error['location'])})",
                      f"  File: {_escape(error.get('file', report.get('input')))}",
                      f"  Recommendation: {_escape(error['suggestion'])}"])
    lines.extend(["", "## Skipped inputs", ""])
    for item in report["skipped"]:
        lines.append(f"- {_escape(item['file'])}: {_escape(item['reason'])}")
    lines.extend(["", "## Structural findings", ""])
    for result in report["results"]:
        for finding in result["findings"]:
            lines.extend([f"- {_escape(finding['rule_id'])} / {_escape(finding['severity'])}: {_escape(finding['message'])}",
                          f"  File: {_escape(result['file'])}; evidence: {_escape(finding['location'])}.",
                          f"  Recommendation: {_escape(finding['suggestion'])}"])
            if finding.get("location_details"):
                lines.append(f"  Position: {_escape(json.dumps(finding['location_details'], sort_keys=True))}")
    analysis = report.get("analysis")
    if not analysis:
        view = report_view(report)
        lines.extend(["", "## Summary", "", "| Metric | Count |", "| --- | --- |"])
        for key, value in view["summary"].items():
            lines.append(f"| {_escape(key)} | {_escape(value)} |")
        lines.extend(["", "## Assessment counts", ""])
        for key, value in view["assessment_counts"].items():
            lines.append(f"- {_escape(key)}: {value}")
        lines.extend(["", "Dependency analysis was not requested. Use analyze for migration checks.", "", _escape(report["notice"])])
        return "\n".join(lines) + "\n"
    lines.extend(["", "## Summary", "", "| Metric | Count |", "| --- | --- |"])
    for key, value in analysis["summary"].items():
        lines.append(f"| {_escape(key)} | {value} |")
    lines.extend(["", "Compatibility: **unknown**. IDs are stable fingerprints; temporary file IDs are explicitly marked.",
                  "", "## Workflow identities", "", "| Workflow ID | Identity kind | File |", "| --- | --- | --- |"])
    for record in analysis["workflows"]:
        lines.append(f"| {_escape(record['workflow_id'])} | {_escape(record['identity_kind'])} | {_escape(record['file'])} |")
    lines.extend(["", "## Migration risks", ""])
    for risk in analysis["risks"]:
        lines.extend([f"### {_escape(risk['rule_id'])} — {_escape(risk['message'])}", "",
                      f"- Severity: {_escape(risk['severity'])}; status: {_escape(risk['status'])}; confidence: {_escape(risk['confidence'])}; assessment: {_escape(risk.get('assessment', 'risk'))}.",
                      f"- Workflow ID: {_escape(risk['workflow_id'])}; node ID: {_escape(risk['node_id'])}.",
                      f"- File: {_escape(risk['file'])}; evidence: {_escape(risk['evidence_location'])}.",
                      f"- Dependencies: {_escape(', '.join(risk['dependency_ids']))}.",
                      f"- Recommendation: {_escape(risk['recommendation'])}", ""])
    for title, key in (("Dependency inventory", "dependencies"), ("Direct cross-workflow dependencies", "direct_dependencies"),
                       ("Credential checklist", "credential_checklist"), ("Variable checklist", "variable_checklist"),
                       ("Unknown dependencies", "unknown_dependencies"),
                       ("Missing From Import Set", "missing_resources")):
        lines.extend([f"## {title}", "", "| Dependency | Kind | Status | Workflow | Evidence |", "| --- | --- | --- | --- | --- |"])
        for dep in analysis.get(key, []):
            lines.append(f"| {_escape(dep['id'])} | {_escape(dep['kind'])} | {_escape(dep['status'])} | {_escape(dep['workflow_id'])} | {_escape(dep['evidence_location'])} |")
        lines.append("")
    lines.extend(["## Assessment checks", "", "Verified means verified within this input set only; destination compatibility remains unknown.", ""])
    for check in report_view(report)["issues"]:
        lines.append(f"- {_escape(check['rule_id'])} / {_escape(check['assessment'])}: {_escape(check['message'])} "
                     f"(file {_escape(check['file'])}; evidence {_escape(check['evidence_location'])}).")
        lines.append(f"  Severity: {_escape(check['severity'])}; status: {_escape(check['status'])}; confidence: {_escape(check['confidence'])}. "
                     f"Workflow: {_escape(check['workflow_id'])}; node: {_escape(check['node_id'])}. "
                     f"Recommendation: {_escape(check['recommendation'])}")
        if check.get("location_details"):
            lines.append(f"  Position: {_escape(json.dumps(check['location_details'], sort_keys=True))}")
    lines.extend(["", "## Assessment counts", ""])
    for key, value in report_view(report)["assessment_counts"].items():
        lines.append(f"- {_escape(key)}: {value}")
    lines.extend(["## Indirect static references", ""])
    for item in analysis["indirect_dependencies"]:
        lines.append(f"- {_escape(item['workflow_id'])}: {_escape(', '.join(item['targets']))}")
    lines.extend(["", "## Human review", ""])
    for item in report_view(report)["manual_review_items"]:
        lines.append(f"- {_escape(item['code'])} / {_escape(item['status'])}: {_escape(item['message'])} "
                     f"(workflow {_escape(item.get('workflow_id'))}; evidence {_escape(item['evidence_location'])}; dependency {_escape(item.get('dependency_id'))}).")
    lines.extend(["", "## Excluded files", ""])
    for item in analysis["excluded_files"]:
        lines.append(f"- {_escape(item['file'])}: {_escape(item['reason'])}")
    lines.extend(["", "## Graphs", "", "Graph JSON is available through `analyze --format graph-json` or the JSON report's `analysis.graphs` field.",
                  f"Cross-workflow cyclic components: {len(analysis['graphs']['workflow_dependencies']['cyclic_components'])}. Cycles are informational.",
                  "", "## Scope", "", analysis["notice"], "", report["notice"]])
    return "\n".join(lines) + "\n"


def to_text(result: dict) -> str:
    lines = [f"Scanned {result['file_count']} JSON file(s); {result['finding_count']} finding(s); "
             f"{result['error_count']} input error(s); {result['skipped_count']} skipped"]
    for file in result["results"]:
        lines.append(f"File: {json.dumps(file['file'], ensure_ascii=True)}")
        for issue in file["findings"]:
            lines.append(f"  [{issue['rule_id']}] {issue['severity']}: {issue['message']} ({issue['location']})")
            if issue["location_details"]:
                lines.append(f"    Position: {json.dumps(issue['location_details'], sort_keys=True)}")
            lines.append(f"    Suggestion: {issue['suggestion']}")
    for issue in result["errors"]:
        lines.append(f"[{issue['code']}] {issue['severity']}: {issue['message']} ({issue['location']})")
        if issue.get("file"):
            lines.append(f"  File: {json.dumps(issue['file'], ensure_ascii=True)}")
        lines.append(f"  Suggestion: {issue['suggestion']}")
    for item in result["skipped"]:
        lines.append(f"Skipped {json.dumps(item['file'], ensure_ascii=True)}: [{item['code']}] {item['reason']}")
    if "analysis" in result:
        analysis = result["analysis"]
        lines.append("Dependency summary: " + json.dumps(analysis["summary"], sort_keys=True))
        for risk in analysis.get("checks", analysis["risks"]):
            lines.append(f"[{risk['rule_id']}] {risk['severity']} / {risk['status']} / {risk['confidence']}: {risk['message']} ({risk['evidence_location']})")
            lines.append(f"  Assessment: {risk.get('assessment', 'risk')}; workflow: {risk['workflow_id']}; node: {risk['node_id']}")
            lines.append(f"  Recommendation: {risk['recommendation']}")
        lines.append(analysis["notice"])
    lines.append(result["notice"])
    return "\n".join(lines)



def render_report(report: dict, format: str, *, generated_at: str | None = None) -> str:
    """Shared render dispatch for CLI and HTTP; no transport dependencies."""
    if format == "json":
        return json.dumps(report, ensure_ascii=True, indent=2)
    if format == "text":
        return to_text(report) + chinese_details(report)
    if format == "markdown":
        return to_markdown(report) + chinese_details(report)
    if format == "html":
        from .html_report import to_html
        return to_html(report, generated_at=generated_at)
    raise ValueError("Unsupported report format")


def chinese_details(report):
    """Append a shared Chinese view; preserve legacy technical text and keys."""
    lines=['', '', '## 中文诊断明细 / 仅基于本次输入文件进行静态分析', '']
    stats=report.get('analysis',{}).get('diagnostics',{}).get('statistics')
    if stats:
        lines += [f"检查总数：{stats['check_count']}；问题发现（阻断/风险/未知）：{stats['finding_count']}；唯一问题规则：{stats['triggered_rule_count']}。",
                  f"风险发现：{stats['risk_finding_count']}；阻断：{stats['blocker_count']}；未知：{stats['unknown_count']}；不适用：{stats['not_applicable_count']}。",
                  f"跨工作流图：{stats['graph_node_count']} 节点 / {stats['graph_edge_count']} 边；未解析引用：{stats['unresolved_reference_count']}；未解析目标：{stats['unresolved_target_count']}；动态引用：{stats['dynamic_dependency_count']}。"]
    for f in report_view(report)['issues']:
        lines += [f"- {f['finding_id']} · {f['rule_id']} · {f['rule_name']}",
                  f"  所属层级：{f['scope_zh']}；诊断状态：{f['status_zh']}；严重程度：{f['severity_level']}；置信度：{f['confidence']}",
                  f"  工作流：{_escape(f['workflow_label'])}；节点：{_escape(f.get('node_label') or '未定位到具体节点')}；证据：{_escape(f['parameter_path'])}",
                  f"  说明：{f['message_zh']}；建议：{f['recommendation_zh']}"]
        if f['unknown_reason']:
            lines += [f"  无法确认原因：{f['unknown_reason']}",f"  所需证据：{'；'.join(f['required_evidence'])}",f"  人工核查：{'；'.join(f['recommended_verification'])}"]
    return '\n'.join(lines)+'\n'
