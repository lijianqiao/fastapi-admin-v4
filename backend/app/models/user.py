"""User model and the user-role association table."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.role import Role


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    ),
    Index("ix_user_roles_role_id", "role_id"),
)


class User(Base, TimestampMixin):
    """Application user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        Index(
            "ix_users_username_trgm",
            "username",
            postgresql_using="gin",
            postgresql_ops={"username": "gin_trgm_ops"},
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_users_email_trgm",
            "email",
            postgresql_using="gin",
            postgresql_ops={"email": "gin_trgm_ops"},
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    roles: Mapped[list["Role"]] = relationship(  # noqa: UP037
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="raise",
        order_by="Role.id",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r}, email={self.email!r})>"
