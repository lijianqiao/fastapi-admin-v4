"""Delegation rules: a non-superuser may only grant permissions they hold."""

from collections.abc import Awaitable, Callable

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, user_roles
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]

LIMITED_CODES = (
    "user:read",
    "user:assign",
    "role:read",
    "role:update",
    "role:assign",
    "role:delete",
    "permission:read",
    "permission:update",
    "permission:delete",
)


@pytest_asyncio.fixture
async def perms(test_permissions: list[Permission]) -> dict[str, Permission]:
    return {permission.code: permission for permission in test_permissions}


@pytest_asyncio.fixture
async def limited_admin(db_session: AsyncSession, perms: dict[str, Permission]) -> User:
    role = Role(name="受限管理员", permissions=[perms[code] for code in LIMITED_CODES])
    user = User(
        username="limited_admin",
        email="limited-admin@example.com",
        hashed_password=hash_password("limitedpassword123"),
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def limited_headers(limited_admin: User, login_user: LoginUser) -> Headers:
    return await login_user(limited_admin.username, "limitedpassword123")


@pytest_asyncio.fixture
async def auditor_role(db_session: AsyncSession, perms: dict[str, Permission]) -> Role:
    role = Role(name="审计员", permissions=[perms["audit:read"]])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest_asyncio.fixture
async def reader_role(db_session: AsyncSession, perms: dict[str, Permission]) -> Role:
    role = Role(name="只读用户", permissions=[perms["user:read"]])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest_asyncio.fixture
async def auditor_member(db_session: AsyncSession, auditor_role: Role) -> User:
    user = User(
        username="auditor_member",
        email="auditor-member@example.com",
        hashed_password=hash_password("auditorpassword123"),
        roles=[auditor_role],
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _new_plain_user(db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("plainpassword123"),
    )
    db.add(user)
    await db.commit()
    return user


async def _role_ids(db: AsyncSession, user_id: int) -> set[int]:
    result = await db.execute(select(user_roles.c.role_id).where(user_roles.c.user_id == user_id))
    return set(result.scalars().all())


async def test_non_superuser_cannot_change_own_roles(
    client: AsyncClient,
    limited_admin: User,
    limited_headers: Headers,
) -> None:
    response = await client.put(
        f"/api/v1/users/{limited_admin.id}/roles",
        json={"role_ids": []},
        headers=limited_headers,
    )

    assert_error(response, 403)


async def test_cannot_assign_role_carrying_permissions_actor_lacks(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
    auditor_role: Role,
) -> None:
    target = await _new_plain_user(db_session, "plain_one")

    response = await client.put(
        f"/api/v1/users/{target.id}/roles",
        json={"role_ids": [auditor_role.id]},
        headers=limited_headers,
    )

    payload = assert_error(response, 403)
    assert payload["data"] == {"missing_codes": ["audit:read"]}
    assert await _role_ids(db_session, target.id) == set()


async def test_can_assign_role_within_own_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
    reader_role: Role,
) -> None:
    target = await _new_plain_user(db_session, "plain_two")

    response = await client.put(
        f"/api/v1/users/{target.id}/roles",
        json={"role_ids": [reader_role.id]},
        headers=limited_headers,
    )

    assert response.status_code == 200, response.text
    assert await _role_ids(db_session, target.id) == {reader_role.id}


async def test_only_newly_added_roles_are_checked(
    client: AsyncClient,
    limited_headers: Headers,
    auditor_member: User,
    auditor_role: Role,
    reader_role: Role,
) -> None:
    response = await client.put(
        f"/api/v1/users/{auditor_member.id}/roles",
        json={"role_ids": [auditor_role.id, reader_role.id]},
        headers=limited_headers,
    )

    assert response.status_code == 200, response.text


async def test_cannot_add_permission_actor_lacks_to_role(
    client: AsyncClient,
    limited_headers: Headers,
    reader_role: Role,
    perms: dict[str, Permission],
) -> None:
    response = await client.put(
        f"/api/v1/roles/{reader_role.id}/permissions",
        json={"permission_ids": [perms["user:read"].id, perms["audit:read"].id]},
        headers=limited_headers,
    )

    payload = assert_error(response, 403)
    assert payload["data"] == {"missing_codes": ["audit:read"]}


async def test_can_add_permission_actor_holds(
    client: AsyncClient,
    limited_headers: Headers,
    reader_role: Role,
    perms: dict[str, Permission],
) -> None:
    response = await client.put(
        f"/api/v1/roles/{reader_role.id}/permissions",
        json={"permission_ids": [perms["user:read"].id, perms["user:assign"].id]},
        headers=limited_headers,
    )

    assert response.status_code == 200, response.text


async def test_reenabling_role_in_use_requires_its_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
    superuser_headers: Headers,
    auditor_member: User,
    auditor_role: Role,
) -> None:
    auditor_role.is_active = False
    await db_session.commit()

    denied = await client.patch(
        f"/api/v1/roles/{auditor_role.id}",
        json={"is_active": True},
        headers=limited_headers,
    )
    assert_error(denied, 403)

    allowed = await client.patch(
        f"/api/v1/roles/{auditor_role.id}",
        json={"is_active": True},
        headers=superuser_headers,
    )
    assert allowed.status_code == 200, allowed.text


async def test_restoring_role_in_use_requires_its_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
    auditor_member: User,
    auditor_role: Role,
) -> None:
    auditor_role.is_deleted = True
    await db_session.commit()

    response = await client.post(
        f"/api/v1/roles/{auditor_role.id}/restore",
        headers=limited_headers,
    )

    assert_error(response, 403)


async def test_reenabling_permission_in_use_is_superuser_only(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
    superuser_headers: Headers,
    auditor_role: Role,
    perms: dict[str, Permission],
) -> None:
    audit_read = perms["audit:read"]
    audit_read.is_active = False
    await db_session.commit()

    denied = await client.patch(
        f"/api/v1/permissions/{audit_read.id}",
        json={"is_active": True},
        headers=limited_headers,
    )
    assert_error(denied, 403)

    allowed = await client.patch(
        f"/api/v1/permissions/{audit_read.id}",
        json={"is_active": True},
        headers=superuser_headers,
    )
    assert allowed.status_code == 200, allowed.text


async def test_restoring_permission_in_use_is_superuser_only(
    client: AsyncClient,
    db_session: AsyncSession,
    limited_headers: Headers,
) -> None:
    exported = Permission(name="导出报表", code="report:export", module="报表")
    db_session.add(Role(name="报表员", permissions=[exported]))
    await db_session.commit()
    exported.is_deleted = True
    await db_session.commit()

    response = await client.post(
        f"/api/v1/permissions/{exported.id}/restore",
        headers=limited_headers,
    )

    assert_error(response, 403)
