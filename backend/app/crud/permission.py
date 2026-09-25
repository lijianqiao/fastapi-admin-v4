"""Asynchronous permission repository."""

from collections import defaultdict
from collections.abc import Collection

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.crud.base import SoftDeleteCRUD, contains_pattern
from app.models.permission import Permission
from app.models.role import Role, role_permissions


class CRUDPermission(SoftDeleteCRUD[Permission]):
    """Data access for RBAC permissions."""

    model = Permission
    updatable_fields = frozenset({"name", "module", "description", "is_active"})
    search_columns = ("name", "code")

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

    async def get_codes_by_ids(
        self,
        db: AsyncSession,
        permission_ids: Collection[int],
    ) -> set[str]:
        """Codes of the given non-deleted permissions."""
        if not permission_ids:
            return set()
        stmt = select(Permission.code).where(
            Permission.id.in_(permission_ids),
            Permission.is_deleted.is_(False),
        )
        return set((await db.execute(stmt)).scalars().all())

    async def is_granted_through_live_role(self, db: AsyncSession, permission_id: int) -> bool:
        """Whether any non-deleted role carries this permission."""
        stmt = select(
            exists().where(
                role_permissions.c.permission_id == permission_id,
                role_permissions.c.role_id == Role.id,
                Role.is_deleted.is_(False),
            )
        )
        return bool(await db.scalar(stmt))

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

        return await self.paginate(
            db,
            stmt,
            order_by=(Permission.module.asc(), Permission.code.asc(), Permission.id.asc()),
            skip=skip,
            limit=limit,
        )


permission_crud = CRUDPermission()
