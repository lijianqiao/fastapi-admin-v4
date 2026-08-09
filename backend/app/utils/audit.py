"""Transactional audit-log helper."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.audit_log import audit_log_crud
from app.schemas.audit_log import AuditLogCreate


async def log_audit(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    target: str = "",
    detail: str = "",
    ip: str = "",
) -> None:
    """Stage an audit record in the caller's transaction.

    The repository only flushes. The endpoint commits once after both its
    business mutation and this record have succeeded, preventing partial writes.
    """
    log_data = AuditLogCreate(
        user_id=user_id,
        action=action,
        target=target,
        detail=detail,
        ip=ip,
    )
    await audit_log_crud.create(db, log_data.model_dump())
