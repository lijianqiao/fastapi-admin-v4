"""Add revocable session families and production query indexes.

Revision ID: a6c8f4d2e901
Revises: 81756b289753
Create Date: 2026-08-09 12:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "a6c8f4d2e901"
down_revision: str | None = "81756b289753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_destructive_downgrade() -> None:
    """Require an explicit opt-in before removing authentication state."""
    arguments = context.get_x_argument(as_dictionary=True)
    if arguments.get("allow-destructive", "").casefold() != "true":
        raise RuntimeError(
            "Destructive downgrade blocked; rerun with "
            "'-x allow-destructive=true' after verifying the database target"
        )


def upgrade() -> None:
    """Apply async-auth, audit, association and search performance changes."""
    # Commit the NOT VALID constraints independently so their brief ACCESS
    # EXCLUSIVE locks are released before normalization. Catalog guards make a
    # partially completed, unstamped run retryable.
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $migration$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_users_username_lowercase'
                      AND conrelid = 'users'::regclass
                ) THEN
                    EXECUTE 'ALTER TABLE users ADD CONSTRAINT ck_users_username_lowercase ' ||
                            'CHECK (username = lower(username)) NOT VALID';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_users_email_lowercase'
                      AND conrelid = 'users'::regclass
                ) THEN
                    EXECUTE 'ALTER TABLE users ADD CONSTRAINT ck_users_email_lowercase ' ||
                            'CHECK (email = lower(email)) NOT VALID';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_permissions_code_lowercase'
                      AND conrelid = 'permissions'::regclass
                ) THEN
                    EXECUTE 'ALTER TABLE permissions ADD CONSTRAINT ' ||
                            'ck_permissions_code_lowercase CHECK (code = lower(code)) NOT VALID';
                END IF;
            END
            $migration$;
            """
        )
        # These RBAC identity tables are small and low-write. One short EXCLUSIVE
        # lock permits ordinary SELECT while serializing the final duplicate
        # check, normalization and validation against legacy application writes.
        # Permission precedes User to match permission-write + audit-FK lock order.
        op.execute(
            """
            DO $normalization$
            BEGIN
                LOCK TABLE permissions, users IN EXCLUSIVE MODE;

                IF EXISTS (
                    SELECT lower(username) FROM users
                    GROUP BY lower(username) HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION 'users contain case-insensitive duplicate usernames';
                END IF;
                IF EXISTS (
                    SELECT lower(email) FROM users
                    GROUP BY lower(email) HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION 'users contain case-insensitive duplicate emails';
                END IF;
                IF EXISTS (
                    SELECT lower(code) FROM permissions
                    GROUP BY lower(code) HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION 'permissions contain case-insensitive duplicate codes';
                END IF;

                UPDATE users
                SET username = lower(username), email = lower(email)
                WHERE username IS DISTINCT FROM lower(username)
                   OR email IS DISTINCT FROM lower(email);
                UPDATE permissions
                SET code = lower(code)
                WHERE code IS DISTINCT FROM lower(code);

                EXECUTE 'ALTER TABLE users VALIDATE CONSTRAINT ' ||
                        'ck_users_username_lowercase';
                EXECUTE 'ALTER TABLE users VALIDATE CONSTRAINT ' ||
                        'ck_users_email_lowercase';
                EXECUTE 'ALTER TABLE permissions VALIDATE CONSTRAINT ' ||
                        'ck_permissions_code_lowercase';
            END
            $normalization$;
            """
        )

    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.create_table(
        "refresh_session_families",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_refresh_session_families_user_revoked",
        "refresh_session_families",
        ["user_id", "revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_session_families_expires_at",
        "refresh_session_families",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.Column("replaced_by_jti", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["refresh_session_families.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_sessions_token_hash"),
    )
    op.create_index(
        "ix_refresh_sessions_jti",
        "refresh_sessions",
        ["jti"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_sessions_family_id",
        "refresh_sessions",
        ["family_id"],
        unique=False,
    )
    op.create_index(
        "ix_refresh_sessions_expires_at",
        "refresh_sessions",
        ["expires_at"],
        unique=False,
    )

    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "role_permissions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.alter_column(
        "user_roles",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert to the original stateless authentication schema."""
    _require_destructive_downgrade()
    op.alter_column(
        "user_roles",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "role_permissions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )

    op.drop_index("ix_refresh_sessions_expires_at", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_family_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_jti", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_index(
        "ix_refresh_session_families_expires_at",
        table_name="refresh_session_families",
    )
    op.drop_index(
        "ix_refresh_session_families_user_revoked",
        table_name="refresh_session_families",
    )
    op.drop_table("refresh_session_families")
    op.drop_column("users", "token_version")
    op.drop_constraint("ck_permissions_code_lowercase", "permissions", type_="check")
    op.drop_constraint("ck_users_email_lowercase", "users", type_="check")
    op.drop_constraint("ck_users_username_lowercase", "users", type_="check")
