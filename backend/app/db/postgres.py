import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection pooling configurations for production-level workloads
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,          # Standard production connection limit
    max_overflow=10,       # Allow burst of connections above the standard pool size
    pool_recycle=3600,     # Recycle connections after 1 hour to prevent stale connections
    pool_pre_ping=True,    # Ping connection before utilizing to verify health
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_postgres() -> None:
    """Verify PostgreSQL connection on startup."""
    try:
        async with engine.begin() as conn:
            # Run simple query to check connection state
            await conn.execute("SELECT 1")
        logger.info("Successfully connected to PostgreSQL database (Async Engine)")
    except Exception as e:
        logger.error(f"PostgreSQL connection failure: {e}", exc_info=True)
        raise e
