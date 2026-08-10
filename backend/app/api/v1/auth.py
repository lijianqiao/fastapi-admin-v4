"""认证路由：注册、登录、refresh token 轮换与退出。"""

from urllib.parse import urlsplit

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import clear_refresh_cookie, set_refresh_cookie
from app.core.database import get_db
from app.core.deps import get_client_ip, get_refresh_token_from_request
from app.core.security import decode_token, hash_password_async
from app.crud.user import user_crud
from app.schemas.auth import TokenResponse, UserLogin, UserRegister
from app.schemas.common import ResponseEnvelope, success_response
from app.schemas.user import UserResponse
from app.services.auth import (
    RefreshSessionCompromisedError,
    RefreshTokenError,
    authenticate_user,
    create_login_session,
    login_rate_limiter,
    registration_rate_limiter,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.utils.audit import log_audit

router = APIRouter()


def _error_response(
    status_code: int,
    message: str,
    *,
    clear_cookie: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """返回 HTTP 状态与响应信封一致的认证错误。"""
    response = JSONResponse(
        status_code=status_code,
        headers=headers,
        content={"code": status_code, "data": None, "message": message},
    )
    response.headers["Cache-Control"] = "no-store"
    if clear_cookie:
        clear_refresh_cookie(response)
    return response


def _require_trusted_origin(request: Request) -> None:
    """Reject browser state-changing requests from untrusted origins.

    Fails closed: at least one of Origin, Referer, or a same-origin
    Sec-Fetch-Site signal must positively prove the request originated from
    this application. A request carrying none of these signals is rejected
    rather than assumed safe — otherwise a browser that omits Fetch Metadata
    headers (pre-2021) together with a stripped Referer would sail through.
    """
    fetch_site = request.headers.get("Sec-Fetch-Site", "").casefold()
    if fetch_site == "cross-site":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")

    allowed_origins = set(settings.cors_origins_list)
    origin = request.headers.get("Origin")
    if origin is not None:
        if origin not in allowed_origins:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")
        return

    referer = request.headers.get("Referer")
    if referer is not None:
        parsed_referer = urlsplit(referer)
        referer_origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"
        if (
            parsed_referer.scheme not in {"http", "https"}
            or not parsed_referer.netloc
            or referer_origin not in allowed_origins
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")
        return

    if fetch_site != "same-origin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")


@router.post(
    "/register",
    response_model=ResponseEnvelope[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_in: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[UserResponse] | JSONResponse:
    """在显式开启自助注册时创建普通用户。"""
    if not settings.REGISTRATION_ENABLED:
        return _error_response(status.HTTP_404_NOT_FOUND, "接口不存在")
    _require_trusted_origin(request)
    client_ip = get_client_ip(request)
    retry_after = await registration_rate_limiter.hit(client_ip, "registration")
    if retry_after is not None:
        return _error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "注册尝试过于频繁，请稍后重试",
            headers={"Retry-After": str(retry_after)},
        )

    username_exists = await user_crud.get_by_username_any(db, user_in.username) is not None
    email_exists = await user_crud.get_by_email_any(db, str(user_in.email)) is not None
    # Do not retain a database connection while Argon2id runs.
    await db.rollback()
    if username_exists or email_exists:
        # Match the KDF cost of a successful registration and avoid revealing
        # which identifier already exists through content or coarse timing.
        await hash_password_async(user_in.password)
        return _error_response(status.HTTP_409_CONFLICT, "用户名或邮箱已被使用")

    try:
        user = await user_crud.create(
            db,
            {
                "username": user_in.username,
                "email": str(user_in.email),
                "password": user_in.password,
                "nickname": user_in.username,
            },
        )
        await log_audit(
            db,
            user_id=user.id,
            action="register",
            target=f"user:{user.id}",
            detail="用户自助注册",
            ip=client_ip,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _error_response(status.HTTP_409_CONFLICT, "用户名或邮箱已被使用")

    return success_response(
        UserResponse.model_validate(user),
        message="注册成功",
        code=status.HTTP_201_CREATED,
    )


@router.post("/login", response_model=ResponseEnvelope[TokenResponse])
async def login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> ResponseEnvelope[TokenResponse] | JSONResponse:
    """验证凭据并签发短期 access token 与持久化 refresh session。"""
    _require_trusted_origin(request)
    try:
        credentials = UserLogin.model_validate(
            {"username": form_data.username, "password": form_data.password}
        )
    except ValidationError:
        return _error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "登录参数无效")

    client_ip = get_client_ip(request)
    retry_after = await login_rate_limiter.hit(client_ip, credentials.username)
    if retry_after is not None:
        return _error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "登录尝试过于频繁，请稍后重试",
            headers={"Retry-After": str(retry_after)},
        )

    user = await authenticate_user(db, credentials.username, credentials.password)
    if user is None:
        await log_audit(
            db,
            user_id=None,
            action="login_failed",
            target="auth",
            detail="凭据验证失败",
            ip=client_ip,
        )
        await db.commit()
        return _error_response(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    await login_rate_limiter.clear(client_ip, credentials.username)
    try:
        tokens = await create_login_session(db, user)
    except RefreshTokenError:
        # Narrow race: the account was disabled/deleted or its token version
        # changed between authenticate_user() and here.
        return _error_response(status.HTTP_401_UNAUTHORIZED, "用户状态已变化，请重试")
    await log_audit(
        db,
        user_id=user.id,
        action="login",
        target="auth",
        detail="用户登录",
        ip=client_ip,
    )
    await db.commit()

    set_refresh_cookie(response, tokens.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    token_data = TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return success_response(token_data, message="登录成功")


@router.post("/refresh", response_model=ResponseEnvelope[TokenResponse])
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[TokenResponse] | JSONResponse:
    """原子消费 refresh token，并轮换同一 session family 的下一枚 token。"""
    _require_trusted_origin(request)
    raw_token = get_refresh_token_from_request(request)
    if raw_token is None:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "未找到 refresh token")

    try:
        claims = decode_token(raw_token)
        _ = claims.user_id
        tokens = await rotate_refresh_session(db, raw_token, claims)
        await db.commit()
    except RefreshSessionCompromisedError as exc:
        await log_audit(
            db,
            user_id=exc.user_id,
            action="refresh_rejected",
            target="auth",
            detail="refresh token 重放或会话失效",
            ip=get_client_ip(request),
        )
        # 服务已撤销整个 family；必须在返回 401 前持久化撤销与安全审计。
        await db.commit()
        return _error_response(
            status.HTTP_401_UNAUTHORIZED,
            "refresh token 无效或已过期",
            clear_cookie=True,
        )
    except jwt.InvalidTokenError, ValueError, RefreshTokenError:
        await db.rollback()
        return _error_response(
            status.HTTP_401_UNAUTHORIZED,
            "refresh token 无效或已过期",
            clear_cookie=True,
        )

    set_refresh_cookie(response, tokens.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    token_data = TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return success_response(token_data, message="刷新成功")


@router.post("/logout", response_model=ResponseEnvelope[None])
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ResponseEnvelope[None]:
    """撤销当前 refresh session family；无效或缺失 Cookie 时保持幂等。"""
    _require_trusted_origin(request)
    raw_token = get_refresh_token_from_request(request)
    if raw_token is not None:
        try:
            claims = decode_token(raw_token)
            user_id = await revoke_refresh_session(db, raw_token, claims)
            if user_id is not None:
                await log_audit(
                    db,
                    user_id=user_id,
                    action="logout",
                    target="auth",
                    detail="用户退出",
                    ip=get_client_ip(request),
                )
                await db.commit()
            else:
                await db.rollback()
        except RefreshSessionCompromisedError as exc:
            await log_audit(
                db,
                user_id=exc.user_id,
                action="logout_rejected",
                target="auth",
                detail="logout token 不匹配，已撤销会话族",
                ip=get_client_ip(request),
            )
            await db.commit()
        except jwt.InvalidTokenError, ValueError:
            await db.rollback()

    clear_refresh_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return success_response(None, message="退出成功")
