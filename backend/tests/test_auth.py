"""Authentication and token lifecycle regression tests."""

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.models.refresh_session_family import RefreshSessionFamily
from app.models.user import User
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "NewUser",
            "email": "newuser@example.com",
            "password": "newpassword123",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["code"] == 201
    assert payload["data"]["username"] == "newuser"
    assert "hashed_password" not in payload["data"]


async def test_register_duplicate_username(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": test_user.username,
            "email": "another@example.com",
            "password": "newpassword123",
        },
    )

    assert_error(response, 409)


async def test_register_duplicate_email(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "anotheruser",
            "email": test_user.email,
            "password": "newpassword123",
        },
    )

    assert_error(response, 409)


async def test_register_rejects_password_over_128_characters(client: AsyncClient) -> None:
    sensitive_password = "must-not-leak-" + "x" * 129
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "longpassword",
            "email": "longpassword@example.com",
            "password": sensitive_password,
        },
    )

    assert_error(response, 422)
    assert sensitive_password not in response.text
    assert response.headers["Cache-Control"] == "no-store"


async def test_login_success(client: AsyncClient, test_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "testpassword123"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["token_type"] == "bearer"
    assert isinstance(payload["data"]["access_token"], str)
    assert response.cookies.get("refresh_token")


async def test_login_wrong_password_returns_http_401(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "wrongpassword"},
    )

    assert_error(response, 401)


async def test_login_nonexistent_user_returns_http_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "noexist", "password": "somepassword"},
    )

    assert_error(response, 401)


async def test_login_rejects_password_over_128_characters(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "x" * 129},
    )

    assert_error(response, 422)


async def test_legacy_bcrypt_login_handles_long_input_and_migrates_hash(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    legacy_password = "中" * 25
    legacy_hash = bcrypt.hashpw(
        legacy_password.encode("utf-8")[:72],
        bcrypt.gensalt(rounds=12),
    ).decode("ascii")
    legacy_user = User(
        username="legacy_bcrypt",
        email="legacy-bcrypt@example.com",
        hashed_password=legacy_hash,
    )
    db_session.add(legacy_user)
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": legacy_user.username, "password": legacy_password},
    )
    assert login_response.status_code == 200, login_response.text

    await db_session.refresh(legacy_user)
    assert legacy_user.hashed_password.startswith("$argon2")

    # The migrated Argon2id hash must use the complete password, not bcrypt's
    # historical 72-byte prefix.
    same_legacy_prefix = "中" * 24 + "文"
    wrong_suffix_response = await client.post(
        "/api/v1/auth/login",
        data={"username": legacy_user.username, "password": same_legacy_prefix},
    )
    assert_error(wrong_suffix_response, 401)


async def test_login_rejects_cross_site_browser_origin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )

    assert_error(response, 403)


async def test_login_rejects_same_site_browser_without_origin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
        headers={"Sec-Fetch-Site": "same-site"},
    )

    assert_error(response, 403)


async def test_login_rejects_request_with_no_origin_signal_at_all(
    client: AsyncClient,
) -> None:
    """A browser with no Fetch Metadata support and a stripped Referer must
    not be treated as trustworthy just because it presents no evidence."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
        headers={"Sec-Fetch-Site": ""},
    )

    assert_error(response, 403)


async def test_register_rejects_cross_site_browser_origin(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "csrf-user",
            "email": "csrf-user@example.com",
            "password": "newpassword123",
        },
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )

    assert_error(response, 403)


async def test_register_rate_limit_returns_http_429(client: AsyncClient) -> None:
    responses = [
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "rate-limit-register",
                "email": "rate-limit-register@example.com",
                "password": "newpassword123",
            },
        )
        for _ in range(6)
    ]

    assert responses[0].status_code == 201
    assert all(response.status_code == 409 for response in responses[1:5])
    assert_error(responses[5], 429)


async def test_refresh_replay_revokes_entire_token_family(
    client: AsyncClient,
    test_user: User,
) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "testpassword123"},
    )
    old_refresh_token = login_response.cookies.get("refresh_token")
    assert old_refresh_token

    rotate_response = await client.post("/api/v1/auth/refresh")
    assert rotate_response.status_code == 200, rotate_response.text
    rotated_payload = rotate_response.json()
    rotated_access_token = rotated_payload["data"]["access_token"]
    new_refresh_token = rotate_response.cookies.get("refresh_token")
    assert new_refresh_token and new_refresh_token != old_refresh_token

    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh_token)
    replay_response = await client.post("/api/v1/auth/refresh")
    assert_error(replay_response, 401)

    family_access_response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {rotated_access_token}"},
    )
    assert_error(family_access_response, 401)

    client.cookies.clear()
    client.cookies.set("refresh_token", new_refresh_token)
    family_refresh_response = await client.post("/api/v1/auth/refresh")
    assert_error(family_refresh_response, 401)


async def test_logout_revokes_access_and_refresh_tokens(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token

    logout_response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_response.status_code == 200, logout_response.text

    access_response = await client.get("/api/v1/me", headers=auth_headers)
    assert_error(access_response, 401)

    client.cookies.clear()
    client.cookies.set("refresh_token", refresh_token)
    refresh_response = await client.post("/api/v1/auth/refresh")
    assert_error(refresh_response, 401)


async def test_logout_token_mismatch_commits_family_revocation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "testpassword123"},
    )
    assert login_response.status_code == 200, login_response.text

    session = (
        await db_session.execute(
            select(RefreshSession).where(RefreshSession.user_id == test_user.id)
        )
    ).scalar_one()
    session.token_hash = "0" * 64
    await db_session.commit()

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    family = await db_session.get(RefreshSessionFamily, session.family_id)
    assert family is not None
    await db_session.refresh(family)
    assert family.revoked_at is not None
    assert family.revoked_reason == "logout_mismatch"


async def test_password_change_revokes_all_existing_tokens(
    client: AsyncClient,
    test_user: User,
    auth_headers: Headers,
) -> None:
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token

    change_response = await client.put(
        "/api/v1/me/password",
        json={
            "old_password": "testpassword123",
            "new_password": "changedpassword123",
        },
        headers=auth_headers,
    )
    assert change_response.status_code == 200, change_response.text

    old_access_response = await client.get("/api/v1/me", headers=auth_headers)
    assert_error(old_access_response, 401)

    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh_token)
    old_refresh_response = await client.post("/api/v1/auth/refresh")
    assert_error(old_refresh_response, 401)

    old_password_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "testpassword123"},
    )
    assert_error(old_password_response, 401)

    new_password_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "changedpassword123"},
    )
    assert new_password_response.status_code == 200, new_password_response.text


async def test_login_rate_limit_returns_http_429(client: AsyncClient) -> None:
    responses = [
        await client.post(
            "/api/v1/auth/login",
            data={"username": "rate-limit-missing", "password": "wrongpassword"},
        )
        for _ in range(6)
    ]

    assert all(response.status_code == 401 for response in responses[:5])
    assert_error(responses[5], 429)
    assert int(responses[5].headers["Retry-After"]) >= 1
