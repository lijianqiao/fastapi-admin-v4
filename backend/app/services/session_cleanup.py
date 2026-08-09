"""Bounded refresh-session retention cleanup."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.models.refresh_session_family import RefreshSessionFamily


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Rows removed by one short cleanup transaction."""

    sessions_deleted: int
    families_deleted: int

    @property
    def total(self) -> int:
        return self.sessions_deleted + self.families_deleted


async def purge_expired_refresh_history(
    db: AsyncSession,
    *,
    replay_grace_days: int,
    family_retention_days: int,
    batch_size: int,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete one lock-safe batch while keeping transactions short."""
    current_time = now or datetime.now(UTC)
    session_cutoff = current_time - timedelta(days=replay_grace_days)
    family_cutoff = current_time - timedelta(days=family_retention_days)

    session_ids = list(
        (
            await db.scalars(
                select(RefreshSession.id)
                .where(RefreshSession.expires_at < session_cutoff)
                .order_by(RefreshSession.expires_at, RefreshSession.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    if session_ids:
        await db.execute(delete(RefreshSession).where(RefreshSession.id.in_(session_ids)))

    family_ids = list(
        (
            await db.scalars(
                select(RefreshSessionFamily.id)
                .where(RefreshSessionFamily.expires_at < family_cutoff)
                .order_by(RefreshSessionFamily.expires_at, RefreshSessionFamily.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    if family_ids:
        await db.execute(
            delete(RefreshSessionFamily).where(RefreshSessionFamily.id.in_(family_ids))
        )

    await db.flush()
    return CleanupResult(
        sessions_deleted=len(session_ids),
        families_deleted=len(family_ids),
    )
