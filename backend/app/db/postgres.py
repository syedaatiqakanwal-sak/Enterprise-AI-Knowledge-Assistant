"""
Async PostgreSQL engine and session factory (SQLAlchemy 2.0).

Connection pooling is configured via Settings so production can tune
``DB_POOL_SIZE`` / ``DB_MAX_OVERFLOW`` without code changes.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and settings.is_development,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    connect_args={"timeout": 5},
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_postgres() -> None:
    """Verify the PostgreSQL connection during application startup."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info(
        "PostgreSQL connected | host=%s | db=%s | pool_size=%s",
        settings.POSTGRES_HOST,
        settings.POSTGRES_DB,
        settings.DB_POOL_SIZE,
    )


async def check_postgres_health() -> bool:
    """Return True when PostgreSQL accepts a simple ping query."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health checks must never raise
        logger.error("PostgreSQL health check failed: %s", exc)
        return False


async def close_postgres() -> None:
    """Dispose the engine connection pool on shutdown."""
    await engine.dispose()
    logger.info("PostgreSQL engine disposed")


def get_engine() -> AsyncEngine:
    """Expose the shared async engine (used by Alembic and diagnostics)."""
    return engine
