"""Loopback production SPA host. No input workflow is used as a filesystem path."""
import argparse
import asyncio
import mimetypes
import re
from pathlib import Path

from starlette.responses import FileResponse

from .app import create_app
from .config import ApiConfig
from .models import ApiProblem

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SPA = re.compile(r"(?:|upload|scans/[a-f0-9]{32}(?:/graph|/reports)?)")


def create_native_app(dist: Path):
    # Enumerate trusted build output once. Request paths never reach resolve/stat:
    # in particular Windows UNC/device/drive paths cannot trigger network I/O.
    dist = Path(dist)
    if str(dist).startswith(('\\\\', '//')):
        raise ValueError('Native build must be on a local disk')
    root = dist.resolve(strict=True)
    if str(root).startswith(('\\\\', '//')):
        raise ValueError('Native build must be on a local disk')
    if (root / 'index.html').is_symlink() or (root / 'index.html').resolve().parent != root:
        raise ValueError('Frontend index must be inside the build directory')
    if not (root / 'index.html').is_file() or (root / 'native-build.txt').read_text() != 'api=same-origin\n':
        raise ValueError('Build the frontend with the same-origin API first')
    manifest = {'': root / 'index.html'}
    allowed = {'.js', '.css', '.woff', '.woff2', '.png', '.svg', '.ico'}
    assets = root / 'assets'
    if not assets.is_dir() or assets.is_symlink() or assets.resolve().parent != root:
        raise ValueError('Frontend assets are missing')
    # Vite emits flat hashed assets. Reject nested/unexpected/reparse outputs.
    for item in assets.iterdir():
        if (item.suffix not in allowed or not re.fullmatch(r'[A-Za-z0-9_.-]+', item.name)
                or not item.is_file() or item.is_symlink() or item.resolve().parent != assets.resolve()):
            raise ValueError('Unexpected frontend build asset; rebuild from reviewed sources')
        manifest['assets/' + item.name] = item
    if not any(path.endswith('.js') for path in manifest):
        raise ValueError('Frontend JavaScript assets are missing')
    app = create_app(ApiConfig(cors_origins=()))

    @app.api_route('/{path:path}', methods=['GET', 'HEAD'], include_in_schema=False)
    async def frontend(path: str):
        if path in manifest:
            target = manifest[path]
        elif SPA.fullmatch(path):
            target = manifest['']
        else:
            raise ApiProblem(404, 'HTTP_NOT_FOUND', 'The local resource was not found')
        # The trusted build directory must not be changed while the server runs.
        media = 'text/html' if target.name == 'index.html' else mimetypes.guess_type(target.name)[0]
        return FileResponse(target, media_type=media, headers={'Content-Security-Policy': CSP})

    return app


def run_server(dist, port, state_dir, instance=None):
    import uvicorn
    from .native_runtime import InstanceLock, write_state
    # Single instance per project; the owning process keeps the lock until exit.
    with InstanceLock(state_dir):
        app = create_native_app(dist)
        server = uvicorn.Server(uvicorn.Config(
            app, host='127.0.0.1', port=port, workers=1, access_log=False,
            log_config=None, log_level='critical', proxy_headers=False,
            limit_concurrency=16, backlog=8, timeout_keep_alive=5,
            timeout_graceful_shutdown=20))

        async def serve():
            import uuid
            identity = instance or uuid.uuid4().hex
            stop = state_dir / (identity + '.stop')
            task = asyncio.create_task(server.serve())
            try:
                for _ in range(200):
                    if task.done():
                        await task
                        return
                    if server.started:
                        break
                    await asyncio.sleep(.05)
                if not server.started:
                    server.should_exit = True
                    return
                write_state(state_dir, port, identity)
                while not task.done():
                    if stop.is_file():
                        server.should_exit = True
                    await asyncio.sleep(.2)
                await task
            finally:
                server.should_exit = True
                await task
                (state_dir / 'instance.json').unlink(missing_ok=True)
                stop.unlink(missing_ok=True)
        asyncio.run(serve())


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local production frontend and API')
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--instance')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if args.instance is not None and not re.fullmatch('[a-f0-9]{32}', args.instance):
        parser.error('invalid instance identifier')
    try:
        run_server(args.dist, args.port, args.state_dir, args.instance)
    except (Exception, SystemExit):
        # Never print dependency tracebacks, request contents or private paths.
        print('NATIVE_START_FAILED: check build, dependencies, port and local runtime directory')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
