"""Add is_active status flags to roles and permissions.

Revision ID: d9f2b3c5a104
Revises: c8e1a2f4b903
Create Date: 2026-08-10 13:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "d9f2b3c5a104"
down_revision: str | None = "c8e1a2f4b903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before applying downgrade operations."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


def upgrade() -> None:
    """Enable status toggles for roles and permissions (default enabled)."""
    op.add_column(
        "roles",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "permissions",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    # Keep application defaults; drop DB-only defaults after backfill.
    op.alter_column("roles", "is_active", server_default=None)
    op.alter_column("permissions", "is_active", server_default=None)


def downgrade() -> None:
    """Remove role/permission status columns."""
    _require_destructive_downgrade()
    op.drop_column("permissions", "is_active")
    op.drop_column("roles", "is_active")
