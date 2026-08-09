"""Authenticated profile and password endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_refresh_cookie
from app.core.database import get_db
from app.core.deps import get_client_ip, get_current_user
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.common import ResponseEnvelope, success_response
from app.schemas.user import (
    ChangePasswordRequest,
    CurrentUserResponse,
    UpdateProfileRequest,
)
from app.services.auth import revoke_all_refresh_sessions
from app.utils.audit import log_audit

router = APIRouter()


async def _current_user_payload(db: AsyncSession, user: User) -> CurrentUserResponse:
    """Serialize an own-profile response together with its permission codes."""
    payload = CurrentUserResponse.model_validate(user)
    return payload.model_copy(
        update={"permissions": await user_crud.get_permission_codes(db, user.id)}
    )


@router.get("", response_model=ResponseEnvelope[CurrentUserResponse])
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[CurrentUserResponse]:
    """Return the current user with active roles and effective permission codes."""
    user = await user_crud.get_with_roles(db, current_user.id)
    if user is None:  # defensive against a concurrent deletion
        raise HTTPException(status_code=401, detail="用户不存在")
    return success_response(await _current_user_payload(db, user))


@router.patch("", response_model=ResponseEnvelope[CurrentUserResponse])
@router.put("", response_model=ResponseEnvelope[CurrentUserResponse], deprecated=True)
async def update_profile(
    profile_in: UpdateProfileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[CurrentUserResponse]:
    """Partially update the current user's mutable profile fields."""
    if profile_in.email is not None and str(profile_in.email) != current_user.email:
        existing = await user_crud.get_by_email_any(db, str(profile_in.email))
        if existing is not None and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="邮箱已被占用（包括已删除账户）")

    user = await user_crud.update(
        db,
        current_user.id,
        profile_in.model_dump(exclude_unset=True),
    )
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="update_profile",
        target=f"user:{current_user.id}",
        detail="更新个人信息",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(await _current_user_payload(db, user), message="更新成功")


@router.put("/password", response_model=ResponseEnvelope[None])
async def change_password(
    password_in: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[None]:
    """Atomically verify/change the password and revoke every prior session."""
    changed = await user_crud.change_password(
        db,
        current_user.id,
        password_in.old_password,
        password_in.new_password,
    )
    if not changed:
        raise HTTPException(status_code=400, detail="旧密码不正确")

    await revoke_all_refresh_sessions(db, current_user.id, reason="password_changed")
    await log_audit(
        db,
        user_id=current_user.id,
        action="change_password",
        target=f"user:{current_user.id}",
        detail="修改密码并撤销全部登录会话",
        ip=get_client_ip(request),
    )
    await db.commit()
    clear_refresh_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return success_response(None, message="密码修改成功，请重新登录")
