"""Authenticated profile and password endpoints."""

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_refresh_cookie
from app.core.deps import CurrentAudit, CurrentUser, DbSession
from app.core.errors import BadRequestError
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.common import ResponseEnvelope, success_response
from app.schemas.user import ChangePasswordRequest, CurrentUserResponse, UpdateProfileRequest
from app.services import users as users_service
from app.services.auth import revoke_all_refresh_sessions

router = APIRouter()


async def _current_user_payload(db: AsyncSession, user: User) -> CurrentUserResponse:
    """Serialize an own-profile response together with its permission codes."""
    payload = CurrentUserResponse.model_validate(user)
    return payload.model_copy(
        update={"permissions": await user_crud.get_permission_codes(db, user.id)}
    )


@router.get("")
async def get_profile(db: DbSession, current_user: CurrentUser) -> ResponseEnvelope[CurrentUserResponse]:
    """Return the current user with active roles and effective permission codes."""
    user = await user_crud.get_with_roles(db, current_user.id)
    if user is None:  # defensive against a concurrent deletion
        raise HTTPException(status_code=401, detail="用户不存在")
    return success_response(await _current_user_payload(db, user))


@router.patch("")
@router.put("", deprecated=True)
async def update_profile(
    profile_in: UpdateProfileRequest,
    audit: CurrentAudit,
) -> ResponseEnvelope[CurrentUserResponse]:
    """Partially update the current user's mutable profile fields."""
    user = await users_service.update_profile(audit.db, audit.actor, profile_in)
    await audit.commit("update_profile", f"user:{audit.actor.id}", "更新个人信息")
    return success_response(await _current_user_payload(audit.db, user), message="更新成功")


@router.put("/password")
async def change_password(
    password_in: ChangePasswordRequest,
    response: Response,
    audit: CurrentAudit,
) -> ResponseEnvelope[None]:
    """Verify/change the password and revoke every prior session."""
    changed = await users_service.change_password(
        audit.db,
        audit.actor.id,
        password_in.old_password,
        password_in.new_password,
    )
    if not changed:
        raise BadRequestError("旧密码不正确")

    await revoke_all_refresh_sessions(audit.db, audit.actor.id, reason="password_changed")
    await audit.commit(
        "change_password",
        f"user:{audit.actor.id}",
        "修改密码并撤销全部登录会话",
    )
    clear_refresh_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return success_response(None, message="密码修改成功，请重新登录")
