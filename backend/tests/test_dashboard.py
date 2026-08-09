"""Dashboard authorization regression tests."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]


async def test_dashboard_with_audit_permission(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get("/api/v1/dashboard", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert "stats" in payload
    assert "recent_logs" in payload


async def test_dashboard_without_audit_permission_hides_recent_logs(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
) -> None:
    user_read = Permission(name="查看用户", code="user:read", module="用户管理")
    role = Role(name="无审计权限角色", permissions=[user_read])
    user = User(
        username="no_audit_user",
        email="no-audit@example.com",
        hashed_password=hash_password("noauditpassword123"),
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    headers = await login_user(user.username, "noauditpassword123")

    response = await client.get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert "stats" in payload
    assert payload["recent_logs"] == []
