"""Asynchronous permission repository."""

from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.crud.base import CRUDBase, ModelData, contains_pattern
from app.models.permission import Permission


class CRUDPermission(CRUDBase[Permission]):
    """Data access for RBAC permissions."""

    model = Permission

    @staticmethod
    def _filtered_statement(
        search: str | None,
        module: str | None,
    ) -> Select[tuple[Permission]]:
        stmt = select(Permission).where(Permission.is_deleted.is_(False))
        if search:
            search_pattern = contains_pattern(search)
            stmt = stmt.where(
                or_(
                    Permission.name.ilike(search_pattern, escape="\\"),
                    Permission.code.ilike(search_pattern, escape="\\"),
                )
            )
        if module:
            stmt = stmt.where(Permission.module == module)
        return stmt

    async def get_by_code_any(self, db: AsyncSession, code: str) -> Permission | None:
        """Return matching code including a recoverable soft-deleted permission."""
        result = await db.execute(select(Permission).where(Permission.code == code))
        return result.scalar_one_or_none()

    async def get_all_grouped(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        module: str | None = None,
    ) -> dict[str, list[Permission]]:
        """Return filtered active permissions grouped in a deterministic order."""
        stmt = self._filtered_statement(search, module).order_by(
            Permission.module,
            Permission.code,
            Permission.id,
        )
        result = await db.execute(stmt)
        grouped: defaultdict[str, list[Permission]] = defaultdict(list)
        for permission in result.scalars().all():
            grouped[permission.module or "其他"].append(permission)
        return dict(grouped)

    async def update(
        self,
        db: AsyncSession,
        id: int,
        obj_data: ModelData,
    ) -> Permission | None:
        permission = await self.get_for_update(db, id)
        if permission is None:
            return None
        for field, value in obj_data.items():
            if field in {"name", "code", "module", "description", "is_active"}:
                setattr(permission, field, value)
        await db.flush()
        return permission

    async def get_multi_filtered(
        self,
        db: AsyncSession,
        search: str | None = None,
        module: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Permission], int]:
        """Return a deterministic filtered permission page."""
        stmt = self._filtered_statement(search, module)

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        page_stmt = stmt.order_by(Permission.module, Permission.code, Permission.id)
        page_stmt = page_stmt.offset(skip).limit(limit)
        permissions_result = await db.execute(page_stmt)
        return list(permissions_result.scalars().all()), total

    async def get_deleted_multi(
        self,
        db: AsyncSession,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Permission], int]:
        """Return a page of soft-deleted permissions for the recycle bin."""
        stmt = select(Permission).where(Permission.is_deleted.is_(True))
        if search:
            search_pattern = contains_pattern(search)
            stmt = stmt.where(
                or_(
                    Permission.name.ilike(search_pattern, escape="\\"),
                    Permission.code.ilike(search_pattern, escape="\\"),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        page_stmt = (
            stmt.order_by(Permission.updated_at.desc(), Permission.id.desc())
            .offset(skip)
            .limit(limit)
        )
        permissions = list((await db.execute(page_stmt)).scalars().all())
        return permissions, total

    async def restore(self, db: AsyncSession, permission_id: int) -> Permission | None:
        """Restore a soft-deleted permission."""
        stmt = (
            select(Permission)
            .where(Permission.id == permission_id, Permission.is_deleted.is_(True))
            .order_by(Permission.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        permission = (await db.execute(stmt)).scalar_one_or_none()
        if permission is None:
            return None
        permission.is_deleted = False
        await db.flush()
        return permission

    async def hard_delete(self, db: AsyncSession, permission_id: int) -> bool:
        """Permanently remove a soft-deleted permission."""
        stmt = (
            select(Permission)
            .where(Permission.id == permission_id, Permission.is_deleted.is_(True))
            .order_by(Permission.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        permission = (await db.execute(stmt)).scalar_one_or_none()
        if permission is None:
            return False
        await db.delete(permission)
        await db.flush()
        return True


permission_crud = CRUDPermission()
