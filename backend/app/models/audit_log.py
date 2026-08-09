"""审计日志模型。

定义 AuditLog ORM 模型，用于记录关键操作日志。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """审计日志模型。

    记录系统中的关键操作，包括操作人、操作类型、目标、详情和 IP 地址。
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_audit_logs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ip: Mapped[str] = mapped_column(String(45), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action!r}, user_id={self.user_id})>"
