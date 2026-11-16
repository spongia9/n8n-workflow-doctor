"""TEST ONLY: a real loopback FastAPI transport serving a fabricated hostile report.

Not imported by production, absent from image build context, no request flag or
environment setting can enable this in the production application.
"""
import argparse
import re

from starlette.responses import Response, JSONResponse
from starlette.middleware import Middleware
from workflow_doctor.api.models import ApiProblem
from workflow_doctor.api.app import create_app

HOSTILE_HTML = '''<!doctype html><html><head>
<meta http-equiv="refresh" content="0;url=https://untrusted.invalid/refresh">
<style>@import url(https://untrusted.invalid/style);body{background:url(https://untrusted.invalid/image)}</style>
</head><body><h1>真实 API 恶意报告测试</h1>
<script>window.parent.postMessage("SPRINT6_SCRIPT_EXECUTED","*");fetch("https://untrusted.invalid/script")</script>
<img src="https://untrusted.invalid/image" onerror="parent.postMessage('SPRINT6_SCRIPT_EXECUTED','*')">
<iframe src="https://untrusted.invalid/frame"></iframe>
<svg onload="parent.postMessage('SPRINT6_SCRIPT_EXECUTED','*')"></svg>
<form action="https://untrusted.invalid/form"><input name="fabricated"></form>
<a href="javascript:parent.postMessage('SPRINT6_SCRIPT_EXECUTED','*')">静态安全文本</a>
<div onclick="parent.postMessage('SPRINT6_SCRIPT_EXECUTED','*')">中文 &lt;script&gt; 报告内容</div>
</body></html>'''


class HostileFixtureMiddleware:
    def __init__(self, app, store):
        self.app, self.store = app, store

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        match = re.fullmatch(r'/api/v1/scans/([a-f0-9]{32})/report', scope['path'])
        if scope['method'] == 'GET' and match and scope.get('query_string') == b'format=html':
            # Only genuine scans in this real test app can receive the fixture.
            try:
                self.store.get(match[1])
            except ApiProblem as error:
                return await JSONResponse(error.body(), status_code=error.status)(scope, receive, send)
            return await Response(HOSTILE_HTML, media_type='text/html', headers={
                'Content-Disposition': f'attachment; filename="scan-{match[1]}.html"',
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            })(scope, receive, send)
        return await self.app(scope, receive, send)


def create_hostile_app():
    app = create_app()
    # Append inside the existing boundary/CORS so even the test fixture keeps
    # the normal Host, Origin, operation gate and sanitized-failure checks.
    app.user_middleware.append(Middleware(HostileFixtureMiddleware, store=app.state.store))
    return app


def main():
    parser = argparse.ArgumentParser(description='Test-only hostile HTML fixture, fixed loopback port')
    parser.parse_args()
    import uvicorn
    uvicorn.run(create_hostile_app(), host='127.0.0.1', port=8002,
                access_log=False, proxy_headers=False, log_level='warning')


if __name__ == '__main__':
    main()
