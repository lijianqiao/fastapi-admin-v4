"""认证、授权与请求上下文依赖。"""

from ipaddress import ip_address
from typing import NoReturn

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Perm
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.services.auth import get_active_session_user, get_authorized_session_user

bearer_scheme = HTTPBearer(auto_error=False)


def _raise_unauthorized(message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_access_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
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


async def get_current_user(
    payload: TokenPayload = Depends(get_access_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
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


class PermissionChecker:
    """声明式权限依赖：会话校验与权限判定合并为一次查询。

    以可调用实例实现，``code`` 可被路由自省（一致性测试、OpenAPI 标注）读取。
    """

    def __init__(self, code: Perm) -> None:
        self.code = code

    async def __call__(
        self,
        payload: TokenPayload = Depends(get_access_token_payload),
        db: AsyncSession = Depends(get_db),
    ) -> User:
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
