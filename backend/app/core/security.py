"""密码哈希、JWT 签发与安全令牌工具。"""

import asyncio
import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from secrets import token_urlsafe
from uuid import uuid4

import bcrypt
import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.auth import TokenPayload

# 新密码使用 Argon2id；BcryptHasher 仅用于验证旧数据并触发渐进升级。
ARGON2_HASH = PasswordHash((Argon2Hasher(),))
BCRYPT_HASH = PasswordHash((BcryptHasher(),))
DUMMY_PASSWORD = token_urlsafe(32)
PASSWORD_HASH_SEMAPHORE = asyncio.Semaphore(settings.PASSWORD_HASH_MAX_CONCURRENCY)


@lru_cache(maxsize=1)
def _dummy_hashes() -> tuple[str, str]:
    """Build the timing-equalization hashes on first use, not at import time.

    Both KDFs together cost far more than a module import should, and only the
    credential paths ever need them.
    """
    return ARGON2_HASH.hash(DUMMY_PASSWORD), BCRYPT_HASH.hash(DUMMY_PASSWORD)


class PasswordHashOverloadedError(RuntimeError):
    """Password worker capacity was unavailable within the bounded wait."""


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    """密码验证结果及可选的新哈希。"""

    valid: bool
    updated_hash: str | None = None


@dataclass(frozen=True, slots=True)
class IssuedRefreshToken:
    """已签发 refresh token 及持久化所需元数据。"""

    token: str
    jti: str
    family_id: str
    expires_at: datetime


def hash_password(password: str) -> str:
    """同步生成 Argon2id 哈希；异步请求路径应使用 ``hash_password_async``。"""
    return ARGON2_HASH.hash(password)


async def hash_password_async(password: str) -> str:
    """在线程池生成密码哈希，避免阻塞事件循环。"""
    return await _run_password_work(hash_password, password)


async def _run_password_work[**P, R](
    func: Callable[P, R],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Run expensive password work with bounded concurrency and queue time."""
    try:
        async with asyncio.timeout(settings.PASSWORD_HASH_QUEUE_TIMEOUT_SECONDS):
            await PASSWORD_HASH_SEMAPHORE.acquire()
    except TimeoutError as exc:
        raise PasswordHashOverloadedError("密码服务繁忙") from exc

    try:
        work = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
    except BaseException:
        PASSWORD_HASH_SEMAPHORE.release()
        raise

    # A thread-pool call cannot be cancelled once running. Keep the permit until
    # the actual KDF finishes even if the HTTP request disconnects meanwhile.
    work.add_done_callback(lambda _: PASSWORD_HASH_SEMAPHORE.release())
    return await asyncio.shield(work)


def _burn_both_dummy_hashes() -> None:
    """Spend the cost of both supported algorithms for unknown/invalid hashes."""
    dummy_argon2_hash, dummy_bcrypt_hash = _dummy_hashes()
    ARGON2_HASH.verify(DUMMY_PASSWORD, dummy_argon2_hash)
    BCRYPT_HASH.verify(DUMMY_PASSWORD, dummy_bcrypt_hash)


def _verify_and_update_password(
    password: str,
    hashed_password: str | None,
) -> PasswordVerification:
    if hashed_password is None:
        _burn_both_dummy_hashes()
        return PasswordVerification(valid=False)

    if hashed_password.startswith(("$2a$", "$2b$", "$2x$", "$2y$")):
        try:
            # bcrypt <=4 silently truncated at 72 bytes. Reproduce that legacy
            # behavior once so long-password accounts can log in and migrate.
            valid = bcrypt.checkpw(
                password.encode("utf-8")[:72],
                hashed_password.encode("ascii"),
            )
        except (UnicodeEncodeError, ValueError):
            _burn_both_dummy_hashes()
            return PasswordVerification(valid=False)

        if valid:
            return PasswordVerification(valid=True, updated_hash=ARGON2_HASH.hash(password))
        ARGON2_HASH.verify(DUMMY_PASSWORD, _dummy_hashes()[0])
        return PasswordVerification(valid=False)

    if not hashed_password.startswith("$argon2"):
        _burn_both_dummy_hashes()
        return PasswordVerification(valid=False)

    try:
        valid, updated_hash = ARGON2_HASH.verify_and_update(password, hashed_password)
    except (UnknownHashError, ValueError):
        _burn_both_dummy_hashes()
        return PasswordVerification(valid=False)

    # Every valid Argon2 path also pays a bcrypt cost. Together with the
    # mirrored bcrypt branch, this keeps account/hash types hard to time.
    BCRYPT_HASH.verify(DUMMY_PASSWORD, _dummy_hashes()[1])
    return PasswordVerification(valid=valid, updated_hash=updated_hash)


async def verify_and_update_password(
    password: str,
    hashed_password: str | None,
) -> PasswordVerification:
    """验证密码，并在旧 bcrypt 哈希成功时返回 Argon2id 新哈希。

    不存在的用户也执行两种算法的固定 dummy hash，以缩小用户名枚举的时序差异。
    """
    return await _run_password_work(_verify_and_update_password, password, hashed_password)


def _base_claims(
    subject: str,
    token_type: str,
    token_version: int,
    expires_at: datetime,
    *,
    jti: str,
    session_id: str,
) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": subject,
        "exp": expires_at,
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": jti,
        "type": token_type,
        "ver": token_version,
    }
    claims["sid"] = session_id
    return claims


def create_access_token(
    subject: str,
    token_version: int,
    session_id: str,
) -> str:
    """签发短期 access token。"""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = _base_claims(
        subject,
        "access",
        token_version,
        expires_at,
        jti=uuid4().hex,
        session_id=session_id,
    )
    return jwt.encode(claims, settings.secret_key, algorithm=settings.ALGORITHM)


def issue_refresh_token(
    subject: str,
    token_version: int = 0,
    *,
    family_id: str | None = None,
) -> IssuedRefreshToken:
    """签发带唯一 jti 和会话 family 的 refresh token。"""
    issued_family_id = family_id or uuid4().hex
    jti = uuid4().hex
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    claims = _base_claims(
        subject,
        "refresh",
        token_version,
        expires_at,
        jti=jti,
        session_id=issued_family_id,
    )
    token = jwt.encode(claims, settings.secret_key, algorithm=settings.ALGORITHM)
    return IssuedRefreshToken(
        token=token,
        jti=jti,
        family_id=issued_family_id,
        expires_at=expires_at,
    )


def decode_token(token: str) -> TokenPayload:
    """验证签名、标准声明与强类型载荷。"""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={
            "require": ["sub", "exp", "iat", "iss", "aud", "jti", "type", "ver"],
        },
    )
    try:
        return TokenPayload.model_validate(payload)
    except ValidationError as exc:
        raise jwt.InvalidTokenError("Token 负载无效") from exc


def hash_refresh_token(token: str) -> str:
    """使用服务端密钥生成 refresh token 的不可逆持久化摘要。"""
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def refresh_token_hash_matches(token: str, expected_hash: str) -> bool:
    """常量时间比较 refresh token 摘要。"""
    return hmac.compare_digest(hash_refresh_token(token), expected_hash)
