"""Recycle-bin endpoints shared by every soft-deletable resource."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Audit, DbSession, PageQuery, audited, require_permission
from app.core.errors import NotFoundError
from app.core.permissions import Perm
from app.crud.base import SoftDeleteCRUD
from app.models.user import User
from app.schemas.common import (
    PaginatedData,
    ResponseEnvelope,
    paginated_response,
    success_response,
)

type RecycleGuard = Callable[[AsyncSession, User, Any], Awaitable[None]]


async def allow_all(_db: AsyncSession, _actor: User, _item: Any) -> None:
    """Default guard: no rule beyond the endpoint permission."""


def build_recycle_bin_router(
    *,
    crud: SoftDeleteCRUD[Any],
    list_schema: type[BaseModel],
    detail_schema: type[BaseModel],
    permission: Perm,
    resource: str,
    label: str,
    describe: Callable[[Any], str],
    before_restore: RecycleGuard = allow_all,
    before_purge: RecycleGuard = allow_all,
) -> APIRouter:
    """Create ``GET /deleted``, ``POST /{id}/restore`` and ``DELETE /{id}/purge``.

    Include the returned router *before* any ``/{id}`` route of the resource so that
    ``/deleted`` is not captured by the path parameter.
    """
    router = APIRouter()
    audit_dependency = audited(permission)

    @router.get(
        "/deleted",
        response_model=ResponseEnvelope[PaginatedData[list_schema]],  # type: ignore[valid-type]
    )
    async def list_deleted(
        page: PageQuery,
        db: DbSession,
        _: Annotated[User, Depends(require_permission(permission))],
    ) -> Any:
        items, total = await crud.get_deleted_multi(
            db,
            search=page.search,
            skip=page.skip,
            limit=page.page_size,
        )
        return paginated_response(
            [list_schema.model_validate(item) for item in items],
            total,
            page.page,
            page.page_size,
        )

    @router.post(
        "/{item_id}/restore",
        response_model=ResponseEnvelope[detail_schema],  # type: ignore[valid-type]
    )
    async def restore(
        item_id: Annotated[int, Path(gt=0)],
        audit: Annotated[Audit, Depends(audit_dependency)],
    ) -> Any:
        item = await crud.get_deleted(audit.db, item_id)
        if item is None:
            raise NotFoundError(f"回收站中不存在该{label}")
        await before_restore(audit.db, audit.actor, item)
        restored = await crud.restore(audit.db, item_id)
        if restored is None:
            raise NotFoundError(f"回收站中不存在该{label}")
        await audit.commit(
            f"restore_{resource}",
            f"{resource}:{item_id}",
            f"恢复{label}: {describe(restored)}",
        )
        return success_response(detail_schema.model_validate(restored), message="恢复成功")

    @router.delete("/{item_id}/purge", response_model=ResponseEnvelope[None])
    async def purge(
        item_id: Annotated[int, Path(gt=0)],
        audit: Annotated[Audit, Depends(audit_dependency)],
    ) -> Any:
        item = await crud.get_deleted(audit.db, item_id)
        if item is None:
            raise NotFoundError(f"回收站中不存在该{label}")
        await before_purge(audit.db, audit.actor, item)
        if not await crud.hard_delete(audit.db, item_id):
            raise NotFoundError(f"回收站中不存在该{label}")
        await audit.commit(f"purge_{resource}", f"{resource}:{item_id}", f"永久删除{label}")
        return success_response(None, message="已永久删除")

    return router
