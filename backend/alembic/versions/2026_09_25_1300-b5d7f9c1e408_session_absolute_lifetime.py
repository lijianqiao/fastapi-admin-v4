"""Cap every refresh-session family with an absolute lifetime.

Revision ID: b5d7f9c1e408
Revises: a4c6e8b0d307
Create Date: 2026-09-25 13:00:00+00:00

Existing families get created_at + 30 days (the default setting), but never less
than their current expiry, so deploying this revision does not log anyone out.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "b5d7f9c1e408"
down_revision: str | None = "a4c6e8b0d307"
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
    """Add, backfill, then require the absolute expiry."""
    op.add_column(
        "refresh_session_families",
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE refresh_session_families "
        "SET absolute_expires_at = GREATEST(created_at + INTERVAL '30 days', expires_at) "
        "WHERE absolute_expires_at IS NULL"
    )
    op.alter_column("refresh_session_families", "absolute_expires_at", nullable=False)


def downgrade() -> None:
    """Drop the absolute expiry."""
    _require_destructive_downgrade()
    op.drop_column("refresh_session_families", "absolute_expires_at")
