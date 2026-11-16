"""Audit exact public Swagger assets; arbitrary JavaScript remains rejected."""
import unittest
from pathlib import Path

from tools.review_public_files import VENDORED_ASSETS, review_blob


class AssetTests(unittest.TestCase):
    def test_upstream_bytes_match_audited_hashes(self):
        for path in VENDORED_ASSETS:
            self.assertEqual(review_blob(path, Path(path).read_bytes()), [])

    def test_modified_or_unreviewed_assets_are_rejected(self):
        path = next(iter(VENDORED_ASSETS))
        self.assertEqual(review_blob(path, b"modified")[0]["code"], "VENDORED_ASSET_HASH")
        self.assertTrue(review_blob("docs/arbitrary.js", b"example"))
