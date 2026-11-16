"""Fabricated build outputs and process records; never real workflows."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from workflow_doctor.api.native import CSP, create_native_app
from workflow_doctor.api.native_runtime import InstanceLock, control, read_state, write_state
from workflow_doctor.api.app import create_app
from tools.review_public_files import path_issue


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'assets').mkdir()
        (self.root / 'index.html').write_text('<!doctype html><html lang="zh"><body>中文</body></html>', encoding='utf-8')
        (self.root / 'native-build.txt').write_text('api=same-origin\n')
        (self.root / 'assets/app-123.js').write_text('/* trusted fabricated build */')
        self.client = TestClient(create_native_app(self.root), base_url='http://127.0.0.1')

    def test_spa_deep_routes_and_security_headers(self):
        for path in ['/', '/upload', '/scans/' + 'a'*32, '/scans/' + 'a'*32 + '/graph', '/scans/' + 'a'*32 + '/reports']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('中文', response.text)
            self.assertEqual(response.headers['content-security-policy'], CSP)
            self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.head('/').content, b'')

    def test_api_docs_and_unknown_paths_preserved(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok', 'mode': 'synchronous'})
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertIn('sha256-', self.client.get('/docs').headers['content-security-policy'])
        self.assertEqual(self.client.get('/openapi.json').json(), TestClient(create_app(), base_url='http://127.0.0.1').get('/openapi.json').json())
        for path in ['/api/missing', '/api/v1/scans/'+'b'*32, '/assets/missing.js', '/missing', '/native-build.txt']:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_asset_content_and_methods(self):
        result = self.client.get('/assets/app-123.js')
        self.assertEqual(result.status_code, 200)
        self.assertIn('javascript', result.headers['content-type'])
        self.assertEqual(self.client.post('/upload').status_code, 405)

    def test_paths_never_touch_request_selected_filesystem(self):
        with patch('pathlib.Path.resolve', side_effect=AssertionError('request must not resolve files')):
            for path in ['/%5c%5cserver%5cshare', '/C:%5cWindows', '/assets/..%5cprivate', '/.env', '/%2e%2e/private', '/assets/%00x.js']:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn('private', response.text)

    def test_foreign_host_origin_rejected_and_no_dev_cors(self):
        self.assertEqual(self.client.get('/', headers={'Host':'attacker.invalid'}).status_code, 400)
        self.assertEqual(self.client.get('/', headers={'Origin':'http://127.0.0.1:5173'}).status_code, 403)

    def test_bad_build_mode_and_unexpected_assets_rejected(self):
        (self.root / 'native-build.txt').write_text('api=http://127.0.0.1:8000\n')
        with self.assertRaises(ValueError): create_native_app(self.root)
        (self.root / 'native-build.txt').write_text('api=same-origin\n')
        (self.root / 'assets/private.json').write_text('{}')
        with self.assertRaises(ValueError): create_native_app(self.root)

    def test_unc_build_rejected_before_resolve(self):
        with patch('pathlib.Path.resolve', side_effect=AssertionError):
            with self.assertRaises(ValueError): create_native_app(Path('//server/share'))


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime'
        self.runtime.mkdir()

    def test_record_validation_and_size_limit(self):
        write_state(self.runtime, 8080, 'a'*32)
        self.assertEqual(read_state(self.runtime)['port'], 8080)
        for data in ['[]', '{}', 'x'*513, json.dumps({'pid':1,'port':8080,'instance':'../escape'})]:
            (self.runtime/'instance.json').write_text(data)
            self.assertIsNone(read_state(self.runtime))

    def test_stop_stale_pid_never_kills_process(self):
        write_state(self.runtime, 8080, 'a'*32)
        with patch('subprocess.Popen') as popen, patch('os.kill') as kill:
            self.assertEqual(control('stop', self.root), 0)
            popen.assert_not_called()
            kill.assert_not_called()
        self.assertFalse((self.runtime/('a'*32+'.stop')).exists())
        self.assertIsNone(read_state(self.runtime))

    def test_lock_probes_do_not_grow_runtime_file(self):
        from workflow_doctor.api.native_runtime import locked
        for _ in range(20):
            self.assertFalse(locked(self.runtime))
        self.assertEqual((self.runtime/'instance.lock').stat().st_size, 1)

    def test_health_probe_never_follows_redirects(self):
        from workflow_doctor.api.native_runtime import health
        with patch('workflow_doctor.api.native_runtime.HTTPConnection') as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 302
            self.assertFalse(health(8080))
            factory.assert_called_once_with('127.0.0.1', 8080, timeout=1)
            connection.request.assert_called_once_with('GET', '/health')
            response.read.assert_not_called()
            connection.close.assert_called_once()

    def test_lock_exclusivity(self):
        with InstanceLock(self.runtime):
            with self.assertRaises(RuntimeError):
                with InstanceLock(self.runtime): pass

    def test_stop_invalid_record_fails_closed(self):
        with InstanceLock(self.runtime):
            self.assertEqual(control('stop', self.root), 1)

    def test_start_port_conflict_does_not_launch(self):
        import socket
        with socket.socket() as listener, patch('subprocess.Popen') as popen:
            listener.bind(('127.0.0.1',0)); listener.listen()
            self.assertEqual(control('start', self.root, listener.getsockname()[1]), 1)
            popen.assert_not_called()

    def test_public_script_allowlist_remains_narrow(self):
        for path in ['start.ps1','stop.ps1','status.ps1','scripts/native.ps1']:
            self.assertIsNone(path_issue(path))
        for path in ['other.ps1','.runtime/instance.json','frontend/native-test-results/workflow.json']:
            self.assertIsNotNone(path_issue(path))


if __name__ == '__main__': unittest.main()
