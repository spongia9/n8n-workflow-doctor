"""Local synchronous FastAPI adapter; no scan logic is implemented here."""
import asyncio
import base64
import hashlib
import logging
import re
from contextlib import asynccontextmanager, suppress
from importlib.resources import files as package_files

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from ..reporting import render_report
from .boundary import RequestBoundary
from .config import ApiConfig
from .models import ApiProblem, ErrorResponse, ScanResponse
from .service import scan_and_store, upload_label
from .store import FORMATS, ResultStore


class _NoMultipartPayloadLogs(logging.Filter):
    def filter(self, record):
        return False


class _CompleteMultipartParser(MultiPartParser):
    """Reject truncated batches: upstream finalize does not verify END state."""
    def on_end(self):
        self._ended = True
        super().on_end()

    async def parse(self):
        self._ended = False
        form = await super().parse()
        if not self._ended:
            await form.close()
            raise MultiPartException("Multipart upload did not terminate")
        return form


@asynccontextmanager
async def _upload_form(request, config):
    try:
        form = await _CompleteMultipartParser(
            request.headers, request.stream(), max_files=config.scan_limits.max_files,
            max_fields=0, max_part_size=1024).parse()
    except MultiPartException as exc:
        if exc.message.startswith("Too many files"):
            raise ApiProblem(413, "UPLOAD_FILE_COUNT", "Upload file count exceeds the server limit") from None
        raise ApiProblem(400, "MULTIPART_INVALID", "Multipart upload could not be read completely") from None
    try:
        yield form
    finally:
        await form.close()


def create_app(config: ApiConfig | None = None) -> FastAPI:
    config = config or ApiConfig()
    store = ResultStore(config)
    # Multipart errors may include boundary/header fragments in dependency logs.
    parser_logger = logging.getLogger("python_multipart.multipart")
    if not any(isinstance(item, _NoMultipartPayloadLogs) for item in parser_logger.filters):
        parser_logger.addFilter(_NoMultipartPayloadLogs())

    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:
                await asyncio.sleep(config.cleanup_interval_seconds)
                store.purge()
        task = asyncio.create_task(cleanup())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            store.clear()

    app = FastAPI(title="n8n Workflow Doctor", version="0.1.0", docs_url=None, redoc_url=None,
                  lifespan=lifespan, debug=False, responses={422: {"model": ErrorResponse}})
    app.state.store, app.state.config = store, config
    app.add_middleware(CORSMiddleware, allow_origins=list(config.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
                       expose_headers=["Content-Disposition"])
    app.add_middleware(RequestBoundary, config=config)

    @app.exception_handler(ApiProblem)
    async def api_error(request, exc):
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(ApiProblem(422, "REQUEST_INVALID", "Request parameters do not match the API contract").body(), status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = "HTTP_NOT_FOUND" if exc.status_code == 404 else "HTTP_REQUEST_ERROR"
        return JSONResponse(ApiProblem(exc.status_code, code, "The HTTP request could not be processed").body(), status_code=exc.status_code)

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": "synchronous"}

    errors = {code: {"model": ErrorResponse} for code in (400, 413, 415, 422, 500, 503)}
    upload_schema = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["files"], "properties": {"files": {"type": "array", "minItems": 1,
        "maxItems": config.scan_limits.max_files, "items": {"type": "string", "format": "binary"}}}}}}}}

    @app.post("/api/v1/scans", response_model=ScanResponse, responses=errors, openapi_extra=upload_schema)
    async def create_scan(request: Request):
        if request.query_params:
            raise ApiProblem(422, "REQUEST_INVALID", "Upload parameters are server-owned")
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
            raise ApiProblem(415, "CONTENT_TYPE_UNSUPPORTED", "Use multipart/form-data with the files field")
        async with _upload_form(request, config) as form:
            uploads = list(form.multi_items())
            if not uploads or any(key != "files" or not isinstance(value, UploadFile) for key, value in uploads):
                raise ApiProblem(422, "UPLOAD_FIELDS_INVALID", "Provide one or more file parts named files")
            payloads = []
            for index, (_, upload) in enumerate(uploads):
                # Multipart libraries can strip an old Windows full-path prefix.
                # Reject path syntax in the original header as well as parsed names.
                disposition = upload.headers.get("content-disposition", "")
                if "/" in disposition or "\\" in disposition:
                    raise ApiProblem(400, "UPLOAD_NAME_INVALID", "Upload name must be a plain filename without path or control characters")
                label = upload_label(upload.filename, index)
                limit = config.scan_limits.max_archive_bytes if label.endswith(".zip") else config.scan_limits.max_file_bytes
                raw = await upload.read(limit + 1)
                if len(raw) > limit:
                    raise ApiProblem(413, "UPLOAD_FILE_TOO_LARGE", "An upload exceeds the server single-file limit")
                payloads.append((label, raw))
            item = await run_in_threadpool(scan_and_store, payloads, config, store)
        return item.summary()

    @app.get("/api/v1/scans/{scan_id}", response_model=ScanResponse, responses={404: {"model": ErrorResponse}})
    async def get_scan(scan_id: str):
        return store.get(scan_id).summary()

    @app.get("/api/v1/scans/{scan_id}/report", responses={
        200: {"content": {media: {"schema": {"type": "string"}} for media in
                         ("application/json", "text/plain", "text/markdown", "text/html")}},
        400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}})
    async def report(scan_id: str, format: str = Query("json", json_schema_extra={"enum": list(FORMATS)})):
        if format not in FORMATS:
            raise ApiProblem(400, "REPORT_FORMAT_UNSUPPORTED", "Supported report formats are text, json, markdown and html")
        item = store.get(scan_id)
        content = render_report(item.report(), format, generated_at=item.created_at).encode("utf-8")
        if len(content) > config.max_response_bytes:
            raise ApiProblem(413, "REPORT_TOO_LARGE", "Rendered report exceeds the server response limit")
        extension = {"text": "txt", "json": "json", "markdown": "md", "html": "html"}[format]
        media = {"text": "text/plain; charset=utf-8", "json": "application/json; charset=utf-8",
                 "markdown": "text/markdown; charset=utf-8", "html": "text/html; charset=utf-8"}[format]
        headers = {"Content-Disposition": f'attachment; filename="scan-{item.scan_id}.{extension}"',
                   "Content-Security-Policy": "sandbox; default-src 'none'"}
        return Response(content, media_type=media, headers=headers)

    @app.get("/docs", include_in_schema=False)
    async def docs():
        response = get_swagger_ui_html(openapi_url="/openapi.json", title="Workflow Doctor API",
                                       swagger_js_url="/docs-assets/swagger-ui-bundle.js",
                                       swagger_css_url="/docs-assets/swagger-ui.css",
                                       swagger_favicon_url="data:,",
                                       swagger_ui_parameters={"validatorUrl": None, "supportedSubmitMethods": ["get", "post"]})
        # Permit only our self-hosted bundle and the exact fixed bootstrap.
        body = response.body.decode()
        inline = re.search(r"<script>(.*?)</script>", body, re.S)[1]
        digest = base64.b64encode(hashlib.sha256(inline.encode()).digest()).decode()
        response.headers["Content-Security-Policy"] = f"default-src 'none'; script-src 'self' 'sha256-{digest}'; style-src 'self' 'unsafe-inline'; img-src data:; connect-src 'self'; base-uri 'none'; form-action 'none'"
        return response

    @app.get("/docs-assets/{name}", include_in_schema=False)
    async def assets(name: str):
        media = {"swagger-ui-bundle.js": "application/javascript", "swagger-ui.css": "text/css"}
        if name not in media:
            raise ApiProblem(404, "HTTP_NOT_FOUND", "Documentation asset was not found")
        return Response(package_files(__package__).joinpath("assets", name).read_bytes(), media_type=media[name])

    return app


app = create_app()
