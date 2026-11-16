"""Self-contained, script-free HTML over the same redacted diagnostic object."""
from __future__ import annotations

import base64
import hashlib
import html
import json
from datetime import datetime, timezone

from .privacy import display_text
from .reporting import ASSESSMENTS, report_view


CSS = """
:root{color-scheme:light;--navy:#142b49;--blue:#245eb3;--paper:#fff;--bg:#f1f4f8;--ink:#21334a;--muted:#52647b;--line:#d9e1eb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 'Segoe UI','Microsoft YaHei','PingFang SC',sans-serif}
header{background:var(--navy);color:white;padding:32px max(24px,calc((100% - 1180px)/2));border-top:5px solid #427cce}
.brand{letter-spacing:.16em;font:12px Consolas,monospace;color:#c4d7f0}h1{font-size:32px;letter-spacing:.02em;margin:12px 0 8px}header p{color:#d1ddeb;margin:4px 0}
nav{display:flex;gap:24px;flex-wrap:wrap;margin-top:20px}nav a{color:white;text-decoration:underline;text-underline-offset:5px}a:focus-visible,summary:focus-visible{outline:3px solid #dc9e32;outline-offset:4px}
main{max-width:1228px;margin:auto;padding:24px}section{background:var(--paper);border:1px solid var(--line);margin-bottom:22px;padding:24px;scroll-margin-top:16px}
h2{font-size:20px;margin:0 0 16px}h3{font-size:16px;margin:18px 0 8px}.scope{border-left:4px solid var(--blue);padding:12px 16px;background:#edf3fc;margin:0 0 22px}
.metrics,.states{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}.metric,.state{background:white;padding:14px}
.metric strong,.state strong{display:block;font:26px/1.3 Consolas,monospace;color:var(--navy)}.caption{color:var(--muted);font-size:12px}.state{border-top:3px solid #6b809b}.verified{border-color:#377a62}.blocked{border-color:#b34646}.risk{border-color:#ac7723}.unknown{border-color:#5b74a2}.not_applicable{border-color:#85919d}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#f5f7fa;color:#425672}code{font:12px/1.6 Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere;word-break:break-word}.identifier{max-width:40ch}p,td,li,dd{overflow-wrap:anywhere}
details.issue{margin:10px 0;border:1px solid var(--line);border-left:3px solid var(--blue);background:white}summary{cursor:pointer;padding:14px;line-height:1.6}summary b{color:var(--blue);margin-right:12px}.issue-body{padding:0 18px 16px}dl{display:grid;grid-template-columns:145px minmax(0,1fr);gap:8px 16px;margin:8px 0}dt{color:var(--muted)}dd{margin:0}.tag{font:12px Consolas,monospace;color:var(--muted);margin-right:12px}.empty{color:var(--muted)}footer{color:var(--muted);font-size:12px;padding:0 24px 32px;text-align:center}
@media(max-width:720px){main{padding:12px}header{padding:24px 18px}section{padding:18px}h1{font-size:26px}.metrics,.states{grid-template-columns:repeat(2,minmax(0,1fr))}dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:10px}nav{gap:14px}}
@media print{body{background:white}header{background:white;color:var(--ink);padding:16px}header p,.brand,nav a{color:var(--ink)}main{padding:0}section{break-inside:avoid}nav{display:none}}
""".strip()
LABELS = {"verified": "集合内已验证", "blocked": "静态分析阻断", "risk": "需要核查", "unknown": "无法确认", "not_applicable": "不适用"}


def _e(value) -> str:
    return html.escape(display_text(value), quote=True)


def _table(headers, rows):
    head = "".join(f"<th scope=\"col\">{_e(label)}</th>" for label in headers)
    body = "".join("<tr>" + "".join(f"<td><code>{_e(value)}</code></td>" for value in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>' if body else '<p class="empty">无记录 / No records</p>'


def to_html(report: dict, *, generated_at: str | None = None) -> str:
    """Timestamp is render metadata; never changes the canonical scan result."""
    view = report_view(report)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    style_hash = base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode("ascii")
    csp = f"default-src 'none'; style-src 'sha256-{style_hash}'; base-uri 'none'; form-action 'none'"
    parts = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
             f'<meta http-equiv="Content-Security-Policy" content="{_e(csp)}">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>n8n Workflow Doctor · 迁移诊断报告</title><style>{CSS}</style></head><body>',
             '<header><div class="brand">WORKFLOW DOCTOR / OFFLINE REVIEW</div><h1>工作流迁移诊断报告</h1>',
             f'<p>生成时间 / Generated: <time>{_e(generated_at)}</time></p><p>输入 / Input: {_e(report.get("input"))}</p>',
             '<nav aria-label="报告章节"><a href="#overview">诊断总览</a><a href="#workflows">工作流</a><a href="#dependencies">依赖</a><a href="#issues">检查明细</a><a href="#review">人工核查</a></nav></header><main>',
             '<p class="scope"><strong>目标环境兼容性：Unknown</strong> · 离线静态证据。集合内匹配不代表目标实例可导入或可运行。</p>',
             '<section id="overview"><h2>诊断总览 / Overview</h2><div class="metrics">']
    for key, label in (("file_count", "扫描 JSON 文件"), ("workflow_count", "结构有效工作流"), ("node_count", "有效工作流节点"),
                       ("connection_count", "节点连接"), ("risk_count", "迁移提醒")):
        value = view["summary"][key]
        parts.append(f'<div class="metric"><span>{label}</span><strong>{_e(value if value is not None else "Unknown")}</strong><span class="caption">{key}</span></div>')
    parts.append('</div><h3>五类诊断状态 / Assessments</h3><div class="states">')
    for kind in ASSESSMENTS:
        parts.append(f'<div class="state {kind}"><span>{LABELS[kind]}</span><strong>{view["assessment_counts"][kind]}</strong><span class="caption">{kind}</span></div>')
    parts.append('</div><h3>全部计数 / Counts</h3>')
    if report.get('analysis',{}).get('diagnostics'):
        parts.append('<h3>统一诊断统计（全量导入集合）</h3>')
        parts.append(_table(('指标','数量'), ((k,v) for k,v in report['analysis']['diagnostics']['statistics'].items() if not isinstance(v,dict))))
    parts.append(_table(("指标 / Metric", "数量 / Count"), view["summary"].items()))
    parts.append(_table(("严重等级 / Severity", "检查数 / Checks"), view["severity_counts"].items()))
    parts.append(f'<p>批次完成 / Complete: {_e(report["complete"])}。工作流与节点计数仅覆盖结构有效输入；状态数按检查项计数。</p></section>')
    if "analysis" not in report:
        parts.append('<p class="scope">本报告仅做结构扫描；完整依赖和迁移核查请使用 analyze 命令。</p>')
    parts.append('<section id="workflows"><h2>工作流列表 / Workflows</h2>')
    parts.append(_table(("本地文件", "工作流身份指纹", "身份类型"), ((r["file"], r["workflow_id"], r["identity_kind"]) for r in view["workflows"])))
    parts.append('</section><section id="dependencies"><h2>迁移依赖 / Dependencies</h2>')
    analysis = report.get("analysis", {})
    if analysis:
        parts.append(_table(("依赖指标", "数量"), analysis["summary"].items()))
    parts.append(_table(("依赖", "类型", "状态", "工作流", "证据位置"), ((d["id"], d["kind"], d["status"], d["workflow_id"], d["evidence_location"]) for d in view["dependencies"])))
    parts.append('<h3>间接依赖 / Indirect dependencies</h3>')
    parts.append(_table(("工作流", "可达目标（排除直接邻居）"), ((d["workflow_id"], ", ".join(d["targets"])) for d in analysis.get("indirect_dependencies", []))))
    parts.append('</section><section id="issues"><h2>检查明细 / Findings</h2>')
    for item in view["issues"]:
        parts.append(f'<p><b>{_e(item["rule_name"])}</b> · {_e(item["finding_id"])} · {_e(item["scope_zh"])} · {_e(item["status_zh"])}</p>')
        parts.append(f'<details class="issue"><summary><b>{_e(item["rule_id"])}</b><span class="tag">{_e(item.get("assessment", "risk"))} / {_e(item["severity"])}</span>{_e(item["message_zh"])}</summary><div class="issue-body"><dl>')
        parts.append(f'<dt>英文技术描述</dt><dd>{_e(item["message"])}</dd>')
        for label, key in (("Status", "status"), ("Workflow ID", "workflow_id"), ("Node ID", "node_id"), ("File", "file"),
                           ("Evidence location", "evidence_location"), ("Recommendation", "recommendation"), ("Confidence", "confidence"), ("Verification scope", "verification_scope")):
            parts.append(f'<dt>{label}</dt><dd>{_e(item.get(key))}</dd>')
        for label,key in (("中文说明","message_zh"),("中文建议","recommendation_zh"),("节点定位","node_label"),("无法确认原因","unknown_reason"),("所需证据","required_evidence"),("人工核查","recommended_verification")):
            parts.append(f'<dt>{label}</dt><dd>{_e(item.get(key))}</dd>')
        if item.get("location_details"):
            parts.append(f'<dt>Position</dt><dd>{_e(json.dumps(item["location_details"], sort_keys=True))}</dd>')
        parts.append('</dl></div></details>')
    if not view["issues"]:
        parts.append('<p class="empty">已实现的检查未发现问题；兼容性仍未知。</p>')
    parts.append('<h3>输入错误 / Input errors</h3>')
    parts.append(_table(("错误码", "原因", "文件", "位置", "建议"), ((e["code"], e["message"], e.get("file", report.get("input")), e["location"], e["suggestion"]) for e in report["errors"])))
    parts.append('<h3>跳过的输入 / Skipped</h3>')
    parts.append(_table(("文件", "原因"), ((s["file"], s["reason"]) for s in report["skipped"])))
    parts.append('</section><section id="review"><h2>人工核查 / Human review</h2>')
    parts.append(_table(("状态", "工作流", "证据位置", "核查内容"), ((m["status"], m.get("workflow_id"), m["evidence_location"], m["message"]) for m in view["manual_review_items"])))
    parts.append('</section><section><h2>免责声明与限制 / Scope</h2>')
    parts.append('<p>本工具不执行工作流，不连接 n8n，不验证真实凭证、资源、发布状态或运行权限。名称和参数原文默认省略；身份为指纹，本地路径仍可见。动态表达式、未知版本、第三方节点语义及真实导出兼容性仍需人工核查。</p>')
    parts.append(f'<p>{_e(analysis.get("notice", ""))}</p><p>{_e(report["notice"])}</p></section></main><footer>n8n Workflow Doctor · 本地静态诊断 / Local static diagnostics</footer></body></html>')
    return "\n".join(parts) + "\n"
