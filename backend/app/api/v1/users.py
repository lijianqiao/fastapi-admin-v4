"""Asynchronous user-management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_client_ip, require_permission
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
from app.services.auth import revoke_all_refresh_sessions
from app.utils.audit import log_audit

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[UserWithRoles]],
)
async def list_users(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    is_active: bool | None = Query(default=None),
    role_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user:read")),
) -> ResponseEnvelope[PaginatedData[UserWithRoles]]:
    """Return a stable, filtered page of users with active roles."""
    users, total = await user_crud.get_multi_filtered(
        db,
        search=search,
        is_active=is_active,
        role_id=role_id,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [UserWithRoles.model_validate(user) for user in users]
    return paginated_response(items, total, page, page_size)


@router.post(
    "",
    response_model=ResponseEnvelope[UserWithRoles],
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:create")),
) -> ResponseEnvelope[UserWithRoles]:
    """Create an unprivileged user; role assignment has its own permission."""
    if await user_crud.get_by_username_any(db, user_in.username):
        raise HTTPException(status_code=409, detail="用户名已被占用（包括已删除账户）")
    if await user_crud.get_by_email_any(db, str(user_in.email)):
        raise HTTPException(status_code=409, detail="邮箱已被占用（包括已删除账户）")

    user = await user_crud.create(db, user_in.model_dump())
    await log_audit(
        db,
        user_id=current_user.id,
        action="create_user",
        target=f"user:{user.id}",
        detail=f"创建用户: {user.username}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(
        UserWithRoles.model_validate(user),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "/deleted",
    response_model=ResponseEnvelope[PaginatedData[UserWithRoles]],
)
async def list_deleted_users(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user:delete")),
) -> ResponseEnvelope[PaginatedData[UserWithRoles]]:
    """List soft-deleted users in the recycle bin."""
    users, total = await user_crud.get_deleted_multi(
        db,
        search=search,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [UserWithRoles.model_validate(user) for user in users]
    return paginated_response(items, total, page, page_size)


@router.post(
    "/{user_id}/restore",
    response_model=ResponseEnvelope[UserWithRoles],
)
async def restore_user(
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:delete")),
) -> ResponseEnvelope[UserWithRoles]:
    """Restore a soft-deleted user from the recycle bin."""
    restored = await user_crud.restore(db, user_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="回收站中不存在该用户")
    await log_audit(
        db,
        user_id=current_user.id,
        action="restore_user",
        target=f"user:{user_id}",
        detail=f"恢复用户: {restored.username}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(UserWithRoles.model_validate(restored), message="恢复成功")


@router.delete(
    "/{user_id}/purge",
    response_model=ResponseEnvelope[None],
)
async def purge_user(
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:delete")),
) -> ResponseEnvelope[None]:
    """Permanently delete a soft-deleted user."""
    if not await user_crud.hard_delete(db, user_id):
        raise HTTPException(status_code=404, detail="回收站中不存在该用户")
    await log_audit(
        db,
        user_id=current_user.id,
        action="purge_user",
        target=f"user:{user_id}",
        detail="永久删除用户",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="已永久删除")


@router.get(
    "/{user_id}",
    response_model=ResponseEnvelope[UserWithRoles],
)
async def get_user(
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user:read")),
) -> ResponseEnvelope[UserWithRoles]:
    """Return one active user and their active roles."""
    user = await user_crud.get_with_roles(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success_response(UserWithRoles.model_validate(user))


@router.patch(
    "/{user_id}",
    response_model=ResponseEnvelope[UserWithRoles],
)
@router.put(
    "/{user_id}",
    response_model=ResponseEnvelope[UserWithRoles],
    deprecated=True,
)
async def update_user(
    user_in: UserUpdate,
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:update")),
) -> ResponseEnvelope[UserWithRoles]:
    """Partially update a user and revoke sessions when disabling them."""
    user = await user_crud.get_with_roles(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == current_user.id and user_in.is_active is False:
        # Disabling bumps the token version and revokes every family, which would
        # lock the caller out of the system immediately.
        raise HTTPException(status_code=400, detail="不能停用当前登录用户")

    if user_in.email is not None and str(user_in.email) != user.email:
        existing = await user_crud.get_by_email_any(db, str(user_in.email))
        if existing is not None and existing.id != user_id:
            raise HTTPException(status_code=409, detail="邮箱已被占用（包括已删除账户）")

    # Treat every explicit disable as a security event. This remains safe when a
    # concurrent enable/disable changed the state after the initial read.
    disabling = user_in.is_active is False
    updated = await user_crud.update(db, user_id, user_in.model_dump(exclude_unset=True))
    if updated is None:  # protects against an unexpected concurrent deletion
        raise HTTPException(status_code=404, detail="用户不存在")
    if disabling:
        await revoke_all_refresh_sessions(db, user_id, reason="user_disabled")
        # The security lock refresh intentionally expires relationship state;
        # rehydrate the response shape without opening a new transaction.
        refreshed = await user_crud.get_with_roles_for_update(db, user_id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        updated = refreshed

    await log_audit(
        db,
        user_id=current_user.id,
        action="update_user",
        target=f"user:{user_id}",
        detail=f"更新用户信息: {updated.username}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(UserWithRoles.model_validate(updated), message="更新成功")


@router.delete(
    "/{user_id}",
    response_model=ResponseEnvelope[None],
)
async def delete_user(
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:delete")),
) -> ResponseEnvelope[None]:
    """Soft-delete a user and revoke all of their sessions atomically."""
    user = await user_crud.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")

    if not await user_crud.soft_delete(db, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    await revoke_all_refresh_sessions(db, user_id, reason="user_deleted")

    await log_audit(
        db,
        user_id=current_user.id,
        action="delete_user",
        target=f"user:{user_id}",
        detail=f"删除用户: {user.username}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="删除成功")


@router.put(
    "/{user_id}/password",
    response_model=ResponseEnvelope[None],
)
async def reset_password(
    password_in: AdminResetPasswordRequest,
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:reset_password")),
) -> ResponseEnvelope[None]:
    """Administrator sets a new password for another user, revoking their sessions."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="请通过个人中心修改自己的密码")

    changed = await user_crud.reset_password(db, user_id, password_in.new_password)
    if not changed:
        raise HTTPException(status_code=404, detail="用户不存在")

    await revoke_all_refresh_sessions(db, user_id, reason="password_reset_by_admin")
    await log_audit(
        db,
        user_id=current_user.id,
        action="reset_password",
        target=f"user:{user_id}",
        detail="管理员重置用户密码并撤销其全部登录会话",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="密码重置成功")


@router.put(
    "/{user_id}/roles",
    response_model=ResponseEnvelope[UserWithRoles],
)
async def assign_roles(
    roles_in: AssignRolesRequest,
    request: Request,
    user_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:assign")),
) -> ResponseEnvelope[UserWithRoles]:
    """Replace a user's roles after validating the complete ID set."""
    user = await user_crud.assign_roles(db, user_id, roles_in.role_ids)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    await log_audit(
        db,
        user_id=current_user.id,
        action="assign_roles",
        target=f"user:{user_id}",
        detail=f"分配角色: {roles_in.role_ids}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(UserWithRoles.model_validate(user), message="角色分配成功")
