"""认证业务服务：登录保护、密码验证与 refresh session 生命周期。"""

import asyncio
import hashlib
import hmac
import math
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    issue_refresh_token,
    refresh_token_hash_matches,
)
from app.crud.user import user_crud
from app.models.refresh_session import RefreshSession
from app.models.refresh_session_family import RefreshSessionFamily
from app.models.user import User
from app.schemas.auth import TokenPayload


class RefreshTokenError(Exception):
    """refresh token 无效或会话不可用。"""


class RefreshSessionCompromisedError(RefreshTokenError):
    """检测到 refresh token 重放；调用方必须提交 family 撤销。"""

    def __init__(self, message: str, *, user_id: int | None = None) -> None:
        super().__init__(message)
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class SessionTokens:
    """一次登录或轮换产生的 token 对。"""

    access_token: str
    refresh_token: str
    family_id: str


class LoginRateLimiter:
    """单进程滑动窗口限流器。

    这是应用侧的安全兜底。多 worker/多实例生产部署仍需在网关或共享存储层限流。
    """

    def __init__(self, attempts: int, window_seconds: int) -> None:
        self._attempts = attempts
        self._ip_attempts = attempts * 5
        self._account_attempts = attempts * 5
        self._window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    def _key(self, kind: str, client_ip: str, identifier: str = "") -> str:
        key_material = f"{kind}\0{client_ip}\0{identifier.casefold()}"
        return hmac.new(
            settings.secret_key.encode("utf-8"),
            key_material.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def hit(self, client_ip: str, identifier: str) -> int | None:
        """Record one attempt and enforce both account/IP and IP-wide windows."""
        pair_key = self._key("pair", client_ip, identifier)
        ip_key = self._key("ip", client_ip)
        account_key = self._key("account", "all", identifier)
        now = monotonic()
        cutoff = now - self._window_seconds

        async with self._lock:
            keys = (pair_key, ip_key, account_key)
            new_key_count = sum(key not in self._entries for key in keys)
            if len(self._entries) + new_key_count > 4096:
                self._remove_stale_entries(cutoff)
                new_key_count = sum(key not in self._entries for key in keys)
            if len(self._entries) + new_key_count > 4096:
                return self._window_seconds

            windows = (
                (self._entries.setdefault(pair_key, deque()), self._attempts),
                (self._entries.setdefault(ip_key, deque()), self._ip_attempts),
                (self._entries.setdefault(account_key, deque()), self._account_attempts),
            )
            retry_after = 0
            for attempts, limit in windows:
                while attempts and attempts[0] <= cutoff:
                    attempts.popleft()
                if len(attempts) >= limit:
                    retry_after = max(
                        retry_after,
                        max(1, math.ceil(attempts[0] + self._window_seconds - now)),
                    )
            if retry_after:
                if not windows[0][0]:
                    self._entries.pop(pair_key, None)
                return retry_after

            for attempts, _ in windows:
                attempts.append(now)
            return None

    async def clear(self, client_ip: str, identifier: str) -> None:
        """Remove the successful attempt while retaining prior IP failures."""
        async with self._lock:
            self._entries.pop(self._key("pair", client_ip, identifier), None)
            self._entries.pop(self._key("account", "all", identifier), None)
            ip_key = self._key("ip", client_ip)
            ip_attempts = self._entries.get(ip_key)
            if ip_attempts:
                ip_attempts.pop()
                if not ip_attempts:
                    self._entries.pop(ip_key, None)

    async def reset(self) -> None:
        """Clear process-local state; used when isolating application test cases."""
        async with self._lock:
            self._entries.clear()

    def _remove_stale_entries(self, cutoff: float) -> None:
        stale_keys = [
            key for key, attempts in self._entries.items() if not attempts or attempts[-1] <= cutoff
        ]
        for key in stale_keys:
            self._entries.pop(key, None)


login_rate_limiter = LoginRateLimiter(
    attempts=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
    window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)
registration_rate_limiter = LoginRateLimiter(
    attempts=settings.REGISTRATION_RATE_LIMIT_ATTEMPTS,
    window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)


async def authenticate_user(db: AsyncSession, identifier: str, password: str) -> User | None:
    """使用用户仓储的唯一认证实现验证凭据。"""
    return await user_crud.authenticate(db, identifier, password)


async def create_login_session(db: AsyncSession, user: User) -> SessionTokens:
    """为成功登录创建可撤销 refresh session。"""
    locked_user = await _get_user_for_update(db, user.id)
    if (
        locked_user is None
        or locked_user.is_deleted
        or not locked_user.is_active
        or locked_user.token_version != user.token_version
    ):
        raise RefreshTokenError("用户状态已变化，无法创建登录会话")
    user = locked_user
    refresh = issue_refresh_token(str(user.id), user.token_version)
    family = RefreshSessionFamily(
        id=refresh.family_id,
        user_id=user.id,
        token_version=user.token_version,
        expires_at=refresh.expires_at,
    )
    db.add(family)
    # The models intentionally have no lazy relationship. Flush the FK parent
    # first so mapper ordering is deterministic on PostgreSQL.
    await db.flush()
    db.add(
        RefreshSession(
            user_id=user.id,
            jti=refresh.jti,
            family_id=refresh.family_id,
            token_hash=hash_refresh_token(refresh.token),
            token_version=user.token_version,
            expires_at=refresh.expires_at,
        )
    )
    await db.flush()
    return SessionTokens(
        access_token=create_access_token(
            str(user.id),
            user.token_version,
            session_id=refresh.family_id,
        ),
        refresh_token=refresh.token,
        family_id=refresh.family_id,
    )


async def rotate_refresh_session(
    db: AsyncSession,
    raw_token: str,
    claims: TokenPayload,
) -> SessionTokens:
    """原子消费一个 refresh token 并创建同 family 的下一代 token。"""
    if claims.type != "refresh":
        raise RefreshTokenError("refresh token 类型或会话标识无效")

    user = await _get_user_for_update(db, claims.user_id)
    if user is None:
        raise RefreshTokenError("用户不存在")

    family = await _get_family_for_update(db, claims.sid)
    if family is None:
        raise RefreshTokenError("refresh session family 不存在")

    now = datetime.now(UTC)
    family_matches = family.user_id == claims.user_id and family.token_version == claims.ver
    if family.revoked_at is not None or not family_matches:
        _revoke_locked_family(family, now=now, reason="refresh_replay")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "检测到 refresh token family 重放",
            user_id=family.user_id,
        )
    if _as_utc(family.expires_at) <= now:
        _revoke_locked_family(family, now=now, reason="expired")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "refresh session family 已过期",
            user_id=family.user_id,
        )

    session_stmt = select(RefreshSession).where(RefreshSession.jti == claims.jti).with_for_update()
    session = (await db.execute(session_stmt)).scalar_one_or_none()
    if session is None:
        _revoke_locked_family(family, now=now, reason="refresh_replay")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "refresh session 不存在",
            user_id=family.user_id,
        )

    metadata_matches = (
        session.user_id == claims.user_id
        and session.family_id == claims.sid
        and session.token_version == claims.ver
        and refresh_token_hash_matches(raw_token, session.token_hash)
    )
    if session.revoked_at is not None or not metadata_matches:
        _revoke_locked_family(family, now=now, reason="refresh_replay")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "检测到 refresh token 重放",
            user_id=session.user_id,
        )

    expires_at = _as_utc(session.expires_at)
    if expires_at <= now:
        session.revoked_at = now
        session.revoked_reason = "expired"
        _revoke_locked_family(family, now=now, reason="expired")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "refresh session 已过期",
            user_id=session.user_id,
        )

    if user.is_deleted or not user.is_active or user.token_version != claims.ver:
        _revoke_locked_family(family, now=now, reason="user_invalidated")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "用户会话已失效",
            user_id=session.user_id,
        )

    refresh = issue_refresh_token(
        str(user.id),
        user.token_version,
        family_id=session.family_id,
    )
    session.revoked_at = now
    session.revoked_reason = "rotated"
    session.replaced_by_jti = refresh.jti
    session.last_used_at = now
    family.expires_at = refresh.expires_at
    family.last_used_at = now
    db.add(
        RefreshSession(
            user_id=user.id,
            jti=refresh.jti,
            family_id=refresh.family_id,
            token_hash=hash_refresh_token(refresh.token),
            token_version=user.token_version,
            expires_at=refresh.expires_at,
        )
    )
    await db.flush()
    return SessionTokens(
        access_token=create_access_token(
            str(user.id),
            user.token_version,
            session_id=refresh.family_id,
        ),
        refresh_token=refresh.token,
        family_id=refresh.family_id,
    )


async def is_session_family_active(
    db: AsyncSession,
    *,
    user_id: int,
    family_id: str,
    token_version: int,
) -> bool:
    """验证 access token 对应的会话 family 仍有有效 refresh session。"""
    stmt = (
        select(RefreshSessionFamily.id)
        .where(
            RefreshSessionFamily.id == family_id,
            RefreshSessionFamily.user_id == user_id,
            RefreshSessionFamily.token_version == token_version,
            RefreshSessionFamily.revoked_at.is_(None),
            RefreshSessionFamily.expires_at > datetime.now(UTC),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def get_active_session_user(
    db: AsyncSession,
    *,
    user_id: int,
    family_id: str,
    token_version: int,
) -> User | None:
    """Validate the account and access-token family in one round trip."""
    stmt = (
        select(User)
        .join(RefreshSessionFamily, RefreshSessionFamily.user_id == User.id)
        .where(
            User.id == user_id,
            User.is_deleted.is_(False),
            User.is_active.is_(True),
            User.token_version == token_version,
            RefreshSessionFamily.id == family_id,
            RefreshSessionFamily.token_version == token_version,
            RefreshSessionFamily.revoked_at.is_(None),
            RefreshSessionFamily.expires_at > datetime.now(UTC),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def revoke_refresh_session(
    db: AsyncSession,
    raw_token: str,
    claims: TokenPayload,
    *,
    reason: str = "logout",
) -> int | None:
    """验证 refresh token 后撤销其 family；无匹配会话时保持幂等。"""
    if claims.type != "refresh":
        return None

    user = await _get_user_for_update(db, claims.user_id)
    if user is None:
        return None

    family = await _get_family_for_update(db, claims.sid)
    if family is None or family.revoked_at is not None:
        return None

    stmt = select(RefreshSession).where(RefreshSession.jti == claims.jti).with_for_update()
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        _revoke_locked_family(family, now=datetime.now(UTC), reason="logout_mismatch")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "logout refresh session 不存在",
            user_id=family.user_id,
        )
    if (
        session.user_id != claims.user_id
        or session.family_id != claims.sid
        or family.user_id != claims.user_id
        or family.token_version != claims.ver
        or not refresh_token_hash_matches(raw_token, session.token_hash)
    ):
        _revoke_locked_family(family, now=datetime.now(UTC), reason="logout_mismatch")
        await db.flush()
        raise RefreshSessionCompromisedError(
            "logout refresh token 元数据不匹配",
            user_id=family.user_id,
        )

    _revoke_locked_family(family, now=datetime.now(UTC), reason=reason)
    await db.flush()
    return session.user_id


async def revoke_all_refresh_sessions(
    db: AsyncSession,
    user_id: int,
    *,
    reason: str = "user_security_change",
) -> None:
    """Lock the user first, then revoke every family in the shared lock order."""
    # Persist caller-side token_version/state changes before populate_existing
    # reloads the lock row (AsyncSession autoflush is intentionally disabled).
    await db.flush()
    if await _get_user_for_update(db, user_id) is None:
        return
    await db.execute(
        update(RefreshSessionFamily)
        .where(
            RefreshSessionFamily.user_id == user_id,
            RefreshSessionFamily.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
    )
    await db.flush()


async def _get_user_for_update(db: AsyncSession, user_id: int) -> User | None:
    """First lock in every refresh-family mutation: user → family → token."""
    stmt = (
        select(User)
        .where(User.id == user_id)
        # PostgreSQL FOR NO KEY UPDATE serializes user mutations while staying
        # compatible with audit/session FK KEY SHARE checks.
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_family_for_update(
    db: AsyncSession,
    family_id: str,
) -> RefreshSessionFamily | None:
    """Use one fixed row as the serialization point for all family writes."""
    stmt = (
        select(RefreshSessionFamily)
        .where(RefreshSessionFamily.id == family_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _revoke_locked_family(
    family: RefreshSessionFamily,
    *,
    now: datetime,
    reason: str,
) -> None:
    """Revoke a family already protected by its row lock."""
    if family.revoked_at is None:
        family.revoked_at = now
        family.revoked_reason = reason


def _as_utc(value: datetime) -> datetime:
    """兼容测试数据库返回的 naive datetime。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
