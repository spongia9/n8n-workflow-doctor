"""Synthetic checks for the local commit guard, with no real secret material."""
import json
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from tools.review_public_files import PUBLIC_JSON, main, review_blob


class PublicReviewTests(unittest.TestCase):
    def test_empty_index_is_not_reported_as_successful_review(self):
        output = io.StringIO()
        with patch("tools.review_public_files.subprocess.run", return_value=SimpleNamespace(stdout=b"")), redirect_stdout(output):
            code = main()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "EMPTY_INDEX")

    def test_known_synthetic_json_allowed_and_unknown_export_rejected(self):
        for path in PUBLIC_JSON:
            self.assertEqual(review_blob(path, b'{}'), [])
        self.assertEqual(review_blob("customer/export.json", b'{}')[0]["code"], "UNREVIEWED_JSON")

    def test_private_directories_venvs_and_local_config_rejected(self):
        for path in ("private/settings.py", ".venv-312/pyvenv.cfg", "credentials/settings.md",
                     ".env", ".env.production", "config.local.toml", "logs/session.md",
                     "credentials.yaml", "Credential.yml", "api-key.ini", "api_key.txt", "token.txt"):
            with self.subTest(path=path):
                self.assertEqual(review_blob(path, b'private')[0]["code"], "PRIVATE_PATH")

    def test_private_key_location_reported_without_value(self):
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        findings = review_blob("docs/sample.md", ("first line\n" + marker + "\nSYNTHETIC").encode())
        self.assertEqual(findings[0]["code"], "PRIVATE_KEY")
        self.assertEqual(findings[0]["line"], 2)
        self.assertNotIn(marker, json.dumps(findings))

    def test_token_patterns_report_codes_not_values(self):
        cases = (("AKIA" + "A" * 16, "AWS_ACCESS_KEY"), ("ghp_" + "a" * 36, "GITHUB_TOKEN"),
                 ("sk-" + "a" * 32, "OPENAI_KEY"))
        for value, code in cases:
            findings = review_blob("docs/sample.md", value.encode())
            self.assertEqual(findings[0]["code"], code)
            self.assertNotIn(value, json.dumps(findings))

    def test_synthetic_placeholder_is_not_a_real_token_pattern(self):
        self.assertEqual(review_blob("tests/test_example.py", b"token = 'SYNTHETIC_DO_NOT_EXPORT'"), [])

    def test_links_and_submodules_rejected(self):
        for mode in ("120000", "160000"):
            self.assertEqual(review_blob("docs/example.md", b"target", mode)[0]["code"], "NON_REGULAR_GIT_ENTRY")

    def test_unreviewed_logs_archives_and_keys_rejected(self):
        for path in ("session.log", "session.txt", "workflows.zip", "server.pem"):
            self.assertTrue(review_blob(path, b"ignored"))

    def test_non_utf8_file_is_not_silently_committed(self):
        self.assertEqual(review_blob("docs/sample.md", b"\xff")[0]["code"], "NON_UTF8_FILE")
