"""Alembic environment using psycopg's synchronous migration connection."""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import Connection, engine_from_config, make_url, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config


def _sync_url(url: str) -> str:
    """Require the production database and select psycopg's sync facade."""
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "Alembic migrations require PostgreSQL; SQLite is test-only and uses create_all"
        )
    raw_options = parsed_url.query.get("options")
    option_values = (raw_options,) if isinstance(raw_options, str) else raw_options or ()
    if any("search_path" in value.casefold() for value in option_values):
        raise RuntimeError(
            "Alembic does not accept URL-level search_path overrides; "
            "use a separate temporary database for migration tests"
        )
    parsed_url = parsed_url.set(drivername="postgresql+psycopg")
    return parsed_url.render_as_string(hide_password=False)


database_url = _sync_url(settings.migration_database_url)
# ConfigParser treats percent signs as interpolation markers. Escaping here keeps
# URL-encoded database passwords such as ``%40`` valid.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
TRIGRAM_INDEX_NAMES = {
    "ix_permissions_code_trgm",
    "ix_permissions_name_trgm",
    "ix_roles_name_trgm",
    "ix_users_email_trgm",
    "ix_users_username_trgm",
}


def include_object(
    _object: object,
    name: str | None,
    type_: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    """Ignore PostgreSQL-only trigram indexes on other dialects."""
    if type_ == "table" and name == "alembic_version":
        return False
    return not (
        type_ == "index"
        and name in TRIGRAM_INDEX_NAMES
        and context.get_context().dialect.name != "postgresql"
    )


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.execute("SET search_path TO public, pg_catalog")
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on the synchronous facade of an async connection."""
    connection.exec_driver_sql("SET search_path TO public, pg_catalog")
    active_schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    connection.commit()
    if active_schema != "public":
        raise RuntimeError("Alembic refused to run outside the public schema")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations synchronously to avoid platform event-loop constraints."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
