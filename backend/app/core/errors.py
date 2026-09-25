"""Expected, user-facing failures and the shared error envelope."""

from typing import Any, ClassVar

from sqlalchemy.exc import IntegrityError


def error_content(status_code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Build the public error envelope used by every error response."""
    return {"code": status_code, "data": data, "message": message}


class AppError(Exception):
    """Base class for domain errors rendered by one exception handler."""

    status_code: ClassVar[int] = 400
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, message: str, *, data: object = None) -> None:
        super().__init__(message)
        self.message = message
        self.data = data


class BadRequestError(AppError):
    status_code = 400


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class UnprocessableError(AppError):
    status_code = 422


class ServiceUnavailableError(AppError):
    status_code = 503


# unique_violation / foreign_key_violation（PostgreSQL SQLSTATE）
_CONFLICT_SQLSTATES = frozenset({"23505", "23503"})
# SQLite 扩展错误名（测试库）
_CONFLICT_SQLITE_ERRORS = frozenset(
    {"SQLITE_CONSTRAINT_UNIQUE", "SQLITE_CONSTRAINT_PRIMARYKEY", "SQLITE_CONSTRAINT_FOREIGNKEY"}
)


def is_conflict_violation(exc: IntegrityError) -> bool:
    """Tell uniqueness/reference conflicts apart from other constraint failures."""
    original = exc.orig
    if getattr(original, "sqlstate", None) in _CONFLICT_SQLSTATES:
        return True
    return getattr(original, "sqlite_errorname", None) in _CONFLICT_SQLITE_ERRORS
