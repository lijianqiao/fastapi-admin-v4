"""A non-superuser administrator must not be able to act on superuser accounts."""

from collections.abc import Awaitable, Callable

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]

MUTATIONS: list[tuple[str, str, dict[str, object] | None]] = [
    ("PATCH", "/api/v1/users/{id}", {"nickname": "被改名"}),
    ("PATCH", "/api/v1/users/{id}", {"is_active": False}),
    ("DELETE", "/api/v1/users/{id}", None),
    ("PUT", "/api/v1/users/{id}/password", {"new_password": "attackerchosen123"}),
    ("PUT", "/api/v1/users/{id}/roles", {"role_ids": []}),
]


@pytest_asyncio.fixture
async def deleted_superuser(db_session: AsyncSession) -> User:
    user = User(
        username="retired_admin",
        email="retired-admin@example.com",
        hashed_password=hash_password("retiredpassword123"),
        is_superuser=True,
        is_deleted=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
async def test_non_superuser_cannot_mutate_superuser(
    client: AsyncClient,
    auth_headers: Headers,
    superuser: User,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    response = await client.request(
        method,
        path.format(id=superuser.id),
        json=body,
        headers=auth_headers,
    )

    assert_error(response, 403)


async def test_superuser_password_survives_takeover_attempt(
    client: AsyncClient,
    auth_headers: Headers,
    superuser: User,
    login_user: LoginUser,
) -> None:
    await client.put(
        f"/api/v1/users/{superuser.id}/password",
        json={"new_password": "attackerchosen123"},
        headers=auth_headers,
    )

    await login_user(superuser.username, "adminpassword123")


@pytest.mark.parametrize(("method", "suffix"), [("POST", "restore"), ("DELETE", "purge")])
async def test_non_superuser_cannot_restore_or_purge_superuser(
    client: AsyncClient,
    auth_headers: Headers,
    deleted_superuser: User,
    method: str,
    suffix: str,
) -> None:
    response = await client.request(
        method,
        f"/api/v1/users/{deleted_superuser.id}/{suffix}",
        headers=auth_headers,
    )

    assert_error(response, 403)


async def test_superuser_can_reset_another_superuser_password(
    client: AsyncClient,
    db_session: AsyncSession,
    superuser_headers: Headers,
    login_user: LoginUser,
) -> None:
    other = User(
        username="second_admin",
        email="second-admin@example.com",
        hashed_password=hash_password("secondpassword123"),
        is_superuser=True,
    )
    db_session.add(other)
    await db_session.commit()

    response = await client.put(
        f"/api/v1/users/{other.id}/password",
        json={"new_password": "rotatedpassword123"},
        headers=superuser_headers,
    )

    assert response.status_code == 200, response.text
    await login_user(other.username, "rotatedpassword123")
