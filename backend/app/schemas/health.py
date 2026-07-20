"""Pydantic schemas for health-check / readiness / liveness probes."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ServiceStatus = Literal["up", "down", "skipped"]


class ServicesHealth(BaseModel):
    """Per-dependency health status."""

    postgres: ServiceStatus
    mongodb: ServiceStatus
    redis: ServiceStatus
    qdrant: ServiceStatus = "skipped"


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


class LiveResponse(BaseModel):
    """Kubernetes liveness — process is alive (no dependency checks)."""

    status: Literal["alive"] = "alive"
    version: str


class ReadyResponse(BaseModel):
    """Kubernetes readiness — ready to receive traffic."""

    status: Literal["ready", "not_ready"]
    services: ServicesHealth
    detail: Optional[str] = None


class RootResponse(BaseModel):
    """Root welcome payload."""

    message: str
    version: str
    environment: str
    docs: str
    health: str
    live: str = "/live"
    ready: str = "/ready"
    metrics: str = "/metrics"
    api_v1: str
