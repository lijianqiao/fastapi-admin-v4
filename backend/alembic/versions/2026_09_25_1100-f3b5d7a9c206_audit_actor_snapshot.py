"""Snapshot the audit actor and detach audit rows from the users table.

Revision ID: f3b5d7a9c206
Revises: e2a4c6f8b105
Create Date: 2026-09-25 11:00:00+00:00

The backfill UPDATE rewrites every audit row once. On a large table run it in a
maintenance window; the migrator role owns the table, so it is allowed to update
it even though the runtime role is append-only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "f3b5d7a9c206"
down_revision: str | None = "e2a4c6f8b105"
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
    """Add the snapshot column, backfill it, then drop the SET NULL foreign key."""
    op.add_column("audit_logs", sa.Column("actor_username", sa.String(50), nullable=True))
    op.execute(
        "UPDATE audit_logs AS a SET actor_username = u.username "
        "FROM users AS u WHERE u.id = a.user_id AND a.actor_username IS NULL"
    )
    # init 迁移中的外键未命名，PostgreSQL 默认名为 <表>_<列>_fkey
    op.execute("ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey")


def downgrade() -> None:
    """Restore the foreign key (orphaned references are nulled first) and drop the snapshot."""
    _require_destructive_downgrade()
    op.execute(
        "UPDATE audit_logs SET user_id = NULL "
        "WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)"
    )
    op.create_foreign_key(
        "audit_logs_user_id_fkey",
        "audit_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_column("audit_logs", "actor_username")
