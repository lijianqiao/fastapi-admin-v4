"""Audit-log API regression tests."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


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
