"""
Database connection setup — async SQLAlchemy engine + session factory.

WHY ASYNC SQLALCHEMY:
- FastAPI is an async framework. Using sync DB calls inside async routes would
  block the event loop and degrade performance under concurrent requests.
- asyncpg is the fastest async Postgres driver for Python.

WHY pool_pre_ping:
- Detects stale/broken connections before using them, avoiding errors when
  Postgres restarts or connections time out.

WHY expire_on_commit=False:
- After committing, SQLAlchemy normally "expires" all loaded attributes, meaning
  the next access triggers a lazy load (which doesn't work in async mode without
  an active session). Setting this to False keeps attributes accessible after commit.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Create the async database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,       # Set True to log all SQL (noisy but useful for debugging)
    pool_pre_ping=True,
)

# Session factory — creates new AsyncSession instances
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models inherit from this. Alembic reads Base.metadata to auto-detect
    schema changes and generate migrations.
    """
    pass
