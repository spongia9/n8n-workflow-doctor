"""Bounded local process control. Stop requests never signal or kill a PID."""
import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


class InstanceLock:
    def __init__(self, directory):
        self.directory = Path(directory)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.stream = (self.directory / 'instance.lock').open('a+b')
        if self.stream.seek(0, 2) == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Native instance already active') from None
        return self

    def __exit__(self, *args):
        self.stream.close()


def locked(directory):
    try:
        with InstanceLock(directory):
            return False
    except RuntimeError:
        return True


def write_state(directory, port, instance):
    target = directory / 'instance.json'
    temp = directory / 'instance.tmp'
    temp.write_text(json.dumps({'pid': os.getpid(), 'port': port, 'instance': instance}), encoding='utf-8')
    temp.replace(target)


def read_state(directory):
    try:
        path = directory / 'instance.json'
        if path.stat().st_size > 512:
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            return None
        if (set(value) == {'pid', 'port', 'instance'} and type(value['pid']) is int and value['pid'] > 0
                and type(value['port']) is int and 1024 <= value['port'] <= 65535
                and isinstance(value['instance'], str) and re.fullmatch('[a-f0-9]{32}', value['instance'])):
            return value
    except (OSError, ValueError, TypeError):
        pass
    return None


def health(port):
    connection = HTTPConnection('127.0.0.1', port, timeout=1)
    try:
        # No proxy or redirect handler: even an unrelated local listener cannot
        # redirect process-control probes to a remote host.
        connection.request('GET', '/health')
        response = connection.getresponse()
        return response.status == 200 and json.loads(response.read(1024)) == {'status': 'ok', 'mode': 'synchronous'}
    except Exception:
        return False
    finally:
        connection.close()


def control(action, root, port=8080):
    root = Path(root).resolve()
    directory = root / '.runtime'
    state = read_state(directory)
    active = locked(directory)
    if action == 'status':
        if active and state and health(state['port']):
            print(f"RUNNING http://127.0.0.1:{state['port']} PID={state['pid']}")
            return 0
        print('STOPPED' if not active else 'STARTING_OR_UNHEALTHY')
        return 3
    if action == 'stop':
        if not active:
            # Remove only our stale record under the same ownership lock. PID
            # reuse never authorizes signalling or terminating another process.
            with InstanceLock(directory):
                (directory / 'instance.json').unlink(missing_ok=True)
            print('STOPPED: no owned native instance; no process was terminated')
            return 0
        if not state:
            print('STOP_REFUSED: active instance has no valid control record; no process was terminated')
            return 1
        (directory / (state['instance'] + '.stop')).write_bytes(b'stop')
        for _ in range(125):
            if not locked(directory):
                print('STOPPED: graceful shutdown; cached scan results cleared')
                return 0
            time.sleep(.2)
        print('STOP_TIMEOUT: active scan may still be finishing; no process was killed')
        return 1
    if not 1024 <= port <= 65535:
        raise ValueError('PORT_INVALID: use 1024..65535')
    if active:
        if state and state['port'] == port and health(port):
            print(f'ALREADY_RUNNING http://127.0.0.1:{port}')
            return 0
        print('START_REFUSED: another owned instance is active; run status.ps1')
        return 1
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            print('PORT_IN_USE: choose -Port or stop the owning application yourself')
            return 1
    from .native import create_native_app
    if not (root / 'frontend' / 'dist' / 'index.html').is_file():
        print('BUILD_MISSING: run start.ps1 -Prepare before starting')
        return 1
    create_native_app(root / 'frontend' / 'dist')
    # Empty stale metadata before launch, under the short-lived lock.
    with InstanceLock(directory):
        (directory / 'instance.json').unlink(missing_ok=True)
    import uuid
    identity = uuid.uuid4().hex
    command = [sys.executable, '-m', 'workflow_doctor.api.native', '--dist', str(root / 'frontend' / 'dist'),
               '--state-dir', str(directory), '--port', str(port), '--instance', identity]
    child = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(150):
        state = read_state(directory)
        # Windows venv executables may redirect to another Python PID. Use the
        # per-launch identity, never assume Popen.pid is the serving interpreter.
        if state and state['instance'] == identity and health(port):
            print(f'STARTED http://127.0.0.1:{port}\nSwagger http://127.0.0.1:{port}/docs')
            return 0
        if child.poll() is not None:
            break
        time.sleep(.1)
    # Do not terminate a PID on failed startup; request a cooperative shutdown.
    if state and state['instance'] == identity:
        (directory / (state['instance'] + '.stop')).write_bytes(b'stop')
    print('START_FAILED: verify dependencies, build, local permissions and port; no process was killed')
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print('PORT_INVALID: use 1024..65535')
        return 1
    try:
        return control(args.action, args.root, args.port)
    except Exception:
        print('NATIVE_CONTROL_FAILED: check the local runtime, dependencies and frontend build; no process was killed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
