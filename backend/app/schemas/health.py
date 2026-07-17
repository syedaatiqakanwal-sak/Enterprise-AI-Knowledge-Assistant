"""
Pydantic schemas for health-check responses.

Kept in the schemas layer so API contracts stay independent of infrastructure
implementation details.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ServiceStatus = Literal["up", "down"]


class ServicesHealth(BaseModel):
    """Per-dependency health status."""

    postgres: ServiceStatus
    mongodb: ServiceStatus
    redis: ServiceStatus


class HealthResponse(BaseModel):
    """Canonical health-check payload."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall backend status derived from dependency checks",
    )
    backend: Literal["up"] = "up"
    services: ServicesHealth
    version: str
    environment: str


class RootResponse(BaseModel):
    """Root welcome payload."""

    message: str
    version: str
    environment: str
    docs: str
    health: str
    api_v1: str
