"""The deliberately hostile HTTP fixture is test-only and keeps API guards."""
import unittest
from starlette.testclient import TestClient
from tools.e2e_hostile_api import create_hostile_app
from workflow_doctor.api.app import create_app


class HostileHarnessTests(unittest.TestCase):
    def test_real_transport_fixture_requires_an_existing_scan_and_keeps_origin_guard(self):
        with TestClient(create_hostile_app(), base_url='http://127.0.0.1') as client:
            self.assertEqual(client.get('/api/v1/scans/' + '0' * 32 + '/report?format=html').status_code, 404)
            scan_id = client.post('/api/v1/scans', files={'files': ('fake.json', b'{"nodes":[],"connections":{}}')}).json()['scan_id']
            path = '/api/v1/scans/' + scan_id + '/report?format=html'
            self.assertIn('<script>', client.get(path).text)
            self.assertEqual(client.get(path, headers={'Origin': 'https://external.invalid'}).status_code, 403)

    def test_production_app_does_not_enable_hostile_fixture(self):
        with TestClient(create_app(), base_url='http://127.0.0.1') as client:
            scan_id = client.post('/api/v1/scans', files={'files': ('fake.json', b'{"nodes":[],"connections":{}}')}).json()['scan_id']
            html = client.get('/api/v1/scans/' + scan_id + '/report?format=html')
            self.assertNotIn('<script>', html.text)
            self.assertNotIn('SPRINT6_SCRIPT_EXECUTED', html.text)
