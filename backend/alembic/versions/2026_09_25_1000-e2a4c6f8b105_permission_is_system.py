"""Mark registry-owned permissions as system permissions.

Revision ID: e2a4c6f8b105
Revises: d9f2b3c5a104
Create Date: 2026-09-25 10:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "e2a4c6f8b105"
down_revision: str | None = "d9f2b3c5a104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 与 app.core.permissions.Perm 在本迁移发布时的取值一致；迁移不得 import 应用代码。
SYSTEM_PERMISSION_CODES = (
    "user:read",
    "user:create",
    "user:update",
    "user:delete",
    "user:assign",
    "user:reset_password",
    "role:read",
    "role:create",
    "role:update",
    "role:delete",
    "role:assign",
    "permission:read",
    "permission:create",
    "permission:update",
    "permission:delete",
    "audit:read",
)


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before applying downgrade operations."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


def upgrade() -> None:
    """Add the system flag (metadata-only on PostgreSQL 11+) and mark registry codes."""
    op.add_column(
        "permissions",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    permissions = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("is_system", sa.Boolean()),
    )
    op.execute(
        permissions.update()
        .where(permissions.c.code.in_(SYSTEM_PERMISSION_CODES))
        .values(is_system=True)
    )


def downgrade() -> None:
    """Drop the system flag."""
    _require_destructive_downgrade()
    op.drop_column("permissions", "is_system")
