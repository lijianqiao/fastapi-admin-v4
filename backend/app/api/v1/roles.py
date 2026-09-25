"""Role-management endpoints: HTTP adaptation only; rules live in app.services.roles."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.v1.recycle_bin import build_recycle_bin_router
from app.core.deps import Audit, DbSession, PageQuery, audited, require_permission
from app.core.permissions import Perm
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
from app.services import roles as roles_service
from app.services.guards import guard_role_restore

router = APIRouter()
router.include_router(
    build_recycle_bin_router(
        crud=role_crud,
        list_schema=RoleResponse,
        detail_schema=RoleWithPermissions,
        permission=Perm.ROLE_DELETE,
        resource="role",
        label="角色",
        describe=lambda role: role.name,
        before_restore=guard_role_restore,
    )
)

RoleId = Annotated[int, Path(gt=0)]


@router.get("")
async def list_roles(
    page: PageQuery,
    db: DbSession,
    _: Annotated[User, Depends(require_permission(Perm.ROLE_READ))],
) -> ResponseEnvelope[PaginatedData[RoleWithPermissions]]:
    """Return roles with permissions and user counts without N+1 queries."""
    roles, total = await role_crud.get_multi_filtered(
        db,
        search=page.search,
        skip=page.skip,
        limit=page.page_size,
    )
    items = [RoleWithPermissions.model_validate(role) for role in roles]
    return paginated_response(items, total, page.page, page.page_size)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    audit: Annotated[Audit, Depends(audited(Perm.ROLE_CREATE))],
) -> ResponseEnvelope[RoleWithPermissions]:
    """Create a role without implicitly assigning privileged permissions."""
    role = await roles_service.create_role(audit.db, role_in)
    await audit.commit("create_role", f"role:{role.id}", f"创建角色: {role.name}")
    return success_response(
        RoleWithPermissions.model_validate(role),
        message="创建成功",
        code=status.HTTP_201_CREATED,
    )


@router.patch("/{role_id}")
@router.put("/{role_id}", deprecated=True)
async def update_role(
    role_id: RoleId,
    role_in: RoleUpdate,
    audit: Annotated[Audit, Depends(audited(Perm.ROLE_UPDATE))],
) -> ResponseEnvelope[RoleWithPermissions]:
    """Partially update a role."""
    role = await roles_service.update_role(audit.db, audit.actor, role_id, role_in)
    await audit.commit("update_role", f"role:{role_id}", f"更新角色: {role.name}")
    return success_response(RoleWithPermissions.model_validate(role), message="更新成功")


@router.delete("/{role_id}")
async def delete_role(
    role_id: RoleId,
    audit: Annotated[Audit, Depends(audited(Perm.ROLE_DELETE))],
) -> ResponseEnvelope[None]:
    """Soft-delete an unassigned role under a row lock."""
    await roles_service.delete_role(audit.db, role_id)
    await audit.commit("delete_role", f"role:{role_id}", "删除角色")
    return success_response(None, message="删除成功")


@router.put("/{role_id}/permissions")
async def assign_permissions(
    role_id: RoleId,
    perms_in: AssignPermissionsRequest,
    audit: Annotated[Audit, Depends(audited(Perm.ROLE_ASSIGN))],
) -> ResponseEnvelope[RoleWithPermissions]:
    """Replace role permissions after validating every requested ID."""
    role = await roles_service.assign_permissions(
        audit.db,
        audit.actor,
        role_id,
        perms_in.permission_ids,
    )
    await audit.commit(
        "assign_permissions",
        f"role:{role_id}",
        f"分配权限: {perms_in.permission_ids}",
    )
    return success_response(RoleWithPermissions.model_validate(role), message="权限分配成功")
