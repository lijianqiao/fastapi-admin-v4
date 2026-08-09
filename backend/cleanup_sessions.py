"""CLI entry point for bounded refresh-session retention cleanup."""

import asyncio
import sys

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.services.session_cleanup import purge_expired_refresh_history


async def cleanup() -> tuple[int, int]:
    """Drain expired history in short, independently committed batches."""
    sessions_deleted = 0
    families_deleted = 0
    try:
        while True:
            async with AsyncSessionLocal() as db:
                result = await purge_expired_refresh_history(
                    db,
                    replay_grace_days=settings.REFRESH_SESSION_REPLAY_GRACE_DAYS,
                    family_retention_days=settings.REFRESH_SESSION_HISTORY_RETENTION_DAYS,
                    batch_size=settings.REFRESH_SESSION_CLEANUP_BATCH_SIZE,
                )
                await db.commit()
            sessions_deleted += result.sessions_deleted
            families_deleted += result.families_deleted
            if result.total < settings.REFRESH_SESSION_CLEANUP_BATCH_SIZE:
                break
    finally:
        await engine.dispose()
    return sessions_deleted, families_deleted


def main() -> None:
    """Run the cleanup with the platform-compatible application loop."""
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sessions_deleted, families_deleted = asyncio.run(
        cleanup(),
        loop_factory=loop_factory,
    )
    print(
        "refresh session cleanup complete: "
        f"sessions={sessions_deleted}, families={families_deleted}"
    )


if __name__ == "__main__":
    main()
