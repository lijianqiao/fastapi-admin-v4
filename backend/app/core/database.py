"""Asynchronous SQLAlchemy engine and request-scoped session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _to_async_database_url(url: str) -> str:
    """Normalize common synchronous URLs to their async SQLAlchemy dialect."""
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


database_url = _to_async_database_url(settings.DATABASE_URL)

# SQL 语句输出由日志级别控制（见 app.main.configure_logging），避免 echo 再挂一层 handler 导致重复打印
if database_url.startswith("sqlite+"):
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        echo=False,
        hide_parameters=True,
    )
else:
    engine = create_async_engine(
        database_url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=False,
        hide_parameters=True,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield one async session for the complete FastAPI dependency chain.

    CRUD functions only flush. A mutating endpoint must commit exactly once after
    both its business change and audit record succeed. Any exception rolls back
    all pending work before the session is returned to the pool.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


async def release_connection(db: AsyncSession) -> None:
    """End a read-only transaction so the pooled connection is free during CPU work.

    ``expire_on_commit=False`` keeps already-loaded objects usable. Call this only
    before password hashing and only while nothing is pending in the session.
    """
    if db.new or db.dirty or db.deleted:
        raise RuntimeError("release_connection 只能在没有未提交写入时调用")
    await db.commit()
