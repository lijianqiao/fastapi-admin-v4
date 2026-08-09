"""Create PostgreSQL trigram indexes without blocking table writes.

Revision ID: b7d9e5f3a012
Revises: a6c8f4d2e901
Create Date: 2026-08-09 13:00:00+00:00
"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "b7d9e5f3a012"
down_revision: str | None = "a6c8f4d2e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before removing production indexes."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


INDEXES = (
    ("ix_users_username_trgm", "users", "username"),
    ("ix_users_email_trgm", "users", "email"),
    ("ix_roles_name_trgm", "roles", "name"),
    ("ix_permissions_name_trgm", "permissions", "name"),
    ("ix_permissions_code_trgm", "permissions", "code"),
)


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    """Create rerunnable concurrent GIN indexes in an index-only revision."""
    if not _is_postgresql():
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        for name, table, column in INDEXES:
            # A failed concurrent build can leave an INVALID index. Dropping by
            # managed name makes this revision safely rerunnable before stamping.
            op.drop_index(
                name,
                table_name=table,
                if_exists=True,
                postgresql_concurrently=True,
            )
            op.create_index(
                name,
                table,
                [column],
                postgresql_using="gin",
                postgresql_ops={column: "gin_trgm_ops"},
                postgresql_concurrently=True,
            )


def downgrade() -> None:
    """Drop the PostgreSQL-only search indexes without blocking writes."""
    _require_destructive_downgrade()
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        for name, table, _column in reversed(INDEXES):
            op.drop_index(
                name,
                table_name=table,
                if_exists=True,
                postgresql_concurrently=True,
            )
