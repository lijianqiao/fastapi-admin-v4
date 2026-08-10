"""Asynchronous audit log repository."""

from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase, contains_pattern
from app.models.audit_log import AuditLog
from app.models.user import User


class AuditLogItem(TypedDict):
    id: int
    user_id: int | None
    username: str | None
    action: str
    target: str
    detail: str
    ip: str
    created_at: datetime


class RecentLoginItem(TypedDict):
    id: int
    user_id: int | None
    username: str | None
    action: str
    ip: str
    created_at: datetime


class CRUDAuditLog(CRUDBase[AuditLog]):
    """Append and query audit records."""

    model = AuditLog

    async def get_multi_filtered(
        self,
        db: AsyncSession,
        user_id: int | None = None,
        username: str | None = None,
        action: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLogItem], int]:
        """Return a stable audit page with the actor's current username."""
        filters = []
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if username:
            filters.append(
                User.username.ilike(contains_pattern(username), escape="\\")
            )
        if action:
            filters.append(AuditLog.action == action)

        stmt = (
            select(
                AuditLog.id,
                AuditLog.user_id,
                User.username.label("username"),
                AuditLog.action,
                AuditLog.target,
                AuditLog.detail,
                AuditLog.ip,
                AuditLog.created_at,
            )
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(*filters)
        )

        # Username filter needs the join for counting; otherwise count the base table.
        if username:
            count_stmt = (
                select(func.count())
                .select_from(AuditLog)
                .outerjoin(User, AuditLog.user_id == User.id)
                .where(*filters)
            )
        else:
            count_stmt = select(func.count()).select_from(AuditLog).where(*filters)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        page_stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        rows_result = await db.execute(page_stmt.offset(skip).limit(limit))
        items: list[AuditLogItem] = [
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.username,
                "action": row.action,
                "target": row.target,
                "detail": row.detail,
                "ip": row.ip,
                "created_at": row.created_at,
            }
            for row in rows_result
        ]
        return items, total

    async def get_recent_logins(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> list[RecentLoginItem]:
        """Return only successful login events for the dashboard."""
        stmt = (
            select(
                AuditLog.id,
                AuditLog.user_id,
                User.username.label("username"),
                AuditLog.action,
                AuditLog.ip,
                AuditLog.created_at,
            )
            .outerjoin(User, AuditLog.user_id == User.id)
            .where(AuditLog.action == "login")
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
        rows_result = await db.execute(stmt)
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.username,
                "action": row.action,
                "ip": row.ip,
                "created_at": row.created_at,
            }
            for row in rows_result
        ]


audit_log_crud = CRUDAuditLog()
