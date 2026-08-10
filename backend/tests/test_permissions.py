"""Permission API and RBAC regression tests."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]


async def test_list_permissions(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    response = await client.get("/api/v1/permissions", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == len(test_permissions)


async def test_list_permissions_grouped(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    response = await client.get(
        "/api/v1/permissions",
        params={"grouped": "true", "search": "user:read"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert "用户管理" in response.json()["data"]
    assert sum(len(items) for items in response.json()["data"].values()) == 1


async def test_create_permission(client: AsyncClient, auth_headers: Headers) -> None:
    response = await client.post(
        "/api/v1/permissions",
        json={
            "name": "导出用户",
            "code": "USER:EXPORT",
            "module": "用户管理",
            "description": "导出用户数据",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["code"] == "user:export"


async def test_create_duplicate_permission_returns_http_409(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    permission = test_permissions[0]
    response = await client.post(
        "/api/v1/permissions",
        json={
            "name": "重复权限",
            "code": permission.code,
            "module": permission.module,
        },
        headers=auth_headers,
    )

    assert_error(response, 409)


async def test_user_without_create_permission_cannot_bypass_rbac(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
) -> None:
    read_permission = Permission(
        name="查看权限",
        code="permission:read",
        module="权限管理",
    )
    read_only_role = Role(name="只读权限角色", permissions=[read_permission])
    read_only_user = User(
        username="permission_reader",
        email="permission-reader@example.com",
        hashed_password=hash_password("readerpassword123"),
        roles=[read_only_role],
    )
    db_session.add(read_only_user)
    await db_session.commit()
    headers = await login_user(read_only_user.username, "readerpassword123")

    response = await client.post(
        "/api/v1/permissions",
        json={"name": "越权权限", "code": "rbac:bypass", "module": "安全"},
        headers=headers,
    )

    assert_error(response, 403)
    created = await db_session.scalar(select(Permission).where(Permission.code == "rbac:bypass"))
    assert created is None


async def test_soft_deleted_role_no_longer_grants_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
) -> None:
    create_permission = Permission(
        name="创建权限",
        code="permission:create",
        module="权限管理",
    )
    role = Role(name="即将删除的角色", permissions=[create_permission])
    user = User(
        username="deleted_role_user",
        email="deleted-role@example.com",
        hashed_password=hash_password("deletedrolepassword"),
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    headers = await login_user(user.username, "deletedrolepassword")

    role.is_deleted = True
    await db_session.commit()

    response = await client.post(
        "/api/v1/permissions",
        json={"name": "不应创建", "code": "deleted-role:bypass", "module": "安全"},
        headers=headers,
    )

    assert_error(response, 403)
    created = await db_session.scalar(
        select(Permission).where(Permission.code == "deleted-role:bypass")
    )
    assert created is None


async def test_inactive_role_no_longer_grants_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
) -> None:
    create_permission = Permission(
        name="创建权限",
        code="permission:create",
        module="权限管理",
    )
    role = Role(name="即将禁用的角色", permissions=[create_permission])
    user = User(
        username="inactive_role_user",
        email="inactive-role@example.com",
        hashed_password=hash_password("inactiverolepassword"),
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    headers = await login_user(user.username, "inactiverolepassword")

    role.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/permissions",
        json={"name": "不应创建", "code": "inactive-role:bypass", "module": "安全"},
        headers=headers,
    )

    assert_error(response, 403)
    created = await db_session.scalar(
        select(Permission).where(Permission.code == "inactive-role:bypass")
    )
    assert created is None


async def test_inactive_permission_no_longer_grants_access(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
) -> None:
    create_permission = Permission(
        name="创建权限",
        code="permission:create",
        module="权限管理",
    )
    role = Role(name="权限将被禁用的角色", permissions=[create_permission])
    user = User(
        username="inactive_perm_user",
        email="inactive-perm@example.com",
        hashed_password=hash_password("inactivepermpassword"),
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    headers = await login_user(user.username, "inactivepermpassword")

    create_permission.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/permissions",
        json={"name": "不应创建", "code": "inactive-perm:bypass", "module": "安全"},
        headers=headers,
    )

    assert_error(response, 403)
    created = await db_session.scalar(
        select(Permission).where(Permission.code == "inactive-perm:bypass")
    )
    assert created is None


async def test_update_permission(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    permission = test_permissions[0]
    response = await client.put(
        f"/api/v1/permissions/{permission.id}",
        json={"description": "更新后的描述"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["description"] == "更新后的描述"


async def test_toggle_permission_is_active(
    client: AsyncClient,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    permission = test_permissions[0]
    response = await client.put(
        f"/api/v1/permissions/{permission.id}",
        json={"is_active": False},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False

    response = await client.put(
        f"/api/v1/permissions/{permission.id}",
        json={"is_active": True},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is True


async def test_delete_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    test_permissions: list[Permission],
) -> None:
    permission_id = test_permissions[-1].id
    response = await client.delete(
        f"/api/v1/permissions/{permission_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    is_deleted = await db_session.scalar(
        select(Permission.is_deleted).where(Permission.id == permission_id)
    )
    assert is_deleted is True
