"""Domain error rendering regression tests."""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    is_conflict_violation,
)
from app.core.middleware import UnhandledErrorMiddleware
from app.core.security import PasswordHashOverloadedError
from app.crud.base import RelatedObjectsNotFoundError
from app.crud.role import RoleInUseError
from app.main import app as application
from app.main import register_exception_handlers
from app.models.permission import Permission
from app.models.user import User

# 不设模块级 pytestmark：asyncio_mode=auto 已覆盖异步用例，且任务 7 会向本文件追加同步用例。


async def _render(exc: Exception) -> tuple[int, dict[str, object], dict[str, str]]:
    """Raise ``exc`` from a throwaway route and return status, body and headers."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")
    return response.status_code, response.json(), dict(response.headers)


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (ForbiddenError("禁止"), 403),
        (NotFoundError("不存在"), 404),
        (ConflictError("冲突"), 409),
    ],
)
async def test_app_error_subclasses_render_envelope(exc: AppError, status_code: int) -> None:
    code, body, _ = await _render(exc)

    assert code == status_code
    assert body == {"code": status_code, "data": None, "message": exc.message}


async def test_existing_domain_errors_keep_their_contract() -> None:
    code, body, _ = await _render(RoleInUseError(3))
    assert code == 409
    assert body["message"] == "角色仍关联 3 个用户"
    assert body["data"] == {"user_count": 3}

    code, body, _ = await _render(RelatedObjectsNotFoundError("role", [5, 2, 5]))
    assert code == 422
    assert body["message"] == "以下角色不存在或已删除"
    assert body["data"] == {"relation": "role", "missing_ids": [2, 5]}

    code, body, headers = await _render(PasswordHashOverloadedError())
    assert code == 503
    assert headers["retry-after"] == "1"
    assert body["message"] == "认证服务繁忙，请稍后重试"


class _FakeDriverError(Exception):
    def __init__(self, **attributes: str) -> None:
        super().__init__("driver error")
        for name, value in attributes.items():
            setattr(self, name, value)


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({"sqlstate": "23505"}, True),
        ({"sqlstate": "23503"}, True),
        ({"sqlstate": "23502"}, False),
        ({"sqlite_errorname": "SQLITE_CONSTRAINT_UNIQUE"}, True),
        ({"sqlite_errorname": "SQLITE_CONSTRAINT_NOTNULL"}, False),
        ({}, False),
    ],
)
def test_is_conflict_violation(attributes: dict[str, str], expected: bool) -> None:
    exc = IntegrityError("INSERT ...", {}, _FakeDriverError(**attributes))

    assert is_conflict_violation(exc) is expected


async def test_sqlite_unique_violation_is_a_conflict(db_session: AsyncSession) -> None:
    db_session.add_all(
        [Permission(name="a", code="dup:code"), Permission(name="b", code="dup:code")]
    )
    with pytest.raises(IntegrityError) as caught:
        await db_session.flush()
    await db_session.rollback()

    assert is_conflict_violation(caught.value)


async def test_unhandled_error_middleware_keeps_cors_headers() -> None:
    app = FastAPI()
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
    )

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crash", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 500
    assert response.json() == {"code": 500, "data": None, "message": "服务器内部错误"}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_application_500_carries_cors_headers(client: AsyncClient) -> None:
    async def explode() -> User:
        raise RuntimeError("boom")

    application.dependency_overrides[get_current_user] = explode
    origin = settings.cors_origins_list[0]

    response = await client.get("/api/v1/dashboard", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == origin
