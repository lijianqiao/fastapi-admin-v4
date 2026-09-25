"""Asynchronous audit log repository."""

from datetime import datetime
from typing import ClassVar, TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase, contains_pattern
from app.models.audit_log import AuditLog


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

    # 分页总数只数到这里；超过时返回 count_cap + 1，由前端显示"N+"，并拒绝更深的页
    count_cap: ClassVar[int] = 10_000

    async def get_multi_filtered(
        self,
        db: AsyncSession,
        user_id: int | None = None,
        username: str | None = None,
        action: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLogItem], int]:
        """Return a stable audit page using the actor snapshot taken at write time."""
        filters = []
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if username:
            filters.append(
                AuditLog.actor_username.ilike(contains_pattern(username), escape="\\")
            )
        if action:
            filters.append(AuditLog.action == action)

        capped = select(AuditLog.id).where(*filters).limit(self.count_cap + 1).subquery()
        total = (await db.execute(select(func.count()).select_from(capped))).scalar_one()

        stmt = (
            select(
                AuditLog.id,
                AuditLog.user_id,
                AuditLog.actor_username.label("username"),
                AuditLog.action,
                AuditLog.target,
                AuditLog.detail,
                AuditLog.ip,
                AuditLog.created_at,
            )
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(skip)
            .limit(limit)
        )
        rows_result = await db.execute(stmt)
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
                AuditLog.actor_username.label("username"),
                AuditLog.action,
                AuditLog.ip,
                AuditLog.created_at,
            )
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
