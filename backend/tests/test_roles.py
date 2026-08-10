"""Role API regression tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_list_roles(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
) -> None:
    response = await client.get("/api/v1/roles", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert any(item["id"] == test_role.id for item in response.json()["data"]["items"])


async def test_create_role(client: AsyncClient, auth_headers: Headers) -> None:
    response = await client.post(
        "/api/v1/roles",
        json={"name": "测试角色", "description": "用于测试"},
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["name"] == "测试角色"


async def test_create_duplicate_role_returns_http_409(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
) -> None:
    response = await client.post(
        "/api/v1/roles",
        json={"name": test_role.name, "description": "重复"},
        headers=auth_headers,
    )

    assert_error(response, 409)


async def test_create_role_with_invalid_permission_is_atomic(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    response = await client.post(
        "/api/v1/roles",
        json={
            "name": "invalid_permission_role",
            "description": "must not persist",
            "permission_ids": [999_999],
        },
        headers=auth_headers,
    )

    assert_error(response, 422)
    role = await db_session.scalar(select(Role).where(Role.name == "invalid_permission_role"))
    assert role is None


async def test_update_role(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
) -> None:
    response = await client.put(
        f"/api/v1/roles/{test_role.id}",
        json={"description": "更新后的描述"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["description"] == "更新后的描述"


async def test_toggle_role_is_active(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    role = Role(name="可切换状态角色", description="用于状态开关测试")
    db_session.add(role)
    await db_session.commit()

    response = await client.put(
        f"/api/v1/roles/{role.id}",
        json={"is_active": False},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False

    response = await client.put(
        f"/api/v1/roles/{role.id}",
        json={"is_active": True},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is True


async def test_delete_role_without_users(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    role = Role(name="无关联角色", description="待删除")
    db_session.add(role)
    await db_session.commit()
    role_id = role.id

    response = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    is_deleted = await db_session.scalar(select(Role.is_deleted).where(Role.id == role_id))
    assert is_deleted is True


async def test_delete_role_with_users_returns_http_409(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
    test_user: User,
) -> None:
    response = await client.delete(f"/api/v1/roles/{test_role.id}", headers=auth_headers)

    assert_error(response, 409)


async def test_assign_permissions(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
    test_permissions: list[Permission],
) -> None:
    expected_ids = [permission.id for permission in test_permissions[:3]]
    response = await client.put(
        f"/api/v1/roles/{test_role.id}/permissions",
        json={"permission_ids": expected_ids},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    actual_ids = [permission["id"] for permission in response.json()["data"]["permissions"]]
    assert set(actual_ids) == set(expected_ids)


async def test_assign_invalid_permission_preserves_existing_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    test_role: Role,
    test_permissions: list[Permission],
) -> None:
    expected_ids = {permission.id for permission in test_permissions}
    response = await client.put(
        f"/api/v1/roles/{test_role.id}/permissions",
        json={"permission_ids": [999_999]},
        headers=auth_headers,
    )

    assert_error(response, 422)
    permission_ids = set(
        (
            await db_session.scalars(
                select(role_permissions.c.permission_id).where(
                    role_permissions.c.role_id == test_role.id
                )
            )
        ).all()
    )
    assert permission_ids == expected_ids
