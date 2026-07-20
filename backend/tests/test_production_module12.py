"""Module 12 — production probes and observability smoke tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_live_ready_health_metrics(client: AsyncClient) -> None:
    live = await client.get("/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"

    ready = await client.get("/ready")
    assert ready.status_code in (200, 503)
    body = ready.json()
    assert "services" in body
    assert "postgres" in body["services"]
    assert "qdrant" in body["services"]

    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"]
    assert "qdrant" in health.json()["services"]

    metrics = await client.get("/metrics")
    assert metrics.status_code in (200, 404)
    if metrics.status_code == 200:
        assert b"http_requests_total" in metrics.content or b"app_info" in metrics.content

    root = await client.get("/")
    assert root.status_code == 200
    data = root.json()
    assert data.get("live") == "/live"
    assert data.get("ready") == "/ready"
