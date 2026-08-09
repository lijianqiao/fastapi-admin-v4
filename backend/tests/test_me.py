"""个人中心接口回归测试。"""

import pytest
from httpx import AsyncClient

from app.models.permission import Permission
from app.models.user import User

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_profile_exposes_effective_permission_codes(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    """前端只能从这里拿到权限码，roles 里不含 permissions。"""
    response = await client.get("/api/v1/me", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert set(payload["permissions"]) == {permission.code for permission in test_permissions}


async def test_profile_permissions_empty_for_roleless_superuser(
    client: AsyncClient,
    superuser_headers: Headers,
    superuser: User,
) -> None:
    """超级管理员靠 is_superuser 通过校验，不需要显式授权。"""
    response = await client.get("/api/v1/me", headers=superuser_headers)

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["is_superuser"] is True
    assert payload["permissions"] == []


async def test_update_profile_returns_permission_codes(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    """更新个人信息后返回体形状必须与 GET /me 一致。"""
    response = await client.patch(
        "/api/v1/me",
        json={"nickname": "新昵称"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["nickname"] == "新昵称"
    assert set(payload["permissions"]) == {permission.code for permission in test_permissions}
