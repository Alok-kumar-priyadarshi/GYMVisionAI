# file_name: env.py

"""Alembic environment.

``docs/07_database/40_DATABASE_MIGRATION_STRATEGY.md`` makes migrations the only
way the schema changes. The connection string is read from the application
settings, so no credentials appear in ``alembic.ini`` or in version control.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.infrastructure.database import models  # noqa: F401 - registers tables
from app.infrastructure.database.session import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    """Return the configured database URL.

    Raises:
        RuntimeError: If none is set. Migrations must never invent a target.
    """
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL must be set to run migrations.")
    return settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Emit SQL without connecting, for review before applying."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations on an open connection."""
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect and apply migrations."""
    engine = create_async_engine(database_url(), poolclass=None)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    """Apply migrations against the configured database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
