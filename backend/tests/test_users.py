"""User API regression tests."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User, user_roles
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]


async def test_list_users(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.get("/api/v1/users", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["data"]["total"] >= 1
    assert any(item["id"] == test_user.id for item in payload["data"]["items"])


async def test_list_users_with_search(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.get(
        "/api/v1/users",
        params={"search": test_user.username},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 1


async def test_user_search_treats_sql_wildcards_as_literals(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get(
        "/api/v1/users",
        params={"search": "%"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 0


async def test_create_user(client: AsyncClient, auth_headers: Headers) -> None:
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "created_user",
            "email": "created@example.com",
            "password": "createdpassword123",
            "nickname": "创建的用户",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["username"] == "created_user"


async def test_create_user_with_invalid_role_is_atomic(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "invalid_role_user",
            "email": "invalid-role@example.com",
            "password": "createdpassword123",
            "role_ids": [999_999],
        },
        headers=auth_headers,
    )

    assert_error(response, 422)
    created_user = await db_session.scalar(select(User).where(User.username == "invalid_role_user"))
    assert created_user is None


async def test_get_user(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["id"] == test_user.id


async def test_get_nonexistent_user_returns_http_404(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get("/api/v1/users/999999", headers=auth_headers)

    assert_error(response, 404)


async def test_update_user(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.put(
        f"/api/v1/users/{test_user.id}",
        json={"nickname": "更新后的昵称"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["nickname"] == "更新后的昵称"


async def test_disable_user_increments_version_and_revokes_existing_session(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    login_user: LoginUser,
) -> None:
    target = User(
        username="todisable",
        email="todisable@example.com",
        hashed_password=hash_password("disablepassword123"),
    )
    db_session.add(target)
    await db_session.commit()
    target_headers = await login_user(target.username, "disablepassword123")

    response = await client.patch(
        f"/api/v1/users/{target.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    access_response = await client.get("/api/v1/me", headers=target_headers)
    assert_error(access_response, 401)

    await db_session.refresh(target)
    assert target.token_version == 1
    assert target.is_active is False


async def test_cannot_disable_current_user(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"is_active": False},
        headers=auth_headers,
    )

    assert_error(response, 400)
    await db_session.refresh(test_user)
    assert test_user.is_active is True
    assert test_user.token_version == 0


async def test_delete_user(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    user = User(
        username="todelete",
        email="todelete@example.com",
        hashed_password=hash_password("deletepassword123"),
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    response = await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    is_deleted = await db_session.scalar(select(User.is_deleted).where(User.id == user_id))
    assert is_deleted is True


async def test_assign_roles(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
    test_role: Role,
) -> None:
    response = await client.put(
        f"/api/v1/users/{test_user.id}/roles",
        json={"role_ids": [test_role.id]},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert [role["id"] for role in response.json()["data"]["roles"]] == [test_role.id]


async def test_assign_invalid_role_preserves_existing_roles(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    test_user: User,
    test_role: Role,
) -> None:
    response = await client.put(
        f"/api/v1/users/{test_user.id}/roles",
        json={"role_ids": [999_999]},
        headers=auth_headers,
    )

    assert_error(response, 422)
    role_ids = list(
        (
            await db_session.scalars(
                select(user_roles.c.role_id).where(user_roles.c.user_id == test_user.id)
            )
        ).all()
    )
    assert role_ids == [test_role.id]


async def test_reset_password_by_admin_revokes_target_session_and_sets_new_password(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    login_user: LoginUser,
) -> None:
    target = User(
        username="toreset",
        email="toreset@example.com",
        hashed_password=hash_password("oldpassword123"),
    )
    db_session.add(target)
    await db_session.commit()
    target_headers = await login_user(target.username, "oldpassword123")

    response = await client.put(
        f"/api/v1/users/{target.id}/password",
        json={"new_password": "brandnewpassword123"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    # The old access token's session was revoked by the reset.
    access_response = await client.get("/api/v1/me", headers=target_headers)
    assert_error(access_response, 401)

    # The new password now authenticates; the old one no longer does.
    new_headers = await login_user(target.username, "brandnewpassword123")
    assert "Authorization" in new_headers
    old_password_response = await client.post(
        "/api/v1/auth/login",
        data={"username": target.username, "password": "oldpassword123"},
    )
    assert_error(old_password_response, 401)


async def test_reset_password_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
    login_user: LoginUser,
    test_user: User,
) -> None:
    no_permission_role = Role(name="无权限角色", permissions=[])
    read_only_user = User(
        username="reset_reader",
        email="reset-reader@example.com",
        hashed_password=hash_password("readerpassword123"),
        roles=[no_permission_role],
    )
    db_session.add(read_only_user)
    await db_session.commit()
    headers = await login_user(read_only_user.username, "readerpassword123")

    response = await client.put(
        f"/api/v1/users/{test_user.id}/password",
        json={"new_password": "shouldnotapply123"},
        headers=headers,
    )

    assert_error(response, 403)


async def test_cannot_reset_own_password_via_admin_endpoint(
    client: AsyncClient,
    auth_headers: Headers,
    test_user: User,
) -> None:
    response = await client.put(
        f"/api/v1/users/{test_user.id}/password",
        json={"new_password": "selfresetpassword123"},
        headers=auth_headers,
    )

    assert_error(response, 400)


async def test_reset_password_nonexistent_user_returns_http_404(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.put(
        "/api/v1/users/999999/password",
        json={"new_password": "irrelevantpassword123"},
        headers=auth_headers,
    )

    assert_error(response, 404)


async def test_unauthorized_access_returns_http_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users")

    assert_error(response, 401)
