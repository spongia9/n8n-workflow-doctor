"""HTTP integration over fabricated bytes; no n8n account or external service."""
import io
import json
import logging
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient
from workflow_doctor.api.app import create_app
from workflow_doctor.api.config import ApiConfig
from workflow_doctor.scanner import scan_uploads
from test_graphs import workflow, node
from test_upload_engine import archive


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app, base_url="http://127.0.0.1")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.raw = json.dumps(workflow()).encode()

    def upload(self, raw=None, name="fabricated.json", client=None):
        return (client or self.client).post("/api/v1/scans", files={"files": (name, self.raw if raw is None else raw, "application/octet-stream")})

    def assert_error(self, response, status, code=None):
        self.assertEqual(response.status_code, status)
        self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(set(response.json()["error"]), {"code", "message"})
        if code:
            self.assertEqual(response.json()["error"]["code"], code)
        self.assertNotIn("Traceback", response.text)

    def test_health_openapi_and_offline_swagger_assets(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok", "mode": "synchronous"})
        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertNotIn("cdn.", docs.text)
        self.assertIn("/docs-assets/swagger-ui-bundle.js", docs.text)
        for name in ("swagger-ui-bundle.js", "swagger-ui.css"):
            self.assertEqual(self.client.get("/docs-assets/" + name).status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("multipart/form-data", schema["paths"]["/api/v1/scans"]["post"]["requestBody"]["content"])
        report_schema = schema["paths"]["/api/v1/scans/{scan_id}/report"]["get"]
        self.assertEqual(set(report_schema["responses"]["200"]["content"]), {"application/json", "text/plain", "text/markdown", "text/html"})
        self.assertEqual(report_schema["responses"]["422"]["content"]["application/json"]["schema"]["$ref"], "#/components/schemas/ErrorResponse")
        self.assert_error(self.client.get("/docs-assets/no-file"), 404)

    def test_json_upload_is_completed_and_retrievable(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(value["status"], "completed")
        self.assertEqual((value["file_count"], value["workflow_count"], value["node_count"]), (1, 1, 2))
        self.assertEqual(value["finding_count"], len(value["findings"]))
        self.assertEqual(self.client.get("/api/v1/scans/" + value["scan_id"]).json(), value)
        self.assertEqual(set(value["report_formats"]), {"text", "json", "markdown", "html"})

    def test_risky_json_is_http_success_and_secrets_names_are_omitted(self):
        secret = "SYNTHETIC_PRIVATE_VALUE"
        raw = json.dumps(workflow(nodes=[node("n", "n8n-nodes-base.httpRequest", {"Authorization": secret, "Cookie": secret}, 4.5)])).encode()
        response = self.upload(raw, name=secret + ".json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("WF011", response.text)
        self.assertNotIn(secret, response.text)
        for format in ("text", "json", "markdown", "html"):
            report = self.client.get(f"/api/v1/scans/{response.json()['scan_id']}/report", params={"format": format})
            self.assertNotIn(secret, report.text)
            self.assertIn("WF011", report.text)

    def test_damaged_json_is_a_completed_diagnostic_with_position(self):
        response = self.upload(b'{"PRIVATE_SENTINEL":')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow_count"], 0)
        self.assertEqual(response.json()["findings"][0]["rule_id"], "WF001")
        self.assertIn("character_offset", response.text)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_nonworkflow_json_is_a_diagnostic(self):
        response = self.upload(b'[1,2,3]')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["findings"][0]["rule_id"], "WF002")

    def test_multiple_json_files_resolve_cross_workflow_dependencies(self):
        a = workflow("A", nodes=[node("call", "n8n-nodes-base.executeWorkflow", {"workflowId": "B"})])
        response = self.client.post("/api/v1/scans", files=[("files", ("A.json", json.dumps(a).encode())), ("files", ("B.JSON", self.raw.replace(b'"A"', b'"B"', 1)))])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file_count"], 2)
        self.assertEqual(response.json()["dependencies"][0]["status"], "Found In Import Set")

    def test_zip_upload_reuses_safety_and_does_not_execute_other_members(self):
        response = self.upload(archive([("A.json", self.raw), ("B.json", self.raw), ("script.py", "PRIVATE_SENTINEL")]), "workflows.zip")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file_count"], 2)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_corrupt_and_traversal_zip_are_safe_http_failures(self):
        self.assert_error(self.upload(b"PK\x03\x04PRIVATE_SENTINEL", "broken.zip"), 400, "ZIP_INVALID")
        response = self.upload(archive([("../PRIVATE_SENTINEL.json", self.raw)]), "unsafe.zip")
        self.assert_error(response, 400, "ZIP_UNSAFE_PATH")
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_mixed_zip_and_json_is_rejected(self):
        response = self.client.post("/api/v1/scans", files=[("files", ("A.zip", archive([("A.json", self.raw)]))), ("files", ("B.json", self.raw))])
        self.assert_error(response, 400, "INPUT_MIXED_ARCHIVE")

    def test_unsupported_type_content_type_and_fields(self):
        self.assert_error(self.upload(b"x", "script.py"), 415, "UPLOAD_TYPE_UNSUPPORTED")
        self.assert_error(self.client.post("/api/v1/scans", content=b"{}"), 415)
        self.assert_error(self.client.post("/api/v1/scans", files={"other": ("a.json", self.raw)}), 422)
        self.assert_error(self.client.post("/api/v1/scans?path=PRIVATE", files={"files": ("a.json", self.raw)}), 422)

    def test_path_and_unicode_filenames_cannot_read_local_files(self):
        for name in ("../PRIVATE.json", "C:\\PRIVATE.json", "/PRIVATE.json", "a/b.json", "a\u202e.json"):
            self.assert_error(self.upload(name=name), 400, "UPLOAD_NAME_INVALID")
        response = self.upload(name="中文工作流.json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("中文工作流", response.text)

    def test_invalid_unknown_scan_ids_and_report_formats_are_unified(self):
        for scan_id in ("bad", "0" * 32):
            self.assert_error(self.client.get("/api/v1/scans/" + scan_id), 404, "SCAN_NOT_FOUND")
        scan_id = self.upload().json()["scan_id"]
        self.assert_error(self.client.get(f"/api/v1/scans/{scan_id}/report?format=PRIVATE"), 400, "REPORT_FORMAT_UNSUPPORTED")

    def test_report_types_encoding_disposition_and_security_headers(self):
        scan_id = self.upload().json()["scan_id"]
        for format, media, extension in (("text", "text/plain", "txt"), ("json", "application/json", "json"),
                                          ("markdown", "text/markdown", "md"), ("html", "text/html", "html")):
            response = self.client.get(f"/api/v1/scans/{scan_id}/report?format={format}")
            self.assertEqual(response.status_code, 200)
            self.assertIn(media, response.headers["content-type"])
            self.assertIn("charset=utf-8", response.headers["content-type"])
            self.assertEqual(response.headers["content-disposition"], f'attachment; filename="scan-{scan_id}.{extension}"')
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertIn("sandbox", response.headers["content-security-policy"])
            response.content.decode("utf-8", errors="strict")

    def test_cors_host_and_origin_are_explicit(self):
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
        response = self.client.options("/api/v1/scans", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], headers["Origin"])
        self.assertNotIn("access-control-allow-credentials", response.headers)
        self.assert_error(self.client.get("/health", headers={"Origin": "https://untrusted.invalid"}), 403)
        self.assert_error(self.client.get("/health", headers={"Host": "untrusted.invalid"}), 400)
        self.assertEqual(self.client.get("/health", headers={"Origin": "http://127.0.0.1"}).status_code, 200)

    def test_limits_apply_to_request_file_count_file_bytes_and_zip_expansion(self):
        cases = [
            (replace(ApiConfig(), max_request_bytes=10), [( "files", ("a.json", self.raw))]),
            (replace(ApiConfig(), scan_limits=replace(ApiConfig().scan_limits, max_files=1)), [("files", ("a.json", self.raw)), ("files", ("b.json", self.raw))]),
            (replace(ApiConfig(), scan_limits=replace(ApiConfig().scan_limits, max_file_bytes=10)), [("files", ("a.json", self.raw))]),
            (replace(ApiConfig(), scan_limits=replace(ApiConfig().scan_limits, max_total_bytes=10)), [("files", ("a.zip", archive([("A.json", self.raw)])))]),
        ]
        for config, files in cases:
            with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
                self.assert_error(client.post("/api/v1/scans", files=files), 413)

    def test_engine_exception_is_not_returned_or_logged(self):
        log = io.StringIO()
        handler = logging.StreamHandler(log)
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            with patch("workflow_doctor.api.service.scan_uploads", side_effect=RuntimeError("PRIVATE_SENTINEL")):
                response = self.upload(name="PRIVATE_SENTINEL.json")
        finally:
            root.removeHandler(handler)
            root.setLevel(previous_level)
        self.assert_error(response, 500, "ENGINE_INTERNAL_ERROR")
        self.assertNotIn("PRIVATE_SENTINEL", response.text)
        self.assertNotIn("PRIVATE_SENTINEL", log.getvalue())
        self.assertEqual(self.upload().status_code, 200)

    def test_render_exception_is_sanitized(self):
        scan_id = self.upload().json()["scan_id"]
        with patch("workflow_doctor.api.app.render_report", side_effect=RuntimeError("PRIVATE_SENTINEL")):
            response = self.client.get(f"/api/v1/scans/{scan_id}/report")
        self.assert_error(response, 500)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_api_and_real_cli_have_identical_canonical_json(self):
        response = self.upload()
        actual = self.client.get(f"/api/v1/scans/{response.json()['scan_id']}/report").json()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upload[0].json"
            path.write_bytes(self.raw)
            result = subprocess.run([sys.executable, "-m", "workflow_doctor", "analyze", path.name], cwd=directory, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(actual, json.loads(result.stdout))
        self.assertEqual(actual, scan_uploads([("upload[0].json", self.raw)]))

    def test_original_public_fixture_hash_is_unchanged(self):
        path = Path("tests/fixtures/valid.json")
        before = sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.upload(path.read_bytes()).status_code, 200)
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), before)

    def test_scan_does_not_access_referenced_files_urls_or_execute_code(self):
        raw = json.dumps(workflow(nodes=[node("code", "n8n-nodes-base.code", {"jsCode": "PRIVATE_SENTINEL"}),
                                        node("n", parameters={"url": "https://never-request.invalid", "path": "/never/read"})])).encode()
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")), patch("pathlib.Path.open", side_effect=AssertionError("file")), patch("os.system", side_effect=AssertionError("execution")):
            response = self.upload(raw)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_busy_requests_are_rejected_without_creating_fake_pending_scans(self):
        entered, release = threading.Event(), threading.Event()
        responses = []
        def slow(files, **kwargs):
            entered.set()
            release.wait(5)
            return scan_uploads(files, **kwargs)
        with patch("workflow_doctor.api.service.scan_uploads", side_effect=slow):
            thread = threading.Thread(target=lambda: responses.append(self.upload()))
            thread.start()
            self.assertTrue(entered.wait(3))
            try:
                self.assert_error(self.upload(), 503, "SCAN_BUSY")
                self.assertEqual(self.client.get("/health").status_code, 200)
            finally:
                release.set()
                thread.join(5)
        self.assertEqual(responses[0].json()["status"], "completed")

    def test_result_and_render_budgets_are_enforced(self):
        for config, code in ((replace(ApiConfig(), max_result_bytes=1), "RESULT_TOO_LARGE"),
                             (replace(ApiConfig(), max_response_bytes=1), "REPORT_TOO_LARGE")):
            with TestClient(create_app(config), base_url="http://127.0.0.1") as client:
                response = self.upload(client=client)
                if code == "REPORT_TOO_LARGE":
                    response = client.get(f"/api/v1/scans/{response.json()['scan_id']}/report")
                self.assert_error(response, 413, code)

    def test_shutdown_clears_cache_and_app_restart_has_no_tasks(self):
        app = create_app()
        with TestClient(app, base_url="http://127.0.0.1") as client:
            value = self.upload(client=client).json()
            self.assertGreater(app.state.store._bytes, 0)
        self.assertEqual(app.state.store._bytes, 0)
        self.assert_error(self.client.get("/api/v1/scans/" + value["scan_id"]), 404)

    def test_multipart_dependency_logs_are_filtered(self):
        self.assertFalse(logging.getLogger("python_multipart.multipart").filter(logging.makeLogRecord({"msg": "PRIVATE_SENTINEL"})))

    def test_malformed_multipart_is_not_an_internal_error_or_payload_echo(self):
        response = self.client.post("/api/v1/scans", content=b"PRIVATE_SENTINEL", headers={"Content-Type": "multipart/form-data; boundary=synthetic"})
        self.assert_error(response, 400)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_download_formats_share_the_identical_stored_diagnostic(self):
        response = self.upload()
        scan_id = response.json()["scan_id"]
        canonical = self.client.get(f"/api/v1/scans/{scan_id}/report?format=json").json()
        from workflow_doctor.reporting import render_report
        for format in ("text", "markdown", "html"):
            actual = self.client.get(f"/api/v1/scans/{scan_id}/report?format={format}").text
            self.assertEqual(actual, render_report(canonical, format, generated_at=response.json()["created_at"]))

    def test_truncated_multipart_rejects_the_entire_batch(self):
        content = (b'--synthetic\r\nContent-Disposition: form-data; name="files"; filename="A.json"\r\n\r\n'
                   + self.raw + b'\r\n--synthetic\r\n')
        before = self.app.state.store._bytes
        response = self.client.post("/api/v1/scans", content=content, headers={"Content-Type": "multipart/form-data; boundary=synthetic"})
        self.assert_error(response, 400, "MULTIPART_INVALID")
        self.assertEqual(self.app.state.store._bytes, before)

    def test_upload_handles_close_on_truncated_and_successful_requests(self):
        import tempfile
        handles = []
        def spool(*args, **kwargs):
            handle = tempfile.SpooledTemporaryFile(*args, **kwargs)
            handles.append(handle)
            return handle
        with patch("starlette.formparsers.SpooledTemporaryFile", side_effect=spool):
            self.assertEqual(self.upload().status_code, 200)
            content = (b'--synthetic\r\nContent-Disposition: form-data; name="files"; filename="A.json"\r\n\r\n'
                       + self.raw + b'\r\n--synthetic\r\n')
            self.assert_error(self.client.post("/api/v1/scans", content=content, headers={"Content-Type": "multipart/form-data; boundary=synthetic"}), 400)
        self.assertTrue(handles)
        self.assertTrue(all(handle.closed for handle in handles))

    def test_allowed_cors_origin_can_read_preparser_limit_errors(self):
        app = create_app(replace(ApiConfig(), max_request_bytes=1))
        with TestClient(app, base_url="http://127.0.0.1") as client:
            response = client.post("/api/v1/scans", content=b"too large", headers={"Origin": "http://localhost:5173"})
            self.assert_error(response, 413)
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
