"""Read-only asynchronous audit-log endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.crud.audit_log import audit_log_crud
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.schemas.common import PaginatedData, ResponseEnvelope, paginated_response

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[AuditLogResponse]],
)
async def list_audit_logs(
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None, gt=0),
    username: str | None = Query(default=None, min_length=1, max_length=50),
    action: str | None = Query(default=None, min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
) -> ResponseEnvelope[PaginatedData[AuditLogResponse]]:
    """Return a stable audit page; audit records are never mutable via the API."""
    logs, total = await audit_log_crud.get_multi_filtered(
        db,
        user_id=user_id,
        username=username,
        action=action,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = [AuditLogResponse.model_validate(log) for log in logs]
    return paginated_response(items, total, page, page_size)
