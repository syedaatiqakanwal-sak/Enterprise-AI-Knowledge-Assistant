"""
Health-check application service.

Orchestrates dependency probes and maps results into the public schema.
Lives in the services layer so the API endpoint stays thin (Clean Architecture).
"""

from __future__ import annotations

import logging
from typing import Literal

from app.core.config import settings
from app.db.mongodb import MongoDBManager
from app.db.postgres import check_postgres_health
from app.db.redis import RedisManager
from app.schemas.health import HealthResponse, ServicesHealth

logger = logging.getLogger(__name__)


class HealthService:
    """Aggregate health status for the backend and its data stores."""

    async def check(self) -> HealthResponse:
        """Probe Postgres, MongoDB, and Redis; return a typed health payload."""
        postgres_ok = await check_postgres_health()
        mongo_ok = await MongoDBManager.check_health()
        redis_ok = await RedisManager.check_health()

        services = ServicesHealth(
            postgres="up" if postgres_ok else "down",
            mongodb="up" if mongo_ok else "down",
            redis="up" if redis_ok else "down",
        )

        overall: Literal["healthy", "degraded", "unhealthy"]
        if postgres_ok and mongo_ok and redis_ok:
            overall = "healthy"
        elif not postgres_ok and not mongo_ok and not redis_ok:
            overall = "unhealthy"
        else:
            overall = "degraded"

        if overall != "healthy":
            logger.warning("Health check %s | services=%s", overall, services.model_dump())

        return HealthResponse(
            status=overall,
            backend="up",
            services=services,
            version=settings.PROJECT_VERSION,
            environment=settings.ENVIRONMENT.value,
        )


health_service = HealthService()
