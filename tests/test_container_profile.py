"""Container adaptation keeps the normal API and CLI's security boundary."""
import io
import json
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from workflow_doctor.api.container import create_container_app, main


class ContainerProfileTests(unittest.TestCase):
    def test_entry_refuses_missing_docker_marker_or_explicit_flag(self):
        for flag, marker in ((None, True), ('0', True), ('1', False)):
            with self.subTest(flag=flag, marker=marker), patch('os.environ.get', return_value=flag), patch('pathlib.Path.is_file', return_value=marker), patch('uvicorn.run') as run:
                with self.assertRaises(SystemExit):
                    main()
                run.assert_not_called()

    def test_explicit_container_entry_uses_bounded_graceful_single_process(self):
        with patch('os.environ.get', return_value='1'), patch('pathlib.Path.is_file', return_value=True), patch('uvicorn.run') as run:
            main()
        options = run.call_args.kwargs
        self.assertEqual(options['host'], '0.0.0.0')
        self.assertEqual(options['workers'], 1)
        self.assertFalse(options['proxy_headers'])
        self.assertFalse(options['access_log'])
        self.assertEqual(options['timeout_graceful_shutdown'], 20)
        self.assertEqual(options['limit_concurrency'], 4)

    def test_proxy_origin_and_host_are_validated_without_dev_cors_exception(self):
        with TestClient(create_container_app(), base_url='http://127.0.0.1:8080') as client:
            self.assertEqual(client.get('/health', headers={'Origin': 'http://127.0.0.1:8080'}).status_code, 200)
            for origin in ('http://127.0.0.1:5173', 'https://external.invalid', 'null'):
                self.assertEqual(client.get('/health', headers={'Origin': origin}).status_code, 403)
            self.assertEqual(client.get('/health', headers={'Host': 'backend:8000'}).status_code, 400)
            self.assertEqual(client.get('/health', headers={'Host': 'external.invalid'}).status_code, 400)

    def test_same_origin_upload_and_report_remain_the_existing_contract(self):
        raw = b'{"name":"fabricated","nodes":[],"connections":{}}'
        with TestClient(create_container_app(), base_url='http://localhost:8080') as client:
            response = client.post('/api/v1/scans', files={'files': ('synthetic.json', raw)}, headers={'Origin': 'http://localhost:8080'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'completed')
            self.assertEqual(client.get('/api/v1/scans/' + response.json()['scan_id'] + '/report?format=json').status_code, 200)


if __name__ == '__main__':
    unittest.main()
