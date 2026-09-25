"""Request transaction atomicity regression tests."""

import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps as deps_module
from app.models.permission import Permission
from tests.assertions import assert_error

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_business_write_rolls_back_when_audit_write_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
    monkeypatch: MonkeyPatch,
) -> None:
    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(deps_module, "log_audit", fail_audit)
    response = await client.post(
        "/api/v1/permissions",
        json={
            "name": "事务原子性测试",
            "code": "transaction:atomic",
            "module": "测试",
        },
        headers=auth_headers,
    )

    assert_error(response, 500)
    permission = await db_session.scalar(
        select(Permission).where(Permission.code == "transaction:atomic")
    )
    assert permission is None
