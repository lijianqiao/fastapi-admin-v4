"""User-management endpoints: HTTP adaptation only; rules live in app.services.users."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.v1.recycle_bin import build_recycle_bin_router
from app.core.deps import Audit, DbSession, PageQuery, audited, require_permission
from app.core.errors import NotFoundError
from app.core.permissions import Perm
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.common import PaginatedData, ResponseEnvelope, paginated_response, success_response
from app.schemas.user import (
    AdminResetPasswordRequest,
    AssignRolesRequest,
    UserCreate,
    UserUpdate,
    UserWithRoles,
)
from app.services import users as users_service
from app.services.guards import guard_user_recycle

router = APIRouter()
router.include_router(
    build_recycle_bin_router(
        crud=user_crud,
        list_schema=UserWithRoles,
        detail_schema=UserWithRoles,
        permission=Perm.USER_DELETE,
        resource="user",
        label="用户",
        describe=lambda user: user.username,
        before_restore=guard_user_recycle,
        before_purge=guard_user_recycle,
    )
)

UserId = Annotated[int, Path(gt=0)]


@router.get("")
async def list_users(
    page: PageQuery,
    db: DbSession,
    _: Annotated[User, Depends(require_permission(Perm.USER_READ))],
    is_active: Annotated[bool | None, Query()] = None,
    role_id: Annotated[int | None, Query(gt=0)] = None,
) -> ResponseEnvelope[PaginatedData[UserWithRoles]]:
    """Return a stable, filtered page of users with active roles."""
    users, total = await user_crud.get_multi_filtered(
        db,
        search=page.search,
        is_active=is_active,
        role_id=role_id,
        skip=page.skip,
        limit=page.page_size,
    )
    items = [UserWithRoles.model_validate(user) for user in users]
    return paginated_response(items, total, page.page, page.page_size)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    audit: Annotated[Audit, Depends(audited(Perm.USER_CREATE))],
) -> ResponseEnvelope[UserWithRoles]:
    """Create an unprivileged user; role assignment has its own permission."""
    user = await users_service.create_user(audit.db, user_in)
    await audit.commit("create_user", f"user:{user.id}", f"创建用户: {user.username}")
    return success_response(
        UserWithRoles.model_validate(user),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.get("/{user_id}")
async def get_user(
    user_id: UserId,
    db: DbSession,
    _: Annotated[User, Depends(require_permission(Perm.USER_READ))],
) -> ResponseEnvelope[UserWithRoles]:
    """Return one active user and their active roles."""
    user = await user_crud.get_with_roles(db, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    return success_response(UserWithRoles.model_validate(user))


@router.patch("/{user_id}")
@router.put("/{user_id}", deprecated=True)
async def update_user(
    user_id: UserId,
    user_in: UserUpdate,
    audit: Annotated[Audit, Depends(audited(Perm.USER_UPDATE))],
) -> ResponseEnvelope[UserWithRoles]:
    """Partially update a user and revoke sessions when disabling them."""
    user = await users_service.update_user(audit.db, audit.actor, user_id, user_in)
    await audit.commit("update_user", f"user:{user_id}", f"更新用户信息: {user.username}")
    return success_response(UserWithRoles.model_validate(user), message="更新成功")


@router.delete("/{user_id}")
async def delete_user(
    user_id: UserId,
    audit: Annotated[Audit, Depends(audited(Perm.USER_DELETE))],
) -> ResponseEnvelope[None]:
    """Soft-delete a user and revoke all of their sessions atomically."""
    user = await users_service.delete_user(audit.db, audit.actor, user_id)
    await audit.commit("delete_user", f"user:{user_id}", f"删除用户: {user.username}")
    return success_response(None, message="删除成功")


@router.put("/{user_id}/password")
async def reset_password(
    user_id: UserId,
    password_in: AdminResetPasswordRequest,
    audit: Annotated[Audit, Depends(audited(Perm.USER_RESET_PASSWORD))],
) -> ResponseEnvelope[None]:
    """Administrator sets a new password for another user, revoking their sessions."""
    await users_service.reset_password(audit.db, audit.actor, user_id, password_in.new_password)
    await audit.commit(
        "reset_password",
        f"user:{user_id}",
        "管理员重置用户密码并撤销其全部登录会话",
    )
    return success_response(None, message="密码重置成功")


@router.put("/{user_id}/roles")
async def assign_roles(
    user_id: UserId,
    roles_in: AssignRolesRequest,
    audit: Annotated[Audit, Depends(audited(Perm.USER_ASSIGN))],
) -> ResponseEnvelope[UserWithRoles]:
    """Replace a user's roles after validating the complete ID set."""
    user = await users_service.assign_roles(audit.db, audit.actor, user_id, roles_in.role_ids)
    await audit.commit("assign_roles", f"user:{user_id}", f"分配角色: {roles_in.role_ids}")
    return success_response(UserWithRoles.model_validate(user), message="角色分配成功")
