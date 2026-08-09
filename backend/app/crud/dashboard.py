"""Dashboard aggregate queries."""

from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


class DashboardCounts(TypedDict):
    user_count: int
    role_count: int
    permission_count: int
    active_user_count: int


class CRUDDashboard:
    """Fetch dashboard counters in one database round trip."""

    async def get_counts(self, db: AsyncSession) -> DashboardCounts:
        user_counts = (
            select(
                func.count(User.id).label("user_count"),
                func.count(User.id).filter(User.is_active.is_(True)).label("active_user_count"),
            )
            .where(User.is_deleted.is_(False))
            .subquery()
        )
        role_count = select(func.count(Role.id)).where(Role.is_deleted.is_(False)).scalar_subquery()
        permission_count = (
            select(func.count(Permission.id))
            .where(Permission.is_deleted.is_(False))
            .scalar_subquery()
        )
        result = await db.execute(
            select(
                user_counts.c.user_count,
                role_count.label("role_count"),
                permission_count.label("permission_count"),
                user_counts.c.active_user_count,
            )
        )
        row = result.one()
        return {
            "user_count": row.user_count,
            "role_count": row.role_count,
            "permission_count": row.permission_count,
            "active_user_count": row.active_user_count,
        }


dashboard_crud = CRUDDashboard()
