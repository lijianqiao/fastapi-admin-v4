"""Build indexes on existing tables without blocking writes.

Revision ID: c8e1a2f4b903
Revises: b7d9e5f3a012
Create Date: 2026-08-09 14:00:00+00:00
"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "c8e1a2f4b903"
down_revision: str | None = "b7d9e5f3a012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before replacing production indexes."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


CURRENT_INDEXES = (
    ("ix_audit_logs_action_created_at", "audit_logs", ("action", "created_at")),
    ("ix_audit_logs_user_id_created_at", "audit_logs", ("user_id", "created_at")),
    ("ix_user_roles_role_id", "user_roles", ("role_id",)),
    ("ix_role_permissions_permission_id", "role_permissions", ("permission_id",)),
)
LEGACY_AUDIT_INDEXES = (
    ("ix_audit_logs_action", "audit_logs", ("action",)),
    ("ix_audit_logs_user_id", "audit_logs", ("user_id",)),
)


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _drop_indexes(
    indexes: tuple[tuple[str, str, tuple[str, ...]], ...],
) -> None:
    for name, table, _columns in indexes:
        op.drop_index(
            name,
            table_name=table,
            if_exists=True,
            postgresql_concurrently=True,
        )


def _create_indexes(
    indexes: tuple[tuple[str, str, tuple[str, ...]], ...],
) -> None:
    for name, table, columns in indexes:
        # A killed concurrent build can leave an INVALID index under the
        # managed name. Dropping first makes a rerun repair that state.
        op.drop_index(
            name,
            table_name=table,
            if_exists=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            name,
            table,
            list(columns),
            unique=False,
            postgresql_concurrently=True,
        )


def upgrade() -> None:
    """Replace legacy indexes and add reverse/composite indexes online."""
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        # Keep the legacy lookup paths until every replacement is usable.
        _create_indexes(CURRENT_INDEXES)
        _drop_indexes(LEGACY_AUDIT_INDEXES)


def downgrade() -> None:
    """Restore the original audit indexes without blocking table writes."""
    _require_destructive_downgrade()
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        # Restore the legacy lookup paths before removing their replacements.
        _create_indexes(LEGACY_AUDIT_INDEXES)
        _drop_indexes(CURRENT_INDEXES)
