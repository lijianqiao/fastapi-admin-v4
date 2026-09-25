"""Index audit listing order and actor-name search without blocking writes.

Revision ID: a4c6e8b0d307
Revises: f3b5d7a9c206
Create Date: 2026-09-25 12:00:00+00:00
"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "a4c6e8b0d307"
down_revision: str | None = "f3b5d7a9c206"
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


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _drop(name: str) -> None:
    op.drop_index(name, table_name="audit_logs", if_exists=True, postgresql_concurrently=True)


def upgrade() -> None:
    """Replace the created_at index with (created_at, id) and add trigram search."""
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        # 先删同名索引：被中断的并发建索引可能留下 INVALID 索引
        _drop("ix_audit_logs_created_at_id")
        op.create_index(
            "ix_audit_logs_created_at_id",
            "audit_logs",
            ["created_at", "id"],
            postgresql_concurrently=True,
        )
        _drop("ix_audit_logs_actor_username_trgm")
        op.create_index(
            "ix_audit_logs_actor_username_trgm",
            "audit_logs",
            ["actor_username"],
            postgresql_using="gin",
            postgresql_ops={"actor_username": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        # 替代索引可用之后再删除旧索引
        _drop("ix_audit_logs_created_at")


def downgrade() -> None:
    """Restore the single-column created_at index."""
    _require_destructive_downgrade()
    if not _is_postgresql():
        return

    with op.get_context().autocommit_block():
        _drop("ix_audit_logs_created_at")
        op.create_index(
            "ix_audit_logs_created_at",
            "audit_logs",
            ["created_at"],
            postgresql_concurrently=True,
        )
        _drop("ix_audit_logs_actor_username_trgm")
        _drop("ix_audit_logs_created_at_id")
