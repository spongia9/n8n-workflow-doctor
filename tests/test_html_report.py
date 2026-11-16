"""HTML safety, canonical report parity and Chinese rendering, with fabricated data."""
import copy
import html
import json
import re
import unittest
from html.parser import HTMLParser

from test_dependencies import caller
from test_graphs import node, workflow
from workflow_doctor.analysis import analyze_documents
from workflow_doctor.html_report import to_html
from workflow_doctor.reporting import report_view, to_markdown
from workflow_doctor.scanner import make_report, scan_bytes


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs, self.text = [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


def envelope(*values):
    documents = [(f"模拟-{i}.json", value) for i, value in enumerate(values)]
    result = make_report([scan_bytes(json.dumps(value).encode(), source) for source, value in documents], source="模拟输入")
    result["analysis"] = analyze_documents(documents)
    return result


class HtmlReportTests(unittest.TestCase):
    def test_standalone_html_title_time_chinese_and_summary(self):
        report = envelope(workflow())
        text = to_html(report, generated_at="2026-11-06T12:00:00+00:00")
        parsed = Document(text)
        self.assertIn('<meta charset="utf-8">', text)
        self.assertIn('lang="zh-CN"', text)
        for value in ("工作流迁移诊断报告", "2026-11-06T12:00:00+00:00", "模拟-0.json", "node_count", "Unknown"):
            self.assertIn(value, text)
        self.assertEqual(parsed.tags.count("html"), 1)

    def test_renderer_has_no_scripts_remote_assets_forms_or_event_handlers(self):
        parsed = Document(to_html(envelope(workflow())))
        self.assertFalse({"script", "iframe", "object", "embed", "img", "link", "form", "base"} & set(parsed.tags))
        for name, value in parsed.attrs:
            self.assertFalse(name.startswith("on"))
            if name in ("src", "href"):
                self.assertTrue(value.startswith("#"))
        policy = dict(parsed.attrs).get("http-equiv")
        self.assertEqual(policy, "Content-Security-Policy")
        self.assertIn("default-src &#x27;none&#x27;", to_html(envelope(workflow())))

    def test_html_injection_in_input_path_messages_locations_and_suggestions_is_text(self):
        marker = '<script>alert("SYNTHETIC")</script><img src="https://no.invalid" onerror="alert(1)">'
        report = make_report([scan_bytes(b"{", source=marker)], source=marker)
        finding = report["results"][0]["findings"][0]
        for key in ("message", "location", "suggestion"):
            finding[key] = marker
        text = to_html(report, generated_at=marker)
        parsed = Document(text)
        self.assertNotIn("script", parsed.tags)
        self.assertNotIn("img", parsed.tags)
        self.assertIn(marker, "".join(parsed.text))
        self.assertNotIn(marker, text)

    def test_workflow_and_node_names_are_private_even_if_chinese_or_malicious(self):
        data = workflow(nodes=[node("n")])
        data["name"] = "私有中文工作流<script>alert(1)</script>"
        data["nodes"][0]["name"] = "私有节点<img src=x>"
        report = envelope(data)
        for text in (json.dumps(report, ensure_ascii=False), to_markdown(report), to_html(report)):
            self.assertNotIn(data["name"], text)
            self.assertNotIn(data["nodes"][0]["name"], text)

    def test_all_five_states_and_every_required_issue_field_match_json(self):
        a = caller("B")
        a["nodes"].extend([node("dynamic", "n8n-nodes-base.executeWorkflow", {"workflowId": "={{ $json.id }}"}),
                           node("key", "n8n-nodes-base.httpRequest", {"password": "SYNTHETIC_ONLY"}, 4.5)])
        bad = workflow("C")
        bad["nodes"][0].pop("type")
        report = envelope(a, workflow("B"), bad)
        view = report_view(report)
        self.assertTrue(all(view["assessment_counts"].values()))
        text = "".join(Document(to_html(report)).text)
        markdown = re.sub(r"\\([\\`*_\[\]|#])", r"\1", html.unescape(to_markdown(report)))
        for item in view["issues"]:
            for field in ("rule_id", "status", "severity", "message", "recommendation", "evidence_location", "confidence", "assessment"):
                self.assertIn(item[field], text)
                self.assertIn(item[field], markdown)
        self.assertEqual(view["assessment_counts"], report["analysis"]["assessment_counts"])

    def test_dependency_targets_and_indirect_paths_are_preserved_in_all_reports(self):
        a, b = caller("B"), caller("C")
        b["id"] = "B"
        report = envelope(a, b, workflow("C"))
        for item in report["analysis"]["dependencies"]:
            self.assertIn(item["workflow_id"], to_html(report))
            self.assertIn(item["workflow_id"], to_markdown(report))
        for item in report["analysis"]["indirect_dependencies"]:
            for target in item["targets"]:
                self.assertIn(target, to_html(report))
                self.assertIn(target, to_markdown(report))

    def test_all_sensitive_values_are_absent_from_json_markdown_and_html(self):
        secret = "SYNTHETIC_SECRET_DO_NOT_EXPORT"
        data = workflow(nodes=[node("n", "n8n-nodes-base.httpRequest", {"token": secret, "Password": secret, "Cookie": secret,
                                                                   "Authorization": secret, "url": "https://example.invalid/" + secret}, 4.5)])
        data["nodes"][0]["credentials"] = {"syntheticAuth": {"id": "ref", "name": secret, "password": secret}}
        report = envelope(data)
        for text in (json.dumps(report), to_markdown(report), to_html(report)):
            self.assertNotIn(secret, text)
        self.assertEqual(len(report["analysis"]["node_checks"]), 4)

    def test_unicode_controls_and_surrogates_are_visible_not_executable_or_encoding_errors(self):
        report = make_report([scan_bytes(b"{", source="中文\u202e\x00\ud800.json")], source="中文\u202e\x00\ud800.json")
        for text in (to_html(report), to_markdown(report)):
            text.encode("utf-8", errors="strict")
            for raw in ("\u202e", "\x00", "\ud800"):
                self.assertNotIn(raw, text)
            self.assertIn("中文", text)
            self.assertIn("u202e", text)

    def test_rendering_does_not_mutate_diagnostics(self):
        report = envelope(workflow())
        before = copy.deepcopy(report)
        to_html(report)
        to_markdown(report)
        self.assertEqual(report, before)

    def test_structural_only_report_and_errors_do_not_invent_dependency_checks(self):
        report = make_report([scan_bytes(json.dumps(workflow()).encode(), "模拟.json")])
        text = to_html(report)
        self.assertIn("本报告仅做结构扫描", text)
        self.assertEqual(report_view(report)["summary"]["node_count"], 2)
        self.assertEqual(report_view(report)["assessment_counts"]["verified"], 0)
        error = {"code": "ZIP_UNSAFE_PATH", "message": "<script>unsafe</script>", "location": "$", "suggestion": "Review locally", "file": "模拟失败.zip"}
        failed = to_html(make_report(errors=[error]))
        self.assertIn("ZIP_UNSAFE_PATH", failed)
        self.assertIn("模拟失败.zip", failed)
        self.assertIn("模拟失败.zip", to_markdown(make_report(errors=[error])))
        self.assertNotIn("script", Document(failed).tags)

    def test_structural_issues_appear_once_in_normalized_view(self):
        bad = workflow()
        bad["nodes"][0].pop("type")
        report = envelope(bad)
        self.assertEqual(len(report_view(report)["issues"]), len(report["results"][0]["findings"]))
        damaged = make_report([scan_bytes(b'{\n"nodes":', "damaged.json")])
        details = damaged["results"][0]["findings"][0]["location_details"]
        for text in (to_html(damaged), to_markdown(damaged)):
            self.assertIn("character_offset", html.unescape(text).replace("\\_", "_"))
            self.assertIn(str(details["line"]), text)
