"""Optional PostgreSQL regression for refresh-family serialization.

Set ``TEST_POSTGRES_DATABASE_URL`` to a migrated, disposable PostgreSQL database
to enable this module. The test creates uniquely named rows and deletes only that
user; it never creates or drops schemas, tables, or databases.
"""

import asyncio
import os
import selectors
import sys
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Literal
from unittest.mock import patch
from uuid import uuid4

import bcrypt
import pytest
from psycopg import Error as PsycopgError
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import decode_token, hash_password_async, verify_and_update_password
from app.crud.user import LastActiveSuperuserError, user_crud
from app.models.refresh_session_family import RefreshSessionFamily
from app.models.user import User
from app.services.auth import (
    RefreshSessionCompromisedError,
    create_login_session,
    is_session_family_active,
    revoke_all_refresh_sessions,
    rotate_refresh_session,
)

POSTGRES_DATABASE_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")
if not POSTGRES_DATABASE_URL:
    pytest.skip(
        "TEST_POSTGRES_DATABASE_URL is not configured",
        allow_module_level=True,
    )


def _validated_postgres_url(raw_url: str) -> URL:
    """Validate the opt-in target without ever displaying its credentials."""
    try:
        url = make_url(raw_url)
    except ArgumentError as exc:
        raise pytest.UsageError("TEST_POSTGRES_DATABASE_URL is not a valid database URL") from exc

    if url.get_backend_name() != "postgresql":
        raise pytest.UsageError("TEST_POSTGRES_DATABASE_URL must target PostgreSQL")
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise pytest.UsageError(
            "TEST_POSTGRES_DATABASE_URL must use the postgresql+psycopg async driver"
        )
    return url


TEST_DATABASE_URL = _validated_postgres_url(POSTGRES_DATABASE_URL)
REQUIRED_TABLES = {"users", "refresh_session_families", "refresh_sessions"}
READY_TIMEOUT_SECONDS = 5
RACE_TIMEOUT_SECONDS = 15


class SafeTestDatabaseError(RuntimeError):
    """A redacted connection failure safe to surface from the sync wrapper."""


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """Observable outcome from one independently connected rotation worker."""

    outcome: str
    backend_pid: int
    replacement_token: str | None = None


async def _assert_migrated(connection: AsyncConnection) -> None:
    table_names = await connection.run_sync(
        lambda sync_connection: set(inspect(sync_connection).get_table_names())
    )
    missing = REQUIRED_TABLES - table_names
    if missing:
        pytest.fail("TEST_POSTGRES_DATABASE_URL is not migrated; missing required auth tables")


def _create_test_engine() -> AsyncEngine:
    return create_async_engine(
        TEST_DATABASE_URL,
        pool_size=3,
        max_overflow=0,
        pool_pre_ping=True,
        hide_parameters=True,
    )


async def _preflight(engine: AsyncEngine) -> None:
    """Check connectivity and schema without exposing driver connection kwargs."""
    try:
        async with engine.connect() as connection:
            await _assert_migrated(connection)
    except SQLAlchemyError, PsycopgError:
        raise SafeTestDatabaseError("cannot connect to TEST_POSTGRES_DATABASE_URL") from None


async def _prepare_worker_connection(db: AsyncSession) -> tuple[AsyncConnection, int]:
    """Pin one connection and apply bounded PostgreSQL lock/query timeouts."""
    try:
        connection = await db.connection()
    except SQLAlchemyError, PsycopgError:
        raise SafeTestDatabaseError("cannot connect to TEST_POSTGRES_DATABASE_URL") from None

    await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    await connection.execute(text("SET LOCAL statement_timeout = '10s'"))
    backend_pid = int((await connection.execute(text("SELECT pg_backend_pid()"))).scalar_one())
    return connection, backend_pid


def _run_async_test(coroutine: Coroutine[Any, Any, None]) -> None:
    """Run one async PostgreSQL scenario and redact connection-stage failures."""
    try:
        asyncio.run(coroutine, loop_factory=_test_loop_factory)
    except SafeTestDatabaseError:
        pytest.fail(
            "cannot connect to TEST_POSTGRES_DATABASE_URL",
            pytrace=False,
        )


async def _rotate_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    raw_token: str,
    barrier: asyncio.Barrier,
) -> WorkerResult:
    """Acquire a distinct connection, rendezvous, then run the real rotation path."""
    claims = decode_token(raw_token)
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)

        await asyncio.wait_for(barrier.wait(), timeout=READY_TIMEOUT_SECONDS)
        try:
            replacement = await rotate_refresh_session(db, raw_token, claims)
        except RefreshSessionCompromisedError:
            # This mirrors the HTTP route contract: replay revocation must commit.
            await db.commit()
            return WorkerResult(outcome="compromised", backend_pid=backend_pid)

        await db.commit()
        return WorkerResult(
            outcome="rotated",
            backend_pid=backend_pid,
            replacement_token=replacement.refresh_token,
        )


def test_replay_racing_current_rotation_revokes_entire_family() -> None:
    """Run the race on a psycopg-compatible loop on every supported platform."""
    _run_async_test(_run_refresh_race())


def _test_loop_factory() -> asyncio.AbstractEventLoop:
    """Create a local loop without using the deprecated global policy API."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.SelectorEventLoop()


async def _run_refresh_race() -> None:
    """A stale-token replay cannot race a current rotation into an active family."""
    engine = _create_test_engine()
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    unique_suffix = uuid4().hex
    username = f"pg_refresh_{unique_suffix[:20]}"
    user_id: int | None = None

    try:
        await _preflight(engine)

        async with session_factory() as setup_db:
            user = User(
                username=username,
                email=f"{unique_suffix}@refresh-race.test",
                hashed_password="not-used-by-this-test",
                nickname="PostgreSQL refresh race",
                is_active=True,
                is_superuser=False,
                token_version=0,
            )
            setup_db.add(user)
            await setup_db.flush()
            user_id = user.id

            original = await create_login_session(setup_db, user)
            await setup_db.commit()

        original_claims = decode_token(original.refresh_token)
        async with session_factory() as setup_db:
            current = await rotate_refresh_session(
                setup_db,
                original.refresh_token,
                original_claims,
            )
            await setup_db.commit()

        barrier = asyncio.Barrier(2)
        replay_task = asyncio.create_task(
            _rotate_worker(
                session_factory,
                raw_token=original.refresh_token,
                barrier=barrier,
            )
        )
        current_task = asyncio.create_task(
            _rotate_worker(
                session_factory,
                raw_token=current.refresh_token,
                barrier=barrier,
            )
        )
        replay_result, current_result = await asyncio.wait_for(
            asyncio.gather(replay_task, current_task),
            timeout=RACE_TIMEOUT_SECONDS,
        )

        assert replay_result.backend_pid != current_result.backend_pid
        assert replay_result.outcome == "compromised"

        async with session_factory() as verify_db:
            family = (
                await verify_db.execute(
                    select(RefreshSessionFamily).where(RefreshSessionFamily.id == current.family_id)
                )
            ).scalar_one()
            assert family.revoked_at is not None
            assert family.revoked_reason == "refresh_replay"
            assert not await is_session_family_active(
                verify_db,
                user_id=user_id,
                family_id=current.family_id,
                token_version=0,
            )

            with pytest.raises(RefreshSessionCompromisedError):
                await rotate_refresh_session(
                    verify_db,
                    current.refresh_token,
                    decode_token(current.refresh_token),
                )
            if current_result.replacement_token is not None:
                with pytest.raises(RefreshSessionCompromisedError):
                    await rotate_refresh_session(
                        verify_db,
                        current_result.replacement_token,
                        decode_token(current_result.replacement_token),
                    )
            await verify_db.rollback()
    finally:
        try:
            if user_id is not None:
                async with session_factory() as cleanup_db:
                    await cleanup_db.execute(delete(User).where(User.username == username))
                    await cleanup_db.commit()
        finally:
            await engine.dispose()


async def _change_password_while_login_waits(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    old_password: str,
    new_password: str,
    row_locked: asyncio.Event,
    login_waiting_for_lock: asyncio.Event,
) -> int:
    """Hold the user lock until login has verified the legacy snapshot."""
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
        row_locked.set()
        await asyncio.wait_for(
            login_waiting_for_lock.wait(),
            timeout=READY_TIMEOUT_SECONDS,
        )
        changed = await user_crud.change_password(
            db,
            user_id,
            old_password,
            new_password,
        )
        assert changed
        await db.commit()
        return backend_pid


async def _login_while_password_changes(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    username: str,
    old_password: str,
    row_locked: asyncio.Event,
) -> tuple[User | None, int]:
    """Read the old bcrypt hash, then block on the changer's row lock."""
    await asyncio.wait_for(row_locked.wait(), timeout=READY_TIMEOUT_SECONDS)
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)
        authenticated = await user_crud.authenticate(db, username, old_password)
        await db.commit()
        return authenticated, backend_pid


def test_bcrypt_login_upgrade_cannot_overwrite_concurrent_password_change() -> None:
    """A stale bcrypt upgrade must reverify after acquiring the user lock."""
    _run_async_test(_run_bcrypt_password_race())


async def _run_bcrypt_password_race() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    unique_suffix = uuid4().hex
    username = f"pg_bcrypt_{unique_suffix[:20]}"
    old_password = f"old-{unique_suffix}"
    new_password = f"new-{unique_suffix}"
    user_id: int | None = None

    try:
        await _preflight(engine)
        legacy_hash = await asyncio.to_thread(
            lambda: bcrypt.hashpw(
                old_password.encode(),
                bcrypt.gensalt(rounds=4),
            ).decode()
        )
        async with session_factory() as setup_db:
            await _prepare_worker_connection(setup_db)
            user = User(
                username=username,
                email=f"{unique_suffix}@bcrypt-race.test",
                hashed_password=legacy_hash,
                nickname="bcrypt race",
                is_active=True,
                is_superuser=False,
                token_version=0,
            )
            setup_db.add(user)
            await setup_db.flush()
            user_id = user.id
            await setup_db.commit()

        row_locked = asyncio.Event()
        login_waiting_for_lock = asyncio.Event()
        original_get_for_update = user_crud.get_by_identifier_for_update

        async def signal_before_login_lock(
            db: AsyncSession,
            identifier: str,
        ) -> User | None:
            login_waiting_for_lock.set()
            return await original_get_for_update(db, identifier)

        with patch.object(
            user_crud,
            "get_by_identifier_for_update",
            new=signal_before_login_lock,
        ):
            change_pid, login_result = await asyncio.wait_for(
                asyncio.gather(
                    _change_password_while_login_waits(
                        session_factory,
                        user_id=user_id,
                        old_password=old_password,
                        new_password=new_password,
                        row_locked=row_locked,
                        login_waiting_for_lock=login_waiting_for_lock,
                    ),
                    _login_while_password_changes(
                        session_factory,
                        username=username,
                        old_password=old_password,
                        row_locked=row_locked,
                    ),
                ),
                timeout=RACE_TIMEOUT_SECONDS,
            )

        authenticated, login_pid = login_result
        assert change_pid != login_pid
        assert authenticated is None

        async with session_factory() as verify_db:
            await _prepare_worker_connection(verify_db)
            final_user = (
                await verify_db.execute(select(User).where(User.id == user_id))
            ).scalar_one()
            new_verification = await verify_and_update_password(
                new_password,
                final_user.hashed_password,
            )
            old_verification = await verify_and_update_password(
                old_password,
                final_user.hashed_password,
            )
            assert new_verification.valid
            assert not old_verification.valid
            assert final_user.hashed_password.startswith("$argon2")
            assert final_user.token_version == 1
            await verify_db.rollback()
    finally:
        try:
            if user_id is not None:
                async with session_factory() as cleanup_db:
                    await _prepare_worker_connection(cleanup_db)
                    await cleanup_db.execute(delete(User).where(User.username == username))
                    await cleanup_db.commit()
        finally:
            await engine.dispose()


@dataclass(frozen=True, slots=True)
class SuperuserMutationResult:
    """Outcome of one concurrent last-superuser mutation."""

    outcome: Literal["applied", "rejected"]
    backend_pid: int


async def _mutate_superuser(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    operation: Literal["deactivate", "delete"],
    barrier: asyncio.Barrier,
) -> SuperuserMutationResult:
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)
        await asyncio.wait_for(barrier.wait(), timeout=READY_TIMEOUT_SECONDS)
        try:
            if operation == "deactivate":
                updated = await user_crud.update(db, user_id, {"is_active": False})
                assert updated is not None
            else:
                assert await user_crud.soft_delete(db, user_id)
        except LastActiveSuperuserError:
            await db.rollback()
            return SuperuserMutationResult("rejected", backend_pid)

        await db.commit()
        return SuperuserMutationResult("applied", backend_pid)


def test_concurrent_superuser_removals_preserve_one_active_superuser() -> None:
    """Concurrent deactivate/delete operations cannot remove both final admins."""
    _run_async_test(_run_last_superuser_race())


async def _run_last_superuser_race() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    unique_suffix = uuid4().hex
    usernames = (
        f"pg_admin_a_{unique_suffix[:16]}",
        f"pg_admin_b_{unique_suffix[:16]}",
    )
    user_ids: list[int] = []

    try:
        await _preflight(engine)
        async with session_factory() as setup_db:
            await _prepare_worker_connection(setup_db)
            existing_active_superusers = await setup_db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.is_superuser.is_(True),
                    User.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            )
            if existing_active_superusers:
                pytest.skip(
                    "last-superuser race requires a dedicated database without existing admins"
                )

            users = [
                User(
                    username=username,
                    email=f"{username}@superuser-race.test",
                    hashed_password="not-used-by-this-test",
                    nickname=username,
                    is_active=True,
                    is_superuser=True,
                    token_version=0,
                )
                for username in usernames
            ]
            setup_db.add_all(users)
            await setup_db.flush()
            user_ids = [user.id for user in users]
            await setup_db.commit()

        barrier = asyncio.Barrier(2)
        deactivate_result, delete_result = await asyncio.wait_for(
            asyncio.gather(
                _mutate_superuser(
                    session_factory,
                    user_id=user_ids[0],
                    operation="deactivate",
                    barrier=barrier,
                ),
                _mutate_superuser(
                    session_factory,
                    user_id=user_ids[1],
                    operation="delete",
                    barrier=barrier,
                ),
            ),
            timeout=RACE_TIMEOUT_SECONDS,
        )

        assert deactivate_result.backend_pid != delete_result.backend_pid
        assert {deactivate_result.outcome, delete_result.outcome} == {
            "applied",
            "rejected",
        }

        async with session_factory() as verify_db:
            await _prepare_worker_connection(verify_db)
            active_ids = list(
                (
                    await verify_db.scalars(
                        select(User.id).where(
                            User.id.in_(user_ids),
                            User.is_superuser.is_(True),
                            User.is_active.is_(True),
                            User.is_deleted.is_(False),
                        )
                    )
                ).all()
            )
            assert len(active_ids) == 1
            await verify_db.rollback()
    finally:
        try:
            if user_ids:
                async with session_factory() as cleanup_db:
                    await _prepare_worker_connection(cleanup_db)
                    await cleanup_db.execute(delete(User).where(User.username.in_(usernames)))
                    await cleanup_db.commit()
        finally:
            await engine.dispose()


async def _login_and_create_family(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    username: str,
    password: str,
    login_locked_user: asyncio.Event,
    password_change_started: asyncio.Event,
) -> tuple[str, int, int]:
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)
        user = await user_crud.authenticate(db, username, password)
        assert user is not None
        login_locked_user.set()
        await asyncio.wait_for(
            password_change_started.wait(),
            timeout=READY_TIMEOUT_SECONDS,
        )
        tokens = await create_login_session(db, user)
        await db.commit()
        return tokens.family_id, user.id, backend_pid


async def _change_password_and_revoke_families(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: int,
    old_password: str,
    new_password: str,
    login_locked_user: asyncio.Event,
    password_change_started: asyncio.Event,
) -> int:
    await asyncio.wait_for(login_locked_user.wait(), timeout=READY_TIMEOUT_SECONDS)
    async with session_factory() as db:
        _connection, backend_pid = await _prepare_worker_connection(db)
        password_change_started.set()
        changed = await user_crud.change_password(
            db,
            user_id,
            old_password,
            new_password,
        )
        assert changed
        await revoke_all_refresh_sessions(db, user_id, reason="password_changed")
        await db.commit()
        return backend_pid


def test_login_family_racing_password_change_is_eventually_revoked() -> None:
    """A login committed just before a password change cannot leave an old family active."""
    _run_async_test(_run_login_family_password_race())


async def _run_login_family_password_race() -> None:
    engine = _create_test_engine()
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    unique_suffix = uuid4().hex
    username = f"pg_family_pwd_{unique_suffix[:16]}"
    old_password = f"old-{unique_suffix}"
    new_password = f"new-{unique_suffix}"
    user_id: int | None = None

    try:
        await _preflight(engine)
        async with session_factory() as setup_db:
            await _prepare_worker_connection(setup_db)
            user = User(
                username=username,
                email=f"{unique_suffix}@family-password-race.test",
                hashed_password=await hash_password_async(old_password),
                nickname="family password race",
                is_active=True,
                is_superuser=False,
                token_version=0,
            )
            setup_db.add(user)
            await setup_db.flush()
            user_id = user.id
            await setup_db.commit()

        login_locked_user = asyncio.Event()
        password_change_started = asyncio.Event()
        login_result, change_pid = await asyncio.wait_for(
            asyncio.gather(
                _login_and_create_family(
                    session_factory,
                    username=username,
                    password=old_password,
                    login_locked_user=login_locked_user,
                    password_change_started=password_change_started,
                ),
                _change_password_and_revoke_families(
                    session_factory,
                    user_id=user_id,
                    old_password=old_password,
                    new_password=new_password,
                    login_locked_user=login_locked_user,
                    password_change_started=password_change_started,
                ),
            ),
            timeout=RACE_TIMEOUT_SECONDS,
        )
        family_id, logged_in_user_id, login_pid = login_result
        assert login_pid != change_pid
        assert logged_in_user_id == user_id

        async with session_factory() as verify_db:
            await _prepare_worker_connection(verify_db)
            family = await verify_db.get(RefreshSessionFamily, family_id)
            assert family is not None
            assert family.revoked_at is not None
            assert family.revoked_reason == "password_changed"
            assert not await is_session_family_active(
                verify_db,
                user_id=user_id,
                family_id=family_id,
                token_version=0,
            )
            final_user = await verify_db.get(User, user_id)
            assert final_user is not None
            assert final_user.token_version == 1
            await verify_db.rollback()
    finally:
        try:
            if user_id is not None:
                async with session_factory() as cleanup_db:
                    await _prepare_worker_connection(cleanup_db)
                    await cleanup_db.execute(delete(User).where(User.username == username))
                    await cleanup_db.commit()
        finally:
            await engine.dispose()
