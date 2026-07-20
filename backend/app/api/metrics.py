"""Prometheus metrics endpoint + FastAPI instrumentation helpers (Module 12)."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import APIRouter, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROM = True
except ImportError:  # pragma: no cover
    _PROM = False

router = APIRouter(tags=["Observability"])

if _PROM:
    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    APP_INFO = Gauge("app_info", "Application info", ["version", "environment"])
    APP_INFO.labels(
        version=settings.PROJECT_VERSION,
        environment=settings.ENVIRONMENT.value,
    ).set(1)


def _normalize_path(path: str) -> str:
    if path.startswith("/api/v1/"):
        parts = path.split("/")
        # Collapse UUIDs
        out = []
        for p in parts:
            if len(p) == 36 and p.count("-") == 4:
                out.append("{id}")
            else:
                out.append(p)
        return "/".join(out)
    return path


class PrometheusMiddleware:
    """Record request counts and latency for Prometheus scrapes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.METRICS_ENABLED or not _PROM:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in ("/metrics", "/live", "/ready", "/health"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            label_path = _normalize_path(path)
            REQUEST_COUNT.labels(
                method=method, path=label_path, status=str(status_holder["code"])
            ).inc()
            REQUEST_LATENCY.labels(method=method, path=label_path).observe(elapsed)


@router.get(
    "/metrics",
    include_in_schema=True,
    summary="Prometheus metrics",
    description="Scrapable Prometheus exposition format for app and HTTP metrics.",
)
async def metrics() -> Response:
    if not settings.METRICS_ENABLED or not _PROM:
        return Response(
            content="# metrics disabled\n",
            media_type="text/plain",
            status_code=404,
        )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
