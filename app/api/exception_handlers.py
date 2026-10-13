"""Turn every failure into the envelope with the right status code.

400: the request cannot be read (bad JSON, bad path/query parameter types).
422: the request is readable but a field breaks a rule (including DB constraint violations).
404 / 401 / 503 from AppError subclasses. Anything unexpected: 500 with the request id only.
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.envelope import fail
from app.core.errors import AppError
from app.core.logging import get_logger

log = get_logger(__name__)

_HTTP_CODES = {400: "bad_request", 401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}
_UNREADABLE_TYPES = {"json_invalid", "model_attributes_type", "dict_type"}


def _request_id() -> str | None:
    return structlog.contextvars.get_contextvars().get("request_id")


def _validation_details(errors: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Classify FastAPI validation errors into 400 (unreadable) or 422 (field rules)."""
    status = 422
    details = []
    for err in errors:
        loc = list(err.get("loc", ()))
        source = loc[0] if loc else "body"
        if (
            source in ("path", "query", "header")
            or err.get("type") in _UNREADABLE_TYPES
            or (loc == ["body"] and err.get("type") == "missing")
        ):
            status = 400
        field = ".".join(str(p) for p in loc[1:]) or None
        message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        details.append({"field": field, "code": err.get("type", "invalid"), "message": message})
    return status, details


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        log.error("app.error", code=exc.code, message=exc.message)
    return fail(exc.status_code, exc.code, exc.message, details=exc.details, request_id=_request_id())


async def _request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    status, details = _validation_details(list(exc.errors()))
    code = "bad_request" if status == 400 else "validation_error"
    message = "The request could not be read." if status == 400 else f"{len(details)} field(s) are invalid."
    return fail(status, code, message, details=details, request_id=_request_id())


async def _http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    return fail(exc.status_code, code, str(exc.detail), request_id=_request_id())


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", error=type(exc).__name__)
    return fail(500, "internal_error", "An unexpected error occurred.", request_id=_request_id())


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _request_validation)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled)
