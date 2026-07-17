"""
Async Redis connection manager.

Provides a shared connection pool, FastAPI dependency injection, and a
health check used by ``GET /health`` and ``GET /api/v1/health``.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Singleton Redis client backed by a shared connection pool."""

    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None

    @classmethod
    async def connect(cls) -> Redis:
        """Create the pool and client if they do not already exist."""
        if cls._client is None:
            logger.info("Initializing Redis connection pool...")
            cls._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            client = Redis(connection_pool=cls._pool)
            try:
                await client.ping()
            except Exception:
                await client.aclose()
                await cls._pool.disconnect()
                cls._pool = None
                raise
            cls._client = client
            logger.info("Redis connected | url=%s", settings.REDIS_URL.split("@")[-1])
        return cls._client

    @classmethod
    def get_client(cls) -> Redis:
        """
        Return the Redis client.

        Raises
        ------
        RuntimeError
            If ``connect()`` has not been called during lifespan startup.
        """
        if cls._client is None:
            raise RuntimeError(
                "Redis is not initialized. Call RedisManager.connect() first."
            )
        return cls._client

    @classmethod
    async def close(cls) -> None:
        """Close the client and disconnect the pool."""
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
        if cls._pool is not None:
            await cls._pool.disconnect()
            cls._pool = None
        logger.info("Redis connection closed")

    @classmethod
    async def check_health(cls) -> bool:
        """Return True when Redis responds to PING."""
        try:
            if cls._client is None:
                return False
            return bool(await cls._client.ping())
        except Exception as exc:  # noqa: BLE001
            logger.error("Redis health check failed: %s", exc)
            return False


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that yields the shared Redis client."""
    yield RedisManager.get_client()
