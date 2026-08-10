"""Asynchronous role repository."""

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_expression
from sqlalchemy.sql.selectable import ScalarSelect

from app.crud.base import CRUDBase, ModelData, RelatedObjectsNotFoundError, contains_pattern
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, user_roles


class RoleInUseError(ValueError):
    """Raised when a role still belongs to one or more non-deleted users."""

    def __init__(self, user_count: int) -> None:
        self.user_count = user_count
        super().__init__(f"角色仍关联 {user_count} 个用户")


class CRUDRole(CRUDBase[Role]):
    """Data access for roles and permission assignments."""

    model = Role

    @staticmethod
    def _active_user_count_expression() -> ScalarSelect[int]:
        return (
            select(func.count(user_roles.c.user_id))
            .select_from(user_roles.join(User, User.id == user_roles.c.user_id))
            .where(
                user_roles.c.role_id == Role.id,
                User.is_deleted.is_(False),
            )
            .correlate(Role)
            .scalar_subquery()
        )

    async def get_by_name_any(self, db: AsyncSession, name: str) -> Role | None:
        """Return matching name including a recoverable soft-deleted role."""
        result = await db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def get_with_permissions_for_update(
        self,
        db: AsyncSession,
        role_id: int,
    ) -> Role | None:
        """Lock and return a role with its active permissions loaded."""
        stmt = (
            select(Role)
            .where(Role.id == role_id, Role.is_deleted.is_(False))
            .options(
                selectinload(Role.permissions.and_(Permission.is_deleted.is_(False))),
                with_expression(Role._user_count, self._active_user_count_expression()),
            )
            .order_by(Role.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_all_permissions_for_update(
        self,
        db: AsyncSession,
        role_id: int,
    ) -> Role | None:
        """Lock a role and load every permission association for replacement."""
        stmt = (
            select(Role)
            .where(Role.id == role_id, Role.is_deleted.is_(False))
            .options(
                selectinload(Role.permissions),
                with_expression(Role._user_count, self._active_user_count_expression()),
            )
            .order_by(Role.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_required_permissions(
        self,
        db: AsyncSession,
        permission_ids: Iterable[int],
    ) -> list[Permission]:
        normalized_ids = tuple(dict.fromkeys(permission_ids))
        if not normalized_ids:
            return []

        stmt = (
            select(Permission)
            .where(
                Permission.id.in_(normalized_ids),
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.id)
            .with_for_update()
        )
        result = await db.execute(stmt)
        permissions_by_id = {permission.id: permission for permission in result.scalars().all()}
        missing_ids = set(normalized_ids) - permissions_by_id.keys()
        if missing_ids:
            raise RelatedObjectsNotFoundError("permission", missing_ids)
        return [permissions_by_id[permission_id] for permission_id in normalized_ids]

    async def create(self, db: AsyncSession, obj_data: ModelData) -> Role:
        """Create an empty role; permissions require the dedicated assign operation."""
        role = Role(**dict(obj_data))
        role.permissions = []
        db.add(role)
        await db.flush()
        return role

    async def update(
        self,
        db: AsyncSession,
        id: int,
        obj_data: ModelData,
    ) -> Role | None:
        """Update mutable role fields while preserving eager response state."""
        role = await self.get_with_permissions_for_update(db, id)
        if role is None:
            return None
        for field, value in obj_data.items():
            if field in {"name", "description", "is_active"}:
                setattr(role, field, value)
        await db.flush()
        return role

    async def assign_permissions(
        self,
        db: AsyncSession,
        role_id: int,
        permission_ids: list[int],
    ) -> Role | None:
        """Atomically replace permissions after validating the full ID set."""
        role = await self.get_with_all_permissions_for_update(db, role_id)
        if role is None:
            return None
        role.permissions = await self._get_required_permissions(db, permission_ids)
        await db.flush()
        return role

    async def get_user_count(self, db: AsyncSession, role_id: int) -> int:
        """Count non-deleted users associated with a role."""
        stmt = (
            select(func.count(user_roles.c.user_id))
            .select_from(user_roles.join(User, User.id == user_roles.c.user_id))
            .where(
                user_roles.c.role_id == role_id,
                User.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def soft_delete_if_unassigned(self, db: AsyncSession, role_id: int) -> bool:
        """Lock a role and delete it only when no live user still references it."""
        role = await self.get_with_permissions_for_update(db, role_id)
        if role is None:
            return False

        user_count = await self.get_user_count(db, role_id)
        if user_count:
            raise RoleInUseError(user_count)

        role.is_deleted = True
        await db.flush()
        return True

    async def get_deleted_multi(
        self,
        db: AsyncSession,
        search: str | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Role], int]:
        """Return a page of soft-deleted roles for the recycle bin."""
        stmt = select(Role).where(Role.is_deleted.is_(True))
        if search:
            stmt = stmt.where(Role.name.ilike(contains_pattern(search), escape="\\"))

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        page_stmt = stmt.order_by(Role.updated_at.desc(), Role.id.desc()).offset(skip).limit(limit)
        roles = list((await db.execute(page_stmt)).scalars().all())
        return roles, total

    async def restore(self, db: AsyncSession, role_id: int) -> Role | None:
        """Restore a soft-deleted role."""
        stmt = (
            select(Role)
            .where(Role.id == role_id, Role.is_deleted.is_(True))
            .options(
                selectinload(Role.permissions.and_(Permission.is_deleted.is_(False))),
                with_expression(Role._user_count, self._active_user_count_expression()),
            )
            .order_by(Role.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            return None
        role.is_deleted = False
        await db.flush()
        return role

    async def hard_delete(self, db: AsyncSession, role_id: int) -> bool:
        """Permanently remove a soft-deleted role."""
        stmt = (
            select(Role)
            .where(Role.id == role_id, Role.is_deleted.is_(True))
            .order_by(Role.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        role = (await db.execute(stmt)).scalar_one_or_none()
        if role is None:
            return False
        await db.delete(role)
        await db.flush()
        return True

    async def get_multi_filtered(
        self,
        db: AsyncSession,
        search: str | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Role], int]:
        """Return a deterministic page with permissions and counts preloaded."""
        stmt = (
            select(Role)
            .where(Role.is_deleted.is_(False))
            .options(
                selectinload(Role.permissions.and_(Permission.is_deleted.is_(False))),
                with_expression(Role._user_count, self._active_user_count_expression()),
            )
        )
        if search:
            stmt = stmt.where(Role.name.ilike(contains_pattern(search), escape="\\"))

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        page_stmt = stmt.order_by(Role.id).offset(skip).limit(limit)
        roles_result = await db.execute(page_stmt)
        return list(roles_result.scalars().unique().all()), total


role_crud = CRUDRole()
