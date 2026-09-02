"""
Alembic migration environment — configures how migrations connect to the DB.

KEY POINTS:
- We use ASYNC migrations because our app uses async SQLAlchemy.
- The database URL comes from our app's Settings (not duplicated in alembic.ini).
- We import ALL models so Alembic can detect schema changes and auto-generate
  migration scripts via: alembic revision --autogenerate -m "description"

WHY ALEMBIC (not create_all):
- create_all() can create tables but can't ALTER them later.
- Alembic tracks every schema change as a versioned migration script.
- You can upgrade, downgrade, and review the history of schema changes.
- Essential for production deployments where you can't just drop and recreate.
"""

import asyncio
import sys
from pathlib import Path
from logging.config import fileConfig

# Add the backend directory to sys.path so we can import 'app'
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import our app's config and models
from app.config import get_settings
from app.database import Base

# Import ALL models here so Alembic sees them in Base.metadata
# Without these imports, Alembic won't detect the tables.
from app.models.user import User        # noqa: F401
from app.models.resume import Resume    # noqa: F401
from app.models.job import Job          # noqa: F401
from app.models.match import Match      # noqa: F401

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic compares against to detect schema changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL without connecting to DB.
    Useful for reviewing migration SQL before applying it.
    """
    url = get_settings().DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations against an active database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations.

    We build the engine config from our app settings so the DB URL
    is defined in exactly one place (.env).
    """
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the actual database."""
    asyncio.run(run_async_migrations())


# Decide which mode to run in
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
