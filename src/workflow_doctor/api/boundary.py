"""ASGI bounds apply before multipart parsing, including chunked bodies."""
import asyncio
import re
import threading

from starlette.responses import JSONResponse

from .models import ApiProblem

HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
           "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}


class RequestBoundary:
    def __init__(self, app, config):
        self.app, self.config = app, config
        self._gate = threading.BoundedSemaphore(1)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, acquired = False, False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = [(k, v) for k, v in message.get("headers", []) if k.decode("latin-1").lower() not in {h.lower() for h in HEADERS}]
                if not any(k.lower() == b"content-security-policy" for k, _ in headers):
                    headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"))
                message = {**message, "headers": headers + [(k.lower().encode(), v.encode()) for k, v in HEADERS.items()]}
            await send(message)

        async def reject(problem):
            request_headers = dict(scope.get("headers", []))
            origin = request_headers.get(b"origin", b"").decode("latin-1")
            cors = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"} if origin in self.config.cors_origins else {}
            await JSONResponse(problem.body(), status_code=problem.status, headers=cors)(scope, receive, safe_send)

        try:
            pairs = scope.get("headers", [])
            headers = {k.lower(): v.decode("latin-1") for k, v in pairs}
            host = headers.get(b"host", "").lower()
            if not re.fullmatch(r"(localhost|127\.0\.0\.1)(:[0-9]{1,5})?", host):
                raise ApiProblem(400, "HOST_NOT_ALLOWED", "Use the local loopback service address")
            if len([k for k, _ in pairs if k.lower() in (b"host", b"origin", b"content-length")]) != len({k.lower() for k, _ in pairs if k.lower() in (b"host", b"origin", b"content-length")}):
                raise ApiProblem(400, "REQUEST_HEADERS_INVALID", "Duplicate routing or length headers are not supported")
            origin = headers.get(b"origin")
            if origin and origin not in self.config.cors_origins and origin != scope.get("scheme", "http") + "://" + host:
                raise ApiProblem(403, "ORIGIN_NOT_ALLOWED", "Origin is not an approved local development origin")
            if scope.get("path", "").startswith("/api/v1/") and scope["method"] != "OPTIONS":
                acquired = self._gate.acquire(blocking=False)
                if not acquired:
                    raise ApiProblem(503, "SCAN_BUSY", "Another scan or report operation is active; retry later")
            if scope["method"] == "POST" and scope["path"] == "/api/v1/scans":
                if headers.get(b"content-encoding", "identity").lower() != "identity":
                    raise ApiProblem(415, "CONTENT_ENCODING_UNSUPPORTED", "Compressed HTTP request bodies are not supported")
                length = headers.get(b"content-length")
                if length is not None:
                    if not re.fullmatch(r"[0-9]{1,20}", length):
                        raise ApiProblem(400, "REQUEST_LENGTH_INVALID", "Content-Length must be a bounded nonnegative integer")
                    if int(length) > self.config.max_request_bytes:
                        raise ApiProblem(413, "UPLOAD_REQUEST_TOO_LARGE", "Upload request exceeds the server byte limit")

                async def read_body():
                    parts, size = [], 0
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            raise ApiProblem(400, "UPLOAD_DISCONNECTED", "Upload did not complete")
                        chunk = message.get("body", b"")
                        size += len(chunk)
                        if size > self.config.max_request_bytes:
                            raise ApiProblem(413, "UPLOAD_REQUEST_TOO_LARGE", "Upload request exceeds the server byte limit")
                        parts.append(chunk)
                        if not message.get("more_body"):
                            return b"".join(parts)

                try:
                    body = await asyncio.wait_for(read_body(), timeout=self.config.upload_timeout_seconds)
                except TimeoutError:
                    raise ApiProblem(408, "UPLOAD_TIMEOUT", "Upload did not complete within the server deadline") from None
                consumed = False

                async def replay():
                    nonlocal consumed
                    if consumed:
                        return await receive()
                    consumed = True
                    return {"type": "http.request", "body": body, "more_body": False}

                await self.app(scope, replay, safe_send)
            else:
                await self.app(scope, receive, safe_send)
        except ApiProblem as problem:
            if not started:
                await reject(problem)
        except Exception:
            if not started:
                await reject(ApiProblem(500, "INTERNAL_ERROR", "The request could not be completed"))
        finally:
            if acquired:
                self._gate.release()
