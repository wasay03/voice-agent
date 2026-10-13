"""Application error hierarchy.

Every layer raises these; only `app/api/exception_handlers.py` (REST) and the voice adapter
turn them into responses. Each class carries its HTTP status and a stable machine code.
"""

from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: list[dict[str, Any]] | None = None) -> None:
        self.message = message or self.default_message
        self.details = details or []
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    default_message = "The request could not be read."


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"
    default_message = "Missing or invalid credentials."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    default_message = "The request conflicts with existing data."


class FieldValidationError(AppError):
    """One or more fields broke a rule. `details` holds one entry per field."""

    status_code = 422
    code = "validation_error"
    default_message = "One or more fields are invalid."


class DataIntegrityError(AppError):
    """A database constraint rejected the data (a rule the app layer should have caught)."""

    status_code = 422
    code = "constraint_violation"
    default_message = "The data breaks a database rule."

    def __init__(
        self,
        message: str | None = None,
        *,
        constraint: str | None = None,
        column: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.constraint = constraint
        self.column = column
        if details is None and (constraint or column):
            details = [{"field": column, "code": constraint or "constraint", "message": message or ""}]
        super().__init__(message, details=details)


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"
    default_message = "The database is temporarily unavailable."


class DatabaseTimeoutError(AppError):
    status_code = 503
    code = "database_timeout"
    default_message = "The database took too long to respond."
