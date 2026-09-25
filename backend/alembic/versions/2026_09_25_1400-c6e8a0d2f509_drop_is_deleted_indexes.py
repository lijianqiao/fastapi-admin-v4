"""Drop low-selectivity single-column is_deleted indexes without blocking writes.

Revision ID: c6e8a0d2f509
Revises: b5d7f9c1e408
Create Date: 2026-09-25 14:00:00+00:00
"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "c6e8a0d2f509"
down_revision: str | None = "b5d7f9c1e408"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    ("ix_users_is_deleted", "users"),
    ("ix_roles_is_deleted", "roles"),
    ("ix_permissions_is_deleted", "permissions"),
)


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before recreating production indexes."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    """A boolean column that is false for nearly every row is never worth an index."""
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        for name, table in INDEXES:
            op.drop_index(name, table_name=table, if_exists=True, postgresql_concurrently=True)


def downgrade() -> None:
    """Recreate the original indexes."""
    _require_destructive_downgrade()
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        for name, table in INDEXES:
            op.drop_index(name, table_name=table, if_exists=True, postgresql_concurrently=True)
            op.create_index(name, table, ["is_deleted"], postgresql_concurrently=True)
