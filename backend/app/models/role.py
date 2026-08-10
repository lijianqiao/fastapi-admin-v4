"""Role model and the role-permission association table."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
    literal,
)
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.permission import Permission
    from app.models.user import User


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    ),
    Index("ix_role_permissions_permission_id", "permission_id"),
)


class Role(Base, TimestampMixin):
    """RBAC role."""

    __tablename__ = "roles"
    __table_args__ = (
        Index(
            "ix_roles_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    permissions: Mapped[list["Permission"]] = relationship(  # noqa: UP037
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="raise",
        order_by="Permission.id",
        passive_deletes=True,
    )

    users: Mapped[list["User"]] = relationship(  # noqa: UP037
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="raise",
        order_by="User.id",
        passive_deletes=True,
    )

    # Query-only value populated by CRUDRole list/detail statements.
    _user_count: Mapped[int | None] = query_expression(literal(0))

    @property
    def user_count(self) -> int:
        """Return the loaded aggregate, or zero for a newly-created role."""
        return self._user_count or 0

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name!r})>"
