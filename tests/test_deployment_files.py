"""Public deployment exceptions stay narrow and media cannot change silently."""
import unittest
from pathlib import Path
from tools.review_public_files import PUBLIC_DEPLOYMENT, PUBLIC_IMAGES, review_blob


class DeploymentPublicFilesTests(unittest.TestCase):
    def test_only_explicit_deployment_config_is_allowed(self):
        for path in PUBLIC_DEPLOYMENT:
            self.assertEqual(review_blob(path, b'public configuration'), [])
        for path in ('deploy/backend/private.lock', 'deploy/frontend/private.conf', 'other/Dockerfile', 'deploy/backend/.env'):
            self.assertTrue(review_blob(path, b'private'))

    def test_public_image_bytes_are_verified_and_other_images_denied(self):
        for path in PUBLIC_IMAGES:
            raw = Path(path).read_bytes()
            self.assertEqual(review_blob(path, raw), [])
            self.assertEqual(review_blob(path, raw + b'changed')[0]['code'], 'PUBLIC_IMAGE_HASH')
        self.assertTrue(review_blob('docs/images/customer.png', b'private'))
