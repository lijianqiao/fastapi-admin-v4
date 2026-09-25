"""Keep the permissions table in step with the code-level registry."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_META
from app.models.permission import Permission


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Rows inserted or repaired by one synchronization."""

    created: int
    updated: int


async def sync_system_permissions(db: AsyncSession) -> SyncResult:
    """Insert missing registry permissions and re-mark existing ones as live system rows.

    Existing names and descriptions are left untouched so administrators can relabel
    them; the code, the system flag and the non-deleted state are owned by the
    registry. Flushes only; the caller commits.
    """
    codes = [perm.value for perm in PERMISSION_META]
    rows = await db.scalars(
        select(Permission).where(Permission.code.in_(codes)).with_for_update()
    )
    existing = {permission.code: permission for permission in rows.all()}

    created = 0
    updated = 0
    for perm, meta in PERMISSION_META.items():
        permission = existing.get(perm.value)
        if permission is None:
            db.add(
                Permission(
                    code=perm.value,
                    name=meta.name,
                    module=meta.module,
                    description=meta.description,
                    is_system=True,
                )
            )
            created += 1
        elif not permission.is_system or permission.is_deleted:
            permission.is_system = True
            permission.is_deleted = False
            updated += 1

    await db.flush()
    return SyncResult(created=created, updated=updated)
