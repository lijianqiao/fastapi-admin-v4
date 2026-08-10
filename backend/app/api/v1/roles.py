"""Asynchronous role-management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_client_ip, require_permission
from app.crud.role import role_crud
from app.models.user import User
from app.schemas.common import PaginatedData, ResponseEnvelope, paginated_response, success_response
from app.schemas.role import (
    AssignPermissionsRequest,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    RoleWithPermissions,
)
from app.utils.audit import log_audit

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[RoleWithPermissions]],
)
async def list_roles(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("role:read")),
) -> ResponseEnvelope[PaginatedData[RoleWithPermissions]]:
    """Return roles with permissions and user counts without N+1 queries."""
    roles, total = await role_crud.get_multi_filtered(
        db,
        search=search,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [RoleWithPermissions.model_validate(role) for role in roles]
    return paginated_response(items, total, page, page_size)


@router.post(
    "",
    response_model=ResponseEnvelope[RoleWithPermissions],
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    role_in: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:create")),
) -> ResponseEnvelope[RoleWithPermissions]:
    """Create a role without implicitly assigning privileged permissions."""
    if await role_crud.get_by_name_any(db, role_in.name):
        raise HTTPException(status_code=409, detail="角色名已被占用（包括已删除角色）")

    role = await role_crud.create(db, role_in.model_dump())
    await log_audit(
        db,
        user_id=current_user.id,
        action="create_role",
        target=f"role:{role.id}",
        detail=f"创建角色: {role.name}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(
        RoleWithPermissions.model_validate(role),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "/deleted",
    response_model=ResponseEnvelope[PaginatedData[RoleResponse]],
)
async def list_deleted_roles(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("role:delete")),
) -> ResponseEnvelope[PaginatedData[RoleResponse]]:
    """List soft-deleted roles in the recycle bin."""
    roles, total = await role_crud.get_deleted_multi(
        db,
        search=search,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [RoleResponse.model_validate(role) for role in roles]
    return paginated_response(items, total, page, page_size)


@router.post(
    "/{role_id}/restore",
    response_model=ResponseEnvelope[RoleWithPermissions],
)
async def restore_role(
    request: Request,
    role_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete")),
) -> ResponseEnvelope[RoleWithPermissions]:
    """Restore a soft-deleted role from the recycle bin."""
    restored = await role_crud.restore(db, role_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="回收站中不存在该角色")
    await log_audit(
        db,
        user_id=current_user.id,
        action="restore_role",
        target=f"role:{role_id}",
        detail=f"恢复角色: {restored.name}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(RoleWithPermissions.model_validate(restored), message="恢复成功")


@router.delete(
    "/{role_id}/purge",
    response_model=ResponseEnvelope[None],
)
async def purge_role(
    request: Request,
    role_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete")),
) -> ResponseEnvelope[None]:
    """Permanently delete a soft-deleted role."""
    if not await role_crud.hard_delete(db, role_id):
        raise HTTPException(status_code=404, detail="回收站中不存在该角色")
    await log_audit(
        db,
        user_id=current_user.id,
        action="purge_role",
        target=f"role:{role_id}",
        detail="永久删除角色",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="已永久删除")


@router.patch(
    "/{role_id}",
    response_model=ResponseEnvelope[RoleWithPermissions],
)
@router.put(
    "/{role_id}",
    response_model=ResponseEnvelope[RoleWithPermissions],
    deprecated=True,
)
async def update_role(
    role_in: RoleUpdate,
    request: Request,
    role_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:update")),
) -> ResponseEnvelope[RoleWithPermissions]:
    """Partially update a role."""
    if role_in.name is not None:
        existing = await role_crud.get_by_name_any(db, role_in.name)
        if existing is not None and existing.id != role_id:
            raise HTTPException(status_code=409, detail="角色名已被占用（包括已删除角色）")

    updated = await role_crud.update(db, role_id, role_in.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="update_role",
        target=f"role:{role_id}",
        detail=f"更新角色: {updated.name}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(RoleWithPermissions.model_validate(updated), message="更新成功")


@router.delete(
    "/{role_id}",
    response_model=ResponseEnvelope[None],
)
async def delete_role(
    request: Request,
    role_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete")),
) -> ResponseEnvelope[None]:
    """Soft-delete an unassigned role under a row lock."""
    if not await role_crud.soft_delete_if_unassigned(db, role_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="delete_role",
        target=f"role:{role_id}",
        detail="删除角色",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="删除成功")


@router.put(
    "/{role_id}/permissions",
    response_model=ResponseEnvelope[RoleWithPermissions],
)
async def assign_permissions(
    perms_in: AssignPermissionsRequest,
    request: Request,
    role_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:assign")),
) -> ResponseEnvelope[RoleWithPermissions]:
    """Replace role permissions after validating every requested ID."""
    role = await role_crud.assign_permissions(db, role_id, perms_in.permission_ids)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="assign_permissions",
        target=f"role:{role_id}",
        detail=f"分配权限: {perms_in.permission_ids}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(RoleWithPermissions.model_validate(role), message="权限分配成功")
