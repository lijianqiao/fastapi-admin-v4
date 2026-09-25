"""Permission-management use cases."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import SYSTEM_PERMISSION_CODES
from app.crud.permission import permission_crud
from app.models.permission import Permission
from app.models.user import User
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.services.guards import ensure_permission_grant_allowed


async def create_permission(db: AsyncSession, data: PermissionCreate) -> Permission:
    """Create a custom permission; registry codes are reserved."""
    if data.code in SYSTEM_PERMISSION_CODES:
        raise ForbiddenError("该权限码由系统保留，请使用其他权限码")
    if await permission_crud.get_by_code_any(db, data.code):
        raise ConflictError("权限码已被占用（包括已删除权限）")
    return await permission_crud.create(db, data.model_dump())


async def update_permission(
    db: AsyncSession,
    actor: User,
    permission_id: int,
    data: PermissionUpdate,
) -> Permission:
    """Partially update a permission; re-enabling it follows the delegation rules."""
    changes = data.model_dump(exclude_unset=True)
    permission = await permission_crud.get_for_update(db, permission_id)
    if permission is None:
        raise NotFoundError("权限不存在")
    if changes.get("is_active") is True and not permission.is_active:
        await ensure_permission_grant_allowed(db, actor, permission)
    permission_crud.apply_update(permission, changes)
    await db.flush()
    return permission


async def delete_permission(db: AsyncSession, permission_id: int) -> Permission:
    """Soft-delete a custom permission."""
    permission = await permission_crud.get_for_update(db, permission_id)
    if permission is None:
        raise NotFoundError("权限不存在")
    if permission.is_system:
        raise ForbiddenError("系统权限不可删除")
    permission.is_deleted = True
    await db.flush()
    return permission
