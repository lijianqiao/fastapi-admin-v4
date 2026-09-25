"""认证、授权与请求上下文依赖。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Annotated, NoReturn

import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.dependencies.models import Dependant
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Perm
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.services.auth import get_active_session_user, get_authorized_session_user
from app.utils.audit import log_audit

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _raise_unauthorized(message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_access_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenPayload:
    """验证 Bearer access token 并返回强类型载荷。"""
    if credentials is None:
        _raise_unauthorized("未提供认证凭据")

    try:
        payload = decode_token(credentials.credentials)
        if payload.type != "access":
            _raise_unauthorized("Token 类型错误")
        _ = payload.user_id
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return payload


AccessTokenPayload = Annotated[TokenPayload, Depends(get_access_token_payload)]


async def get_current_user(payload: AccessTokenPayload, db: DbSession) -> User:
    """Validate the user and access-token family in one database query."""
    user = await get_active_session_user(
        db,
        user_id=payload.user_id,
        family_id=payload.sid,
        token_version=payload.ver,
    )
    if user is None:
        _raise_unauthorized("Token 已撤销或用户不可用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class PermissionChecker:
    """声明式权限依赖：会话校验与权限判定合并为一次查询。

    以可调用实例实现，``code`` 可被路由自省（一致性测试、OpenAPI 标注）读取。
    """

    def __init__(self, code: Perm) -> None:
        self.code = code

    async def __call__(self, payload: AccessTokenPayload, db: DbSession) -> User:
        authorized = await get_authorized_session_user(
            db,
            user_id=payload.user_id,
            family_id=payload.sid,
            token_version=payload.ver,
            permission_code=self.code,
        )
        if authorized is None:
            _raise_unauthorized("Token 已撤销或用户不可用")
        if not authorized.user.is_superuser and not authorized.has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权限执行此操作（需要权限：{self.code}）",
            )
        return authorized.user


def require_permission(code: Perm) -> PermissionChecker:
    """创建声明式权限校验依赖。"""
    return PermissionChecker(code)


def collect_required_permissions(dependant: Dependant) -> set[Perm]:
    """Walk a route's dependency tree and return every permission it requires."""
    found: set[Perm] = set()
    for dependency in dependant.dependencies:
        if isinstance(dependency.call, PermissionChecker):
            found.add(dependency.call.code)
        found |= collect_required_permissions(dependency)
    return found


def get_client_ip(request: Request) -> str:
    """Return the normalized peer set by the single trusted-proxy middleware."""
    if request.client is None:
        return "unknown"

    try:
        return ip_address(request.client.host).compressed
    except ValueError:
        return "unknown"


def get_refresh_token_from_request(request: Request) -> str | None:
    """从受限 httpOnly Cookie 读取 refresh token。"""
    return request.cookies.get("refresh_token")


@dataclass(slots=True)
class Audit:
    """Audit context of the current request: shared session, actor and client IP."""

    db: AsyncSession
    actor: User
    ip: str

    async def commit(self, action: str, target: str, detail: str = "") -> None:
        """Stage the audit record and commit it together with the business change."""
        await log_audit(
            self.db,
            user_id=self.actor.id,
            action=action,
            target=target,
            detail=detail,
            ip=self.ip,
            username=self.actor.username,
        )
        await self.db.commit()


def audited(code: Perm) -> Callable[..., Awaitable[Audit]]:
    """Dependency factory: require ``code`` and expose an ``Audit`` for the endpoint."""
    checker = require_permission(code)

    async def dependency(
        request: Request,
        db: DbSession,
        actor: Annotated[User, Depends(checker)],
    ) -> Audit:
        return Audit(db=db, actor=actor, ip=get_client_ip(request))

    return dependency


async def get_current_audit(request: Request, db: DbSession, actor: CurrentUser) -> Audit:
    """Audit context for endpoints that only require an authenticated user."""
    return Audit(db=db, actor=actor, ip=get_client_ip(request))


CurrentAudit = Annotated[Audit, Depends(get_current_audit)]


@dataclass(frozen=True, slots=True)
class PageParams:
    """Validated page request."""

    page: int
    page_size: int
    search: str | None

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


def page_query(*, default_size: int = 10, max_size: int = 100) -> Callable[..., PageParams]:
    """Build a pagination dependency with per-endpoint size limits."""

    def dependency(
        page: Annotated[int, Query(ge=1, le=100_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=max_size)] = default_size,
        search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ) -> PageParams:
        return PageParams(page=page, page_size=page_size, search=search)

    return dependency


PageQuery = Annotated[PageParams, Depends(page_query())]
