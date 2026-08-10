"""Asynchronous permission-management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_client_ip, require_permission
from app.crud.permission import permission_crud
from app.models.user import User
from app.schemas.common import PaginatedData, ResponseEnvelope, paginated_response, success_response
from app.schemas.permission import PermissionCreate, PermissionResponse, PermissionUpdate
from app.utils.audit import log_audit

router = APIRouter()

type PermissionListData = PaginatedData[PermissionResponse] | dict[str, list[PermissionResponse]]


@router.get(
    "/deleted",
    response_model=ResponseEnvelope[PaginatedData[PermissionResponse]],
)
async def list_deleted_permissions(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("permission:delete")),
) -> ResponseEnvelope[PaginatedData[PermissionResponse]]:
    """List soft-deleted permissions in the recycle bin."""
    permissions, total = await permission_crud.get_deleted_multi(
        db,
        search=search,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [PermissionResponse.model_validate(permission) for permission in permissions]
    return paginated_response(items, total, page, page_size)


@router.post(
    "/{permission_id}/restore",
    response_model=ResponseEnvelope[PermissionResponse],
)
async def restore_permission(
    request: Request,
    permission_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission:delete")),
) -> ResponseEnvelope[PermissionResponse]:
    """Restore a soft-deleted permission from the recycle bin."""
    restored = await permission_crud.restore(db, permission_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="回收站中不存在该权限")
    await log_audit(
        db,
        user_id=current_user.id,
        action="restore_permission",
        target=f"permission:{permission_id}",
        detail=f"恢复权限: {restored.code}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(PermissionResponse.model_validate(restored), message="恢复成功")


@router.delete(
    "/{permission_id}/purge",
    response_model=ResponseEnvelope[None],
)
async def purge_permission(
    request: Request,
    permission_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission:delete")),
) -> ResponseEnvelope[None]:
    """Permanently delete a soft-deleted permission."""
    if not await permission_crud.hard_delete(db, permission_id):
        raise HTTPException(status_code=404, detail="回收站中不存在该权限")
    await log_audit(
        db,
        user_id=current_user.id,
        action="purge_permission",
        target=f"permission:{permission_id}",
        detail="永久删除权限",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="已永久删除")


@router.get(
    "",
    response_model=ResponseEnvelope[PermissionListData],
)
async def list_permissions(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    module: str | None = Query(default=None, min_length=1, max_length=50),
    grouped: bool = Query(default=False, description="按模块分组返回"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("permission:read")),
) -> ResponseEnvelope[PermissionListData]:
    """Return either a paginated list or a deterministic module grouping."""
    if grouped:
        grouped_permissions = await permission_crud.get_all_grouped(
            db,
            search=search,
            module=module,
        )
        result: PermissionListData = {
            module_name: [PermissionResponse.model_validate(item) for item in permissions]
            for module_name, permissions in grouped_permissions.items()
        }
        return success_response(result)

    permissions, total = await permission_crud.get_multi_filtered(
        db,
        search=search,
        module=module,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [PermissionResponse.model_validate(permission) for permission in permissions]
    result = PaginatedData[PermissionResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return success_response(result)


@router.post(
    "",
    response_model=ResponseEnvelope[PermissionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_permission(
    permission_in: PermissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission:create")),
) -> ResponseEnvelope[PermissionResponse]:
    """Create a unique permission code."""
    if await permission_crud.get_by_code_any(db, permission_in.code):
        raise HTTPException(status_code=409, detail="权限码已被占用（包括已删除权限）")

    permission = await permission_crud.create(db, permission_in.model_dump())
    await log_audit(
        db,
        user_id=current_user.id,
        action="create_permission",
        target=f"permission:{permission.id}",
        detail=f"创建权限: {permission.code}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(
        PermissionResponse.model_validate(permission),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.patch(
    "/{permission_id}",
    response_model=ResponseEnvelope[PermissionResponse],
)
@router.put(
    "/{permission_id}",
    response_model=ResponseEnvelope[PermissionResponse],
    deprecated=True,
)
async def update_permission(
    permission_in: PermissionUpdate,
    request: Request,
    permission_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission:update")),
) -> ResponseEnvelope[PermissionResponse]:
    """Partially update a permission under a row lock."""
    if permission_in.code is not None:
        existing = await permission_crud.get_by_code_any(db, permission_in.code)
        if existing is not None and existing.id != permission_id:
            raise HTTPException(status_code=409, detail="权限码已被占用（包括已删除权限）")

    updated = await permission_crud.update(
        db,
        permission_id,
        permission_in.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="权限不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="update_permission",
        target=f"permission:{permission_id}",
        detail=f"更新权限: {updated.code}",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(PermissionResponse.model_validate(updated), message="更新成功")


@router.delete(
    "/{permission_id}",
    response_model=ResponseEnvelope[None],
)
async def delete_permission(
    request: Request,
    permission_id: int = Path(gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("permission:delete")),
) -> ResponseEnvelope[None]:
    """Soft-delete a permission under the same lock used by assignment."""
    if not await permission_crud.soft_delete(db, permission_id):
        raise HTTPException(status_code=404, detail="权限不存在")
    await log_audit(
        db,
        user_id=current_user.id,
        action="delete_permission",
        target=f"permission:{permission_id}",
        detail="删除权限",
        ip=get_client_ip(request),
    )
    await db.commit()
    return success_response(None, message="删除成功")
