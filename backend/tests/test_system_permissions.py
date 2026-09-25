"""System permissions are owned by the code registry."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Perm
from app.models.permission import Permission
from app.services.permission_sync import SyncResult, sync_system_permissions
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_permission_response_exposes_is_system(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    response = await client.get("/api/v1/permissions", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert all(item["is_system"] is True for item in response.json()["data"]["items"])


async def test_permission_code_is_immutable(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    response = await client.patch(
        f"/api/v1/permissions/{test_permissions[0].id}",
        json={"code": "user:renamed"},
        headers=auth_headers,
    )

    assert_error(response, 422)


async def test_system_permission_cannot_be_deleted(
    client: AsyncClient,
    superuser_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    response = await client.delete(
        f"/api/v1/permissions/{test_permissions[0].id}",
        headers=superuser_headers,
    )

    assert_error(response, 403)


async def test_system_permission_cannot_be_purged(
    client: AsyncClient,
    db_session: AsyncSession,
    superuser_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    permission = test_permissions[0]
    permission.is_deleted = True
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/permissions/{permission.id}/purge",
        headers=superuser_headers,
    )

    assert_error(response, 403)


async def test_registry_code_cannot_be_created_by_hand(
    client: AsyncClient,
    superuser_headers: Headers,
) -> None:
    response = await client.post(
        "/api/v1/permissions",
        json={"name": "伪造", "code": "audit:read", "module": "安全"},
        headers=superuser_headers,
    )

    assert_error(response, 403)


async def test_custom_permission_can_still_be_deleted(
    client: AsyncClient,
    db_session: AsyncSession,
    superuser_headers: Headers,
) -> None:
    custom = Permission(name="导出报表", code="report:export", module="报表")
    db_session.add(custom)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/permissions/{custom.id}",
        headers=superuser_headers,
    )

    assert response.status_code == 200, response.text


async def test_sync_creates_missing_and_repairs_existing(db_session: AsyncSession) -> None:
    stale = Permission(
        name="旧名称",
        code="user:read",
        module="用户管理",
        is_system=False,
        is_deleted=True,
    )
    db_session.add(stale)
    await db_session.commit()

    result = await sync_system_permissions(db_session)
    await db_session.commit()

    assert result == SyncResult(created=len(Perm) - 1, updated=1)
    rows = (await db_session.scalars(select(Permission))).all()
    assert {row.code for row in rows} == {perm.value for perm in Perm}
    assert all(row.is_system and not row.is_deleted for row in rows)
    assert next(row for row in rows if row.code == "user:read").name == "旧名称"
