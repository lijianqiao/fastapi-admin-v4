"""User use cases: KDF work must not hold a pooled connection."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.security import PasswordVerification, hash_password
from app.models.user import User
from app.services import users as users_service


async def test_reset_password_hashes_outside_a_transaction(
    db_session: AsyncSession,
    superuser: User,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[bool] = []

    async def spy_hash(password: str) -> str:
        observed.append(db_session.in_transaction())
        return hash_password(password)

    monkeypatch.setattr(users_service, "hash_password_async", spy_hash)

    await users_service.reset_password(db_session, superuser, test_user.id, "brandnewpassword123")
    await db_session.commit()

    assert observed == [False]


async def test_change_password_verifies_and_hashes_outside_a_transaction(
    db_session: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, bool]] = []
    real_verify = users_service.verify_and_update_password
    real_hash = users_service.hash_password_async

    async def spy_verify(password: str, hashed: str | None) -> PasswordVerification:
        observed.append(("verify", db_session.in_transaction()))
        return await real_verify(password, hashed)

    async def spy_hash(password: str) -> str:
        observed.append(("hash", db_session.in_transaction()))
        return await real_hash(password)

    monkeypatch.setattr(users_service, "verify_and_update_password", spy_verify)
    monkeypatch.setattr(users_service, "hash_password_async", spy_hash)

    changed = await users_service.change_password(
        db_session,
        test_user.id,
        "testpassword123",
        "brandnewpassword123",
    )
    await db_session.commit()

    assert changed
    assert observed == [("verify", False), ("hash", False)]


async def test_change_password_loses_to_a_concurrent_change(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A change committed between the optimistic read and the row lock must win."""
    real_hash = users_service.hash_password_async
    other_sessions = async_sessionmaker(db_engine, expire_on_commit=False)

    async def hash_while_someone_else_changes_it(password: str) -> str:
        async with other_sessions() as other:
            user = await other.get(User, test_user.id)
            assert user is not None
            user.hashed_password = hash_password("someoneelsespassword1")
            await other.commit()
        return await real_hash(password)

    monkeypatch.setattr(users_service, "hash_password_async", hash_while_someone_else_changes_it)

    changed = await users_service.change_password(
        db_session,
        test_user.id,
        "testpassword123",
        "brandnewpassword123",
    )

    assert not changed
