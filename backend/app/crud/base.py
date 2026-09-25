"""Typed asynchronous CRUD primitives.

Repositories flush pending changes but never commit. The HTTP/service layer owns
the transaction so a business change and its audit entry succeed or fail together.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, ClassVar, cast

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select
from sqlalchemy.sql.base import ExecutableOption

from app.core.errors import UnprocessableError
from app.models.base import Base

type ModelData = Mapping[str, object]


def contains_pattern(value: str) -> str:
    """Build a literal SQL LIKE contains pattern with wildcard characters escaped."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


_RELATION_LABELS = {"role": "角色", "permission": "权限"}


class RelatedObjectsNotFoundError(UnprocessableError):
    """Raised when a relation assignment contains unknown or deleted IDs."""

    def __init__(self, relation: str, missing_ids: Iterable[int]) -> None:
        self.relation = relation
        self.missing_ids = tuple(sorted(set(missing_ids)))
        super().__init__(
            f"以下{_RELATION_LABELS.get(relation, relation)}不存在或已删除",
            data={"relation": relation, "missing_ids": list(self.missing_ids)},
        )


class CRUDBase[ModelT: Base]:
    """Common asynchronous operations for one ORM model."""

    model: type[ModelT]
    updatable_fields: ClassVar[frozenset[str]] = frozenset()

    def _column(self, name: str) -> InstrumentedAttribute[Any]:
        return cast("InstrumentedAttribute[Any]", getattr(self.model, name))

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

    async def get_including_deleted(self, db: AsyncSession, id: int) -> ModelT | None:
        """Return one record by primary key regardless of soft-deletion state."""
        result = await db.execute(select(self.model).where(self._id_column() == id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_data: ModelData) -> ModelT:
        """Add a new record and flush without committing."""
        db_obj = self.model(**dict(obj_data))
        db.add(db_obj)
        await db.flush()
        return db_obj

    def apply_update(self, obj: ModelT, data: ModelData) -> None:
        """Assign only whitelisted fields; unknown or protected keys are ignored."""
        for field in self.updatable_fields & data.keys():
            setattr(obj, field, data[field])

    async def paginate(
        self,
        db: AsyncSession,
        stmt: Select[tuple[ModelT]],
        *,
        order_by: Sequence[ColumnElement[Any]],
        skip: int,
        limit: int,
    ) -> tuple[list[ModelT], int]:
        """Count the filtered statement, then fetch one deterministic page."""
        total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        rows = await db.scalars(stmt.order_by(*order_by).offset(skip).limit(limit))
        return list(rows.unique().all()), total or 0


class SoftDeleteCRUD[ModelT: Base](CRUDBase[ModelT]):
    """Recycle-bin operations shared by every soft-deletable model.

    Subclasses set ``search_columns`` and override ``load_options`` so that
    recycle-bin responses have their relationships loaded (every relationship in
    this project is ``lazy="raise"``).
    """

    search_columns: ClassVar[tuple[str, ...]] = ()

    def load_options(self) -> Sequence[ExecutableOption]:
        """Eager-load options applied to recycle-bin listings and restores."""
        return ()

    def _deleted_statement(self) -> Select[tuple[ModelT]]:
        return select(self.model).where(self._column("is_deleted").is_(True))

    async def get_deleted(self, db: AsyncSession, id: int) -> ModelT | None:
        """Return one record that is currently in the recycle bin."""
        result = await db.execute(self._deleted_statement().where(self._id_column() == id))
        return result.scalar_one_or_none()

    async def get_deleted_multi(
        self,
        db: AsyncSession,
        *,
        search: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[ModelT], int]:
        """Return a page of soft-deleted records, most recently changed first."""
        stmt = self._deleted_statement().options(*self.load_options())
        if search and self.search_columns:
            pattern = contains_pattern(search)
            stmt = stmt.where(
                or_(
                    *(
                        self._column(name).ilike(pattern, escape="\\")
                        for name in self.search_columns
                    )
                )
            )
        return await self.paginate(
            db,
            stmt,
            order_by=(self._column("updated_at").desc(), self._id_column().desc()),
            skip=skip,
            limit=limit,
        )

    async def restore(self, db: AsyncSession, id: int) -> ModelT | None:
        """Bring a record back from the recycle bin under a non-key row lock."""
        stmt = (
            self._deleted_statement()
            .where(self._id_column() == id)
            .options(*self.load_options())
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        obj = (await db.execute(stmt)).scalar_one_or_none()
        if obj is None:
            return None
        setattr(obj, self._column("is_deleted").key, False)
        await db.flush()
        return obj

    async def hard_delete(self, db: AsyncSession, id: int) -> bool:
        """Permanently remove a record that is already in the recycle bin."""
        stmt = (
            self._deleted_statement()
            .where(self._id_column() == id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        obj = (await db.execute(stmt)).scalar_one_or_none()
        if obj is None:
            return False
        await db.delete(obj)
        await db.flush()
        return True
