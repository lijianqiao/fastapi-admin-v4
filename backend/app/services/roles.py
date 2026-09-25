"""Role-management use cases."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.crud.permission import permission_crud
from app.crud.role import RoleInUseError, role_crud
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleUpdate
from app.services.guards import ensure_grantable, ensure_role_grant_allowed


async def _ensure_name_available(db: AsyncSession, name: str, *, owner_id: int | None) -> None:
    existing = await role_crud.get_by_name_any(db, name)
    if existing is not None and existing.id != owner_id:
        raise ConflictError("角色名已被占用（包括已删除角色）")


async def create_role(db: AsyncSession, data: RoleCreate) -> Role:
    """Create an empty role; permissions require the dedicated assign operation."""
    await _ensure_name_available(db, data.name, owner_id=None)
    return await role_crud.create(db, data.model_dump())


async def update_role(db: AsyncSession, actor: User, role_id: int, data: RoleUpdate) -> Role:
    """Partially update a role; re-enabling it follows the delegation rules."""
    changes = data.model_dump(exclude_unset=True)
    role = await role_crud.get_with_permissions_for_update(db, role_id)
    if role is None:
        raise NotFoundError("角色不存在")
    if changes.get("is_active") is True and not role.is_active:
        await ensure_role_grant_allowed(db, actor, role.id)
    if "name" in changes and changes["name"] != role.name:
        await _ensure_name_available(db, changes["name"], owner_id=role.id)
    role_crud.apply_update(role, changes)
    await db.flush()
    return role


async def delete_role(db: AsyncSession, role_id: int) -> Role:
    """Soft-delete a role only when no live user still holds it."""
    role = await role_crud.get_with_permissions_for_update(db, role_id)
    if role is None:
        raise NotFoundError("角色不存在")
    user_count = await role_crud.get_user_count(db, role_id)
    if user_count:
        raise RoleInUseError(user_count)
    role.is_deleted = True
    await db.flush()
    return role


async def assign_permissions(
    db: AsyncSession,
    actor: User,
    role_id: int,
    permission_ids: list[int],
) -> Role:
    """Replace a role's permissions; non-superusers may only add what they hold."""
    if not actor.is_superuser:
        added_ids = set(permission_ids) - await role_crud.get_permission_ids(db, role_id)
        await ensure_grantable(db, actor, await permission_crud.get_codes_by_ids(db, added_ids))
    role = await role_crud.assign_permissions(db, role_id, permission_ids)
    if role is None:
        raise NotFoundError("角色不存在")
    return role
