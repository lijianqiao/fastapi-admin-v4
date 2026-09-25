"""Permission-management endpoints: HTTP adaptation only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.v1.recycle_bin import build_recycle_bin_router
from app.core.deps import Audit, DbSession, PageParams, audited, page_query, require_permission
from app.core.permissions import Perm
from app.crud.permission import permission_crud
from app.models.user import User
from app.schemas.common import PaginatedData, ResponseEnvelope, success_response
from app.schemas.permission import PermissionCreate, PermissionResponse, PermissionUpdate
from app.services import permissions as permissions_service
from app.services.guards import guard_permission_purge, guard_permission_restore

router = APIRouter()
router.include_router(
    build_recycle_bin_router(
        crud=permission_crud,
        list_schema=PermissionResponse,
        detail_schema=PermissionResponse,
        permission=Perm.PERMISSION_DELETE,
        resource="permission",
        label="权限",
        describe=lambda permission: permission.code,
        before_restore=guard_permission_restore,
        before_purge=guard_permission_purge,
    )
)

PermissionId = Annotated[int, Path(gt=0)]
type PermissionListData = PaginatedData[PermissionResponse] | dict[str, list[PermissionResponse]]


@router.get("")
async def list_permissions(
    db: DbSession,
    _: Annotated[User, Depends(require_permission(Perm.PERMISSION_READ))],
    page: Annotated[PageParams, Depends(page_query(default_size=100, max_size=200))],
    module: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    grouped: Annotated[bool, Query(description="按模块分组返回")] = False,
) -> ResponseEnvelope[PermissionListData]:
    """Return either a paginated list or a deterministic module grouping."""
    if grouped:
        grouped_permissions = await permission_crud.get_all_grouped(
            db,
            search=page.search,
            module=module,
        )
        result: PermissionListData = {
            module_name: [PermissionResponse.model_validate(item) for item in permissions]
            for module_name, permissions in grouped_permissions.items()
        }
        return success_response(result)

    permissions, total = await permission_crud.get_multi_filtered(
        db,
        search=page.search,
        module=module,
        skip=page.skip,
        limit=page.page_size,
    )
    result = PaginatedData[PermissionResponse](
        items=[PermissionResponse.model_validate(permission) for permission in permissions],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )
    return success_response(result)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission_in: PermissionCreate,
    audit: Annotated[Audit, Depends(audited(Perm.PERMISSION_CREATE))],
) -> ResponseEnvelope[PermissionResponse]:
    """Create a unique custom permission code."""
    permission = await permissions_service.create_permission(audit.db, permission_in)
    await audit.commit(
        "create_permission",
        f"permission:{permission.id}",
        f"创建权限: {permission.code}",
    )
    return success_response(
        PermissionResponse.model_validate(permission),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.patch("/{permission_id}")
@router.put("/{permission_id}", deprecated=True)
async def update_permission(
    permission_id: PermissionId,
    permission_in: PermissionUpdate,
    audit: Annotated[Audit, Depends(audited(Perm.PERMISSION_UPDATE))],
) -> ResponseEnvelope[PermissionResponse]:
    """Partially update a permission under a row lock."""
    permission = await permissions_service.update_permission(
        audit.db,
        audit.actor,
        permission_id,
        permission_in,
    )
    await audit.commit(
        "update_permission",
        f"permission:{permission_id}",
        f"更新权限: {permission.code}",
    )
    return success_response(PermissionResponse.model_validate(permission), message="更新成功")


@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: PermissionId,
    audit: Annotated[Audit, Depends(audited(Perm.PERMISSION_DELETE))],
) -> ResponseEnvelope[None]:
    """Soft-delete a custom permission under the same lock used by assignment."""
    await permissions_service.delete_permission(audit.db, permission_id)
    await audit.commit("delete_permission", f"permission:{permission_id}", "删除权限")
    return success_response(None, message="删除成功")
