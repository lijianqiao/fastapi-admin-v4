"""Domain error rendering regression tests."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import PasswordHashOverloadedError
from app.crud.base import RelatedObjectsNotFoundError
from app.crud.role import RoleInUseError
from app.main import register_exception_handlers

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
