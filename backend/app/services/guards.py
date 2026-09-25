"""Authorization rules that depend on who is acting on whom."""

from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.crud.permission import permission_crud
from app.crud.role import role_crud
from app.crud.user import user_crud
from app.models.permission import Permission
from app.models.user import User


def ensure_can_manage(actor: User, target: User) -> None:
    """Only a superuser may modify another superuser's account.

    ``is_superuser`` cannot be changed through the API, so checking it on a
    non-locking read is race-free.
    """
    if target.is_superuser and not actor.is_superuser:
        raise ForbiddenError("仅超级管理员可以管理超级管理员账户")


async def ensure_grantable(db: AsyncSession, actor: User, codes: Collection[str]) -> None:
    """A non-superuser may only grant permissions they currently hold themselves."""
    if actor.is_superuser or not codes:
        return
    owned = set(await user_crud.get_permission_codes(db, actor.id))
    missing = sorted(set(codes) - owned)
    if missing:
        raise ForbiddenError(
            f"不能授予自己不具备的权限：{'、'.join(missing)}",
            data={"missing_codes": missing},
        )


async def ensure_role_grant_allowed(db: AsyncSession, actor: User, role_id: int) -> None:
    """启用或恢复角色会把它的权限重新授予其用户；角色没有在用用户时不构成授权。"""
    if actor.is_superuser or not await role_crud.get_user_count(db, role_id):
        return
    await ensure_grantable(db, actor, await role_crud.get_permission_codes(db, {role_id}))


async def ensure_permission_grant_allowed(
    db: AsyncSession,
    actor: User,
    permission: Permission,
) -> None:
    """启用或恢复挂在未删除角色上的权限，等同于把它授予这些角色的用户。"""
    if actor.is_superuser:
        return
    if not await permission_crud.is_granted_through_live_role(db, permission.id):
        return
    await ensure_grantable(db, actor, {permission.code})
