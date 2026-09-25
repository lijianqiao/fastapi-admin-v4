"""Audit-log API regression tests."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.crud.audit_log import audit_log_crud
from app.models.user import User
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]
type LoginUser = Callable[[str, str], Awaitable[Headers]]


async def test_list_audit_logs(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get("/api/v1/audit-logs", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["data"]["total"] >= 1
    assert any(item["action"] == "login" for item in payload["data"]["items"])


async def test_list_audit_logs_with_filter(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get(
        "/api/v1/audit-logs",
        params={"action": "login"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert items
    assert all(item["action"] == "login" for item in items)


async def test_list_audit_logs_filter_by_username(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    response = await client.get(
        "/api/v1/audit-logs",
        params={"username": "testuser"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert items
    assert all(item["username"] == "testuser" for item in items)


async def test_audit_log_pagination(
    client: AsyncClient,
    auth_headers: Headers,
) -> None:
    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpassword123"},
        )
        assert response.status_code == 200, response.text

    response = await client.get(
        "/api/v1/audit-logs",
        params={"page": 1, "page_size": 2},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["page"] == 1
    assert page["page_size"] == 2
    assert len(page["items"]) == 2


async def test_audit_keeps_actor_username_after_user_is_purged(
    client: AsyncClient,
    db_session: AsyncSession,
    superuser_headers: Headers,
    login_user: LoginUser,
) -> None:
    leaver = User(
        username="leaver",
        email="leaver@example.com",
        hashed_password=hash_password("leaverpassword123"),
    )
    db_session.add(leaver)
    await db_session.commit()
    await login_user("leaver", "leaverpassword123")

    deleted = await client.delete(f"/api/v1/users/{leaver.id}", headers=superuser_headers)
    assert deleted.status_code == 200, deleted.text
    purged = await client.delete(f"/api/v1/users/{leaver.id}/purge", headers=superuser_headers)
    assert purged.status_code == 200, purged.text

    response = await client.get(
        "/api/v1/audit-logs",
        params={"action": "login", "username": "leaver"},
        headers=superuser_headers,
    )

    items = response.json()["data"]["items"]
    assert items
    assert all(item["username"] == "leaver" and item["user_id"] == leaver.id for item in items)


async def test_failed_login_records_attempted_identifier(
    client: AsyncClient,
    superuser_headers: Headers,
) -> None:
    await client.post(
        "/api/v1/auth/login",
        data={"username": "Nobody@Example.com", "password": "wrongpassword1"},
    )

    response = await client.get(
        "/api/v1/audit-logs",
        params={"action": "login_failed"},
        headers=superuser_headers,
    )

    targets = [item["target"] for item in response.json()["data"]["items"]]
    assert targets == ["login:nobody@example.com"]


async def test_audit_total_is_capped(
    client: AsyncClient,
    auth_headers: Headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit_log_crud, "count_cap", 2)
    for _ in range(3):
        await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpassword123"},
        )

    response = await client.get("/api/v1/audit-logs", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 3  # count_cap + 1 表示"超过上限"


async def test_audit_rejects_pages_beyond_cap(
    client: AsyncClient,
    auth_headers: Headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit_log_crud, "count_cap", 2)

    response = await client.get(
        "/api/v1/audit-logs",
        params={"page": 2, "page_size": 2},
        headers=auth_headers,
    )

    assert_error(response, 400)
