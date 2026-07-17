"""
Async MongoDB connection manager (Motor).

Uses a process-wide singleton client so connection pools are shared across
requests. FastAPI lifespan hooks call ``connect`` / ``disconnect``.
"""

from __future__ import annotations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """Singleton Motor client and database accessor."""

    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    def connect(cls) -> AsyncIOMotorDatabase:
        """Initialize (or reuse) the Motor client and return the app database."""
        if cls._client is None:
            logger.info("Initializing MongoDB Motor client...")
            cls._client = AsyncIOMotorClient(
                settings.MONGO_URL,
                minPoolSize=settings.MONGO_MIN_POOL_SIZE,
                maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
                serverSelectionTimeoutMS=5000,
            )
            cls._db = cls._client[settings.MONGO_DB]
            logger.info("MongoDB client ready | db=%s", settings.MONGO_DB)
        assert cls._db is not None
        return cls._db

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        """Return the singleton Motor client, creating it if needed."""
        if cls._client is None:
            cls.connect()
        assert cls._client is not None
        return cls._client

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Return the configured application database."""
        if cls._db is None:
            return cls.connect()
        return cls._db

    @classmethod
    async def close(cls) -> None:
        """Close the client and reset the singleton state."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB connection closed")

    @classmethod
    async def check_health(cls) -> bool:
        """Ping the MongoDB admin command; return False on any failure."""
        try:
            client = cls.get_client()
            await client.admin.command("ping")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("MongoDB health check failed: %s", exc)
            return False


async def get_mongo_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency that yields the shared MongoDB database."""
    return MongoDBManager.get_db()
