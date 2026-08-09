"""可撤销、可轮换的 refresh token 会话模型。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshSession(Base):
    """仅保存 refresh token 摘要及轮换状态，不保存原始 token。"""

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        Index("ix_refresh_sessions_family_id", "family_id"),
        Index("ix_refresh_sessions_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    family_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("refresh_session_families.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
