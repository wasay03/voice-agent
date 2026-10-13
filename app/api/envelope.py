"""The `{ "data": ..., "error": ... }` envelope every REST response uses."""

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    code: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class Envelope[T](BaseModel):
    """Response schema for OpenAPI docs; handlers build responses with `ok()` / `fail()`."""

    data: T | None = None
    error: ErrorBody | None = None


def ok(data: Any, *, status_code: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "error": None},
        headers=headers,
    )


def fail(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
    data: Any = None,
) -> JSONResponse:
    error = ErrorBody(
        code=code,
        message=message,
        details=[ErrorDetail(**d) for d in details or []],
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "error": error.model_dump()},
    )
