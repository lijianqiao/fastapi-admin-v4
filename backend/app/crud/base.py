"""Typed asynchronous CRUD primitives.

Repositories flush pending changes but never commit. The HTTP/service layer owns
the transaction so a business change and its audit entry succeed or fail together.
"""

from collections.abc import Iterable, Mapping
from typing import Generic, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)
type ModelData = Mapping[str, object]


def contains_pattern(value: str) -> str:
    """Build a literal SQL LIKE contains pattern with wildcard characters escaped."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class RelatedObjectsNotFoundError(ValueError):
    """Raised when a relation assignment contains unknown or deleted IDs."""

    def __init__(self, relation: str, missing_ids: Iterable[int]) -> None:
        self.relation = relation
        self.missing_ids = tuple(sorted(set(missing_ids)))
        joined_ids = ", ".join(str(item_id) for item_id in self.missing_ids)
        super().__init__(f"{relation} IDs do not exist: {joined_ids}")


class CRUDBase(Generic[ModelT]):
    """Common asynchronous operations for one ORM model."""

    model: type[ModelT]

    def _id_column(self) -> InstrumentedAttribute[int]:
        return cast("InstrumentedAttribute[int]", vars(self.model)["id"])

    def _soft_delete_column(self) -> InstrumentedAttribute[bool] | None:
        column = getattr(self.model, "is_deleted", None)
        if column is None:
            return None
        return cast("InstrumentedAttribute[bool]", column)

    def _active_statement(self) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        deleted_column = self._soft_delete_column()
        if deleted_column is not None:
            stmt = stmt.where(deleted_column.is_(False))
        return stmt

    async def get(self, db: AsyncSession, id: int) -> ModelT | None:
        """Return one non-deleted record by primary key."""
        stmt = self._active_statement().where(self._id_column() == id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update(self, db: AsyncSession, id: int) -> ModelT | None:
        """Lock and return one active row for a caller-owned transaction."""
        stmt = (
            self._active_statement()
            .where(self._id_column() == id)
            .order_by(self._id_column())
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_data: ModelData) -> ModelT:
        """Add a new record and flush without committing."""
        db_obj = self.model(**dict(obj_data))
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        id: int,
        obj_data: ModelData,
    ) -> ModelT | None:
        """Apply provided fields and flush without committing."""
        db_obj = await self.get_for_update(db, id)
        if db_obj is None:
            return None

        immutable_fields = {"id", "created_at", "updated_at", "is_deleted"}
        for field, value in obj_data.items():
            if field not in immutable_fields and hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await db.flush()
        return db_obj

    async def soft_delete(self, db: AsyncSession, id: int) -> bool:
        """Mark a record as deleted and flush without committing."""
        db_obj = await self.get_for_update(db, id)
        deleted_column = self._soft_delete_column()
        if db_obj is None or deleted_column is None:
            return False

        setattr(db_obj, deleted_column.key, True)
        await db.flush()
        return True
