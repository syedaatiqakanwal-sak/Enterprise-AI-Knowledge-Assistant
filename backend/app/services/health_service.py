"""
Health-check application service.

Probes: PostgreSQL, MongoDB, Redis, Qdrant.
Exposes aggregated health, liveness, and readiness for Kubernetes / LB.
"""

from __future__ import annotations

import logging
from typing import Literal

from app.core.config import settings
from app.db.mongodb import MongoDBManager
from app.db.postgres import check_postgres_health
from app.db.redis import RedisManager
from app.schemas.health import (
    HealthResponse,
    LiveResponse,
    ReadyResponse,
    ServicesHealth,
)

logger = logging.getLogger(__name__)


async def _check_qdrant() -> bool:
    try:
        from app.ai.qdrant.client import get_qdrant_service

        svc = get_qdrant_service()
        # Prefer real client when connected; in-memory fallback counts as up for local
        if getattr(svc, "_client", None) is not None:
            svc._client.get_collections()
            return True
        return True  # in-memory / soft-fail mode still serves the process
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant health check failed: %s", exc)
        return False


class HealthService:
    """Aggregate health status for the backend and its data stores."""

    async def _probe_services(self) -> tuple[ServicesHealth, bool, bool, bool, bool]:
        postgres_ok = await check_postgres_health()
        mongo_ok = await MongoDBManager.check_health()
        redis_ok = await RedisManager.check_health()
        qdrant_ok = await _check_qdrant()
        services = ServicesHealth(
            postgres="up" if postgres_ok else "down",
            mongodb="up" if mongo_ok else "down",
            redis="up" if redis_ok else "down",
            qdrant="up" if qdrant_ok else "down",
        )
        return services, postgres_ok, mongo_ok, redis_ok, qdrant_ok

    async def check(self) -> HealthResponse:
        """Probe dependencies; return typed health payload."""
        services, postgres_ok, mongo_ok, redis_ok, qdrant_ok = await self._probe_services()

        overall: Literal["healthy", "degraded", "unhealthy"]
        core_ok = postgres_ok and mongo_ok and redis_ok
        if core_ok and qdrant_ok:
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

    async def live(self) -> LiveResponse:
        """Liveness — process responds (no dependency I/O)."""
        return LiveResponse(status="alive", version=settings.PROJECT_VERSION)

    async def ready(self) -> ReadyResponse:
        """Readiness — Postgres + Redis required; Qdrant optional unless configured."""
        services, postgres_ok, mongo_ok, redis_ok, qdrant_ok = await self._probe_services()
        ready = postgres_ok and redis_ok and mongo_ok
        if settings.READY_REQUIRE_QDRANT:
            ready = ready and qdrant_ok
        return ReadyResponse(
            status="ready" if ready else "not_ready",
            services=services,
            detail=None if ready else "One or more required dependencies are down",
        )


health_service = HealthService()
