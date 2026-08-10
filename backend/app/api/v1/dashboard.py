"""Dashboard aggregate endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.crud.audit_log import audit_log_crud
from app.crud.dashboard import dashboard_crud
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.common import ResponseEnvelope, success_response
from app.schemas.dashboard import DashboardData, DashboardStats, RecentLoginItem

router = APIRouter()


@router.get("", response_model=ResponseEnvelope[DashboardData])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseEnvelope[DashboardData]:
    """Return shared counters and gate audit-derived login data separately."""
    stats = DashboardStats.model_validate(await dashboard_crud.get_counts(db))

    can_read_audit = await user_crud.has_permission_or_superuser(db, current_user, "audit:read")

    recent_logs: list[RecentLoginItem] = []
    if can_read_audit:
        recent_logs = [
            RecentLoginItem.model_validate(item)
            for item in await audit_log_crud.get_recent_logins(db, limit=10)
        ]

    return success_response(DashboardData(stats=stats, recent_logs=recent_logs))
