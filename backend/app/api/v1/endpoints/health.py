"""
Health endpoints.

- ``GET /health``              — infrastructure / load-balancer probe (root)
- ``GET /api/v1/health``       — versioned API health (same payload)
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse
from app.services.health_service import health_service

router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Versioned health check",
    description=(
        "Returns backend status plus live probes for PostgreSQL, MongoDB, "
        "Redis, and Qdrant, along with version and environment."
    ),
)
async def api_health() -> HealthResponse:
    """Versioned health endpoint under ``/api/v1/health``."""
    return await health_service.check()
