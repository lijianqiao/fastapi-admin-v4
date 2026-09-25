"""Request correlation IDs and the readiness probe."""

import logging
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app


async def test_response_carries_generated_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert len(response.headers["x-request-id"]) == 32


async def test_well_formed_inbound_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "trace-1234abcd"})

    assert response.headers["x-request-id"] == "trace-1234abcd"


async def test_malformed_inbound_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id with spaces"})

    assert response.headers["x-request-id"] != "bad id with spaces"
    assert len(response.headers["x-request-id"]) == 32


def test_log_records_carry_request_id(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        logging.getLogger("observability-test").info("hello")

    assert caplog.records[-1].__dict__["request_id"] == "-"


async def test_readiness_reports_database_up(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_reports_database_down(client: AsyncClient) -> None:
    class _BrokenSession:
        async def execute(self, *_args: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("database is down"))

    async def broken_db() -> AsyncIterator[_BrokenSession]:
        yield _BrokenSession()

    app.dependency_overrides[get_db] = broken_db

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["message"] == "数据库不可用"
