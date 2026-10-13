"""Per-request context: a request id bound to every log line, and one `http.request` event."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

from app.core.logging import get_logger

log = get_logger("http")

# Keep-alive pings arrive every few minutes; logging them adds noise, not signal.
_QUIET_PATHS = frozenset({"/healthz"})


async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        if request.url.path not in _QUIET_PATHS:
            log.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status=status,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
            )
