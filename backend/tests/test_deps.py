"""Shared request dependencies."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Audit, page_query
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User


def test_page_query_computes_offset() -> None:
    params = page_query(default_size=20, max_size=50)(page=3, page_size=20, search=None)

    assert params.skip == 40


async def test_audit_commit_persists_record(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    audit = Audit(db=db_session, actor=test_user, ip="203.0.113.7")

    await audit.commit("demo_action", "demo:1", "细节")

    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "demo_action"))
    assert row is not None
    assert (row.user_id, row.target, row.detail, row.ip) == (
        test_user.id,
        "demo:1",
        "细节",
        "203.0.113.7",
    )


def test_openapi_lists_required_permissions() -> None:
    schema = app.openapi()

    assert schema["paths"]["/api/v1/users"]["get"]["x-permissions"] == ["user:read"]
    assert "x-permissions" not in schema["paths"]["/api/v1/me"]["get"]
