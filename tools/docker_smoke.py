"""Real local Compose acceptance. Synthetic inputs only; no fake Docker pass."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8080'
MARKER = 'FABRICATED_SPRINT6_PRIVATE_VALUE'


class CheckFailed(Exception):
    pass


def require(condition, code):
    if not condition:
        raise CheckFailed(code)


def docker(*args):
    try:
        return subprocess.run(['docker', *args], cwd=ROOT, check=True, capture_output=True, timeout=90).stdout
    except (OSError, subprocess.SubprocessError):
        raise CheckFailed('DOCKER_OPERATION_FAILED') from None


def local_engine():
    configured = os.environ.get('DOCKER_HOST', '')
    endpoint = configured or json.loads(docker('context', 'inspect', '--format', '{{json .Endpoints.docker.Host}}'))
    require(endpoint.startswith(('unix:///', 'npipe:////./pipe/')), 'LOCAL_DOCKER_ENGINE_REQUIRED')
    require(docker('info', '--format', '{{.OSType}}').strip() == b'linux', 'LINUX_CONTAINERS_REQUIRED')


def request(path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    try:
        result = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        result = error
    except (OSError, urllib.error.URLError):
        raise CheckFailed('LOCAL_HTTP_UNAVAILABLE') from None
    with result:
        raw = result.read(16 * 1024 * 1024 + 1)
        require(len(raw) <= 16 * 1024 * 1024, 'RESPONSE_LIMIT_EXCEEDED')
        return result.status, result.headers, raw


def upload(files):
    boundary = 'doctor-' + uuid.uuid4().hex
    parts = []
    for filename, raw in files:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + raw + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return request('/api/v1/scans', b''.join(parts), {'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Origin': BASE})


def workflow(identifier='S6-A', target=None):
    nodes = [{'id': 'one', 'name': '中文开始', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'position': [0, 0], 'parameters': {}}]
    if target:
        nodes.append({'id': 'call', 'name': 'call', 'type': 'n8n-nodes-base.executeWorkflow', 'typeVersion': 1.2, 'position': [200, 0], 'parameters': {'workflowId': {'__rl': True, 'mode': 'id', 'value': target}}})
    return {'id': identifier, 'name': '合成验收 <script>never_execute()</script>', 'nodes': nodes, 'connections': {}, 'settings': {}}


def archive(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, raw in entries:
            zf.writestr(filename, raw)
    return out.getvalue()


def wait_healthy():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if request('/health')[0] == 200:
                return
        except CheckFailed:
            pass
        time.sleep(0.5)
    raise CheckFailed('HEALTH_DEADLINE_EXCEEDED')


def inspect_runtime():
    network = None
    for service, uid in (('backend', '10001:10001'), ('frontend', '101:101')):
        cid = docker('compose', 'ps', '-q', service).decode().strip()
        require(bool(cid), 'CONTAINER_MISSING')
        data = json.loads(docker('inspect', cid))[0]
        require(data['Config']['User'] == uid, 'CONTAINER_USER_INVALID')
        cfg = data['HostConfig']
        require(cfg['ReadonlyRootfs'] and 'ALL' in cfg['CapDrop'], 'CONTAINER_PRIVILEGES_INVALID')
        require('no-new-privileges:true' in cfg['SecurityOpt'], 'NO_NEW_PRIVILEGES_MISSING')
        require(cfg['Memory'] > 0 and cfg['PidsLimit'] > 0, 'CONTAINER_BUDGET_MISSING')
        require('/tmp' in cfg['Tmpfs'], 'TMPFS_MISSING')
        require(not any(m['Type'] == 'bind' for m in data['Mounts']), 'HOST_BIND_MOUNT_UNEXPECTED')
        if service == 'backend':
            network = data['NetworkSettings']['Networks']
            require(not cfg.get('PortBindings'), 'BACKEND_PORT_EXPOSED')
            docker('compose', 'exec', '-T', 'backend', 'python', '-c',
                   'import os,pathlib; assert os.geteuid()==10001; assert not pathlib.Path("/app/tests").exists(); assert not pathlib.Path("/app/.env").exists(); assert not any(p.is_file() for p in pathlib.Path("/tmp").iterdir())')
    require(network is not None and len(network) == 1, 'UNEXPECTED_NETWORK_ATTACHMENT')
    network_info = json.loads(docker('network', 'inspect', next(iter(network.values()))['NetworkID']))[0]
    require(network_info['Internal'], 'NETWORK_NOT_INTERNAL')
    # A fixed test endpoint, never an input URL. No application bytes are sent.
    docker('compose', 'exec', '-T', 'backend', 'python', '-c',
           'import socket,sys\ns=socket.socket();s.settimeout(2)\ntry:s.connect(("1.1.1.1",443))\nexcept OSError:sys.exit(0)\nelse:sys.exit(1)\nfinally:s.close()')


def run(restart=False):
    wait_healthy()
    checks = []
    for path in ('/', '/health', '/docs', '/openapi.json', '/docs-assets/swagger-ui-bundle.js', '/scans/' + '0' * 32):
        require(request(path)[0] == 200, 'PUBLIC_ROUTE_FAILED')
    checks.append('frontend_health_docs_assets_spa')
    fixture = ROOT / 'tests/fixtures/valid.json'
    original = hashlib.sha256(fixture.read_bytes()).hexdigest()
    status, _, raw = upload([('fabricated.json', fixture.read_bytes())])
    require(status == 200 and json.loads(raw)['status'] == 'completed', 'JSON_UPLOAD_FAILED')
    checks.append('real_json_upload')
    pairs = [('A.json', json.dumps(workflow('S6-A', 'S6-B')).encode()), ('B.json', json.dumps(workflow('S6-B')).encode())]
    for files in (pairs, [('fabricated.zip', archive(pairs))]):
        status, _, raw = upload(files)
        require(status == 200 and json.loads(raw)['workflow_count'] == 2, 'BATCH_UPLOAD_FAILED')
    checks.append('multi_json_zip_dependencies')
    hostile = workflow()
    hostile['nodes'].append({'id': 'http', 'name': MARKER, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [0, 0], 'parameters': {'url': 'https://never-request.invalid/' + MARKER, 'headerParameters': {'parameters': [{'name': 'Authorization', 'value': MARKER}]}}})
    status, _, raw = upload([('fabricated.json', json.dumps(hostile).encode())])
    require(status == 200 and MARKER.encode() not in raw, 'RISK_SCAN_FAILED')
    scan_id = json.loads(raw)['scan_id']
    for fmt, content_type, ext in (('text', 'text/plain', 'txt'), ('json', 'application/json', 'json'), ('markdown', 'text/markdown', 'md'), ('html', 'text/html', 'html')):
        status, headers, raw = request(f'/api/v1/scans/{scan_id}/report?format={fmt}')
        require(status == 200 and headers.get_content_type() == content_type, 'REPORT_FORMAT_FAILED')
        require(headers.get('Content-Disposition') == f'attachment; filename="scan-{scan_id}.{ext}"', 'UNSAFE_DOWNLOAD_NAME')
        require(MARKER.encode() not in raw, 'REPORT_DISCLOSURE')
        if fmt == 'html':
            require(b'<script' not in raw.lower() and "default-src 'none'" in headers.get('Content-Security-Policy', ''), 'HTML_REPORT_UNSAFE')
    checks.append('four_reports_mime_names_secrets_csp')
    for files, expected in (([('large.json', b' ' * (2 * 1024 * 1024 + 1))], 413),
                            ([('large.zip', b'x' * (8 * 1024 * 1024 + 1))], 413),
                            ([('../bad.json', b'{}')], 400),
                            ([('bad.zip', b'not-a-zip')], 400),
                            ([('traversal.zip', archive([('../escape.json', b'{}')]))], 400)):
        status, _, raw = upload(files)
        require(status == expected and b'error' in raw and b'Traceback' not in raw, 'INPUT_REJECTION_FAILED')
    checks.append('proxy_and_engine_limits_zip_paths_names_sanitized_errors')
    require(request('/health', headers={'Origin': 'https://external.invalid'})[0] == 403, 'ORIGIN_REJECTION_FAILED')
    require(request('/api/v1/scans/' + '0' * 32)[0] == 404, 'MISSING_SCAN_FAILED')
    require(request(f'/api/v1/scans/{scan_id}/report?format=invalid')[0] == 400, 'INVALID_FORMAT_FAILED')
    status, _, raw = upload([('broken.json', b'{broken')])
    require(status == 200 and json.loads(raw)['structural_finding_count'] > 0, 'DIAGNOSTIC_HTTP_SEPARATION_FAILED')
    checks.append('diagnostics_http_errors')
    inspect_runtime()
    require(MARKER.encode() not in docker('compose', 'logs', '--no-color'), 'LOG_DISCLOSURE')
    checks.append('users_readonly_caps_budgets_tmpfs_cleanup_egress_logs')
    stale_id = None
    if restart:
        status, _, raw = upload([('fabricated.json', fixture.read_bytes())])
        require(status == 200, 'PRE_RESTART_UPLOAD_FAILED')
        stale_id = json.loads(raw)['scan_id']
        require(request('/api/v1/scans/' + stale_id)[0] == 200, 'PRE_RESTART_SCAN_ABSENT')
        docker('compose', 'restart', 'backend')
        wait_healthy()
        require(request('/api/v1/scans/' + stale_id)[0] == 404, 'RESTART_DID_NOT_CLEAR_RESULTS')
        checks.append('actual_backend_restart_clears_results')
    require(hashlib.sha256(fixture.read_bytes()).hexdigest() == original, 'ORIGINAL_BYTES_CHANGED')
    checks.append('original_fixture_hash_unchanged')
    return {'state': 'docker_verified', 'checks': checks, 'stale_scan_id': stale_id,
            'scope': 'Synthetic local Docker checks only; not remote CI or real n8n compatibility.'}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--restart', action='store_true', help='Explicitly restart these local Compose services and verify cache loss')
    args = parser.parse_args(argv)
    if not shutil.which('docker'):
        print(json.dumps({'state': 'not_run', 'code': 'DOCKER_UNAVAILABLE'}))
        return 2
    try:
        local_engine()
        result = run(args.restart)
        output = ROOT / 'output/docker-verification.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
        return 0
    except (CheckFailed, ValueError, OSError, KeyError, TypeError) as error:
        code = str(error) if isinstance(error, CheckFailed) else 'DOCKER_VERIFICATION_FAILED'
        print(json.dumps({'state': 'failed', 'code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
