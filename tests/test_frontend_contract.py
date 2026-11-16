"""Frontend additions preserve the real HTTP contract and public-file policy."""
import unittest
from tools.export_frontend_contract import DEST, generate
from tools.review_public_files import review_blob


class FrontendContractTests(unittest.TestCase):
    def test_generated_envelope_matches_real_openapi(self):
        self.assertEqual(DEST.read_text(encoding="utf-8"), generate())

    def test_only_explicit_frontend_config_json_is_public(self):
        for path in ("frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json"):
            self.assertEqual(review_blob(path, b'{}'), [])
        for path in ("frontend/export.json", "frontend/tests/private-data.json", "frontend/src/real-workflow.json"):
            self.assertTrue(review_blob(path, b'{}'))

    def test_frontend_source_and_entry_only_allowlist(self):
        for path in ("frontend/src/App.vue", "frontend/tests/client.test.ts", "frontend/src/styles/main.css", "frontend/index.html"):
            self.assertEqual(review_blob(path, b"source"), [])
        for path in ("frontend/report.html", "frontend/dist/index.html", "outside.ts", "frontend/src/private/record.ts",
                     "frontend/node_modules/library/README.md", "frontend/test-results/result.md"):
            self.assertTrue(review_blob(path, b"source"))


if __name__ == "__main__":
    unittest.main()
