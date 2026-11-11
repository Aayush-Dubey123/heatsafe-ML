from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import backend.core.models.health_model  # noqa: F401 - registers tables on Base.metadata
import backend.core.models.product_model  # noqa: F401 - registers tables on Base.metadata
from backend.core.config.settings import get_settings
from backend.core.database.base_class import Base, migration_name_filter

POSTGRES_CONNECT_TIMEOUT_SECONDS = 10

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# A caller (e.g. the test suite) may pass an explicit URL; otherwise use settings.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Emit migration SQL to stdout without a live database connection.

    Used for reviewing the SQL a migration would run (`alembic upgrade head --sql`).
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Apply migrations against the configured database inside a transaction.

    Batch mode is enabled so the same migrations also run on SQLite in tests.
    """
    url = config.get_main_option("sqlalchemy.url") or ""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={} if url.startswith("sqlite") else {"connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS},
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            include_name=migration_name_filter(connection),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
