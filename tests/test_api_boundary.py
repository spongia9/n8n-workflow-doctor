"""Raw ASGI body/timeout bounds, independent of client Content-Length behavior."""
import asyncio
import json
import unittest
from dataclasses import replace

from workflow_doctor.api.boundary import RequestBoundary
from workflow_doctor.api.config import ApiConfig


class BoundaryTests(unittest.TestCase):
    def invoke(self, messages, *, headers=(), config=None, hang=False):
        sent, calls = [], []
        values = iter(messages)

        async def app(scope, receive, send):
            calls.append(await receive())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def receive():
            if hang:
                await asyncio.sleep(5)
            return next(values)

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "method": "POST", "path": "/api/v1/scans", "scheme": "http",
                 "headers": [(b"host", b"127.0.0.1"), *headers]}
        asyncio.run(RequestBoundary(app, config or ApiConfig())(scope, receive, send))
        return sent, calls

    def test_chunked_body_is_bounded_before_downstream_parser(self):
        sent, calls = self.invoke([{"type": "http.request", "body": b"A" * 6, "more_body": True},
                                  {"type": "http.request", "body": b"B" * 6}],
                                 config=replace(ApiConfig(), max_request_bytes=10))
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(calls, [])

    def test_false_content_length_does_not_bypass_actual_byte_limit(self):
        sent, calls = self.invoke([{"type": "http.request", "body": b"A" * 11}],
                                 headers=[(b"content-length", b"1")], config=replace(ApiConfig(), max_request_bytes=10))
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(calls, [])

    def test_declared_oversize_encoding_and_duplicate_length_fail_without_reading(self):
        cases = [([(b"content-length", b"999999999")], 413),
                 ([(b"content-length", b"PRIVATE_SENTINEL")], 400),
                 ([(b"content-length", b"1"), (b"content-length", b"2")], 400),
                 ([(b"content-encoding", b"gzip")], 415)]
        for headers, expected in cases:
            sent, calls = self.invoke([], headers=headers)
            self.assertEqual(sent[0]["status"], expected)
            self.assertEqual(calls, [])
            self.assertNotIn("PRIVATE_SENTINEL", str(sent))

    def test_successful_replay_is_complete_and_has_security_headers(self):
        sent, calls = self.invoke([{"type": "http.request", "body": b"abc", "more_body": True},
                                  {"type": "http.request", "body": b"def"}])
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(calls, [{"type": "http.request", "body": b"abcdef", "more_body": False}])
        self.assertIn((b"cache-control", b"no-store"), sent[0]["headers"])

    def test_upload_deadline_and_disconnect_are_explicit_failures(self):
        sent, calls = self.invoke([], hang=True, config=replace(ApiConfig(), upload_timeout_seconds=1))
        self.assertEqual(sent[0]["status"], 408)
        self.assertEqual(calls, [])
        sent, calls = self.invoke([{"type": "http.disconnect"}])
        self.assertEqual(sent[0]["status"], 400)
        self.assertEqual(calls, [])
