# file_name: session.py

"""Database engine and session management.

``docs/04_backend/26_PERSISTENCE_LAYER.md`` places all database access behind
repositories, and ``instructions/02_BACKEND_RULES.md`` section 8 requires
sessions to be supplied by dependency injection rather than by global state.

The engine is created lazily so the application can start without a database,
which is how the backend runs before ``DATABASE_URL`` is configured.
"""

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, get_settings
from app.shared.exceptions import DatabaseUnavailableError

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for every database model."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_database(url: str, echo: bool = False) -> AsyncEngine:
    """Create the engine and session factory for a database URL.

    Args:
        url: An async SQLAlchemy URL, such as ``postgresql+asyncpg://...``.
        echo: Whether to log emitted SQL. Never enable in production.

    Returns:
        The configured engine.
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        future=True,
    )
    _session_factory = async_sessionmaker(
        _engine, expire_on_commit=False, class_=AsyncSession
    )
    logger.info("Database engine configured.")
    return _engine


def configure_from_settings(settings: Settings | None = None) -> AsyncEngine | None:
    """Configure the database from application settings, if one is set.

    Returns:
        The engine, or ``None`` when no database is configured.
    """
    settings = settings or get_settings()
    if settings.database_url is None:
        logger.warning("No database configured; persistence is unavailable.")
        return None
    return configure_database(settings.database_url.get_secret_value())


def get_engine() -> AsyncEngine:
    """Return the configured engine.

    Raises:
        DatabaseUnavailableError: If no database has been configured.
    """
    if _engine is None:
        raise DatabaseUnavailableError()
    return _engine


def is_configured() -> bool:
    """Report whether a database has been configured."""
    return _session_factory is not None


async def dispose_database() -> None:
    """Close every pooled connection, on shutdown."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine disposed.")
    _engine = None
    _session_factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for one request.

    The session is committed when the request succeeds and rolled back when it
    raises, so a failed request never leaves a partial write behind.

    Raises:
        DatabaseUnavailableError: If no database has been configured.
    """
    if _session_factory is None:
        raise DatabaseUnavailableError()

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
