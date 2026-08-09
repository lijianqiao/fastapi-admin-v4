"""Refresh-session retention cleanup tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.models.refresh_session_family import RefreshSessionFamily
from app.models.user import User
from app.services.session_cleanup import purge_expired_refresh_history

pytestmark = pytest.mark.asyncio


async def test_cleanup_removes_only_expired_history(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    now = datetime.now(UTC)
    expired_family = RefreshSessionFamily(
        id="expired-family",
        user_id=test_user.id,
        token_version=0,
        expires_at=now - timedelta(days=40),
    )
    active_family = RefreshSessionFamily(
        id="active-family",
        user_id=test_user.id,
        token_version=0,
        expires_at=now + timedelta(days=7),
    )
    db_session.add_all([expired_family, active_family])
    await db_session.flush()
    old_session = RefreshSession(
        user_id=test_user.id,
        jti="old-session",
        family_id=expired_family.id,
        token_hash="1" * 64,
        token_version=0,
        expires_at=now - timedelta(days=40),
    )
    recently_expired_session = RefreshSession(
        user_id=test_user.id,
        jti="recently-expired-session",
        family_id=active_family.id,
        token_hash="2" * 64,
        token_version=0,
        expires_at=now - timedelta(days=2),
    )
    active_session = RefreshSession(
        user_id=test_user.id,
        jti="active-session",
        family_id=active_family.id,
        token_hash="3" * 64,
        token_version=0,
        expires_at=now + timedelta(days=7),
    )
    db_session.add_all([old_session, recently_expired_session, active_session])
    await db_session.commit()

    result = await purge_expired_refresh_history(
        db_session,
        replay_grace_days=1,
        family_retention_days=30,
        batch_size=100,
        now=now,
    )
    await db_session.commit()

    assert result.sessions_deleted == 2
    assert result.families_deleted == 1
    assert await db_session.get(RefreshSessionFamily, expired_family.id) is None
    assert await db_session.get(RefreshSessionFamily, active_family.id) is not None
    assert await db_session.get(RefreshSession, active_session.id) is not None
