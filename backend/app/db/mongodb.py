import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger(__name__)

class MongoDBManager:
    """Singleton MongoDB Client Connection Manager using Motor."""
    _client: AsyncIOMotorClient = None
    _db = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        """Returns the singleton Motor client instance."""
        if cls._client is None:
            logger.info("Initializing MongoDB client...")
            cls._client = AsyncIOMotorClient(settings.MONGO_URL)
        return cls._client

    @classmethod
    def get_db(cls):
        """Returns the active MongoDB database instance."""
        if cls._db is None:
            client = cls.get_client()
            cls._db = client[settings.MONGO_DB]
        return cls._db

    @classmethod
    async def close_connection(cls) -> None:
        """Close connection pools gracefully."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB connection closed.")

    @classmethod
    async def verify_health(cls) -> bool:
        """Verify MongoDB database connection health."""
        try:
            client = cls.get_client()
            # The admin database ping command is standard for checking Mongo availability
            await client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health verification failure: {e}")
            return False

# FastAPI dependency to yield MongoDB instance
async def get_mongo_db():
    """Dependency injection wrapper for MongoDB session database context."""
    return MongoDBManager.get_db()
