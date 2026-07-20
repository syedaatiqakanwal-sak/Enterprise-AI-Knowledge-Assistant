"""Module 10 — Analytics & AI Observability tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.telemetry import buffer_api_request, estimate_cost
from tests.conftest import login


def test_estimate_cost() -> None:
    cost = estimate_cost(prompt_tokens=1000, completion_tokens=1000, embedding_tokens=1000)
    assert cost > 0


@pytest.mark.asyncio
async def test_analytics_overview_and_permissions(
    client: AsyncClient,
    admin_credentials: dict[str, str],
) -> None:
    buffer_api_request(
        request_id="test-req-1",
        method="GET",
        path="/api/v1/health",
        status_code=200,
        latency_ms=12.5,
    )
    buffer_api_request(
        request_id="test-req-2",
        method="GET",
        path="/api/v1/documents",
        status_code=200,
        latency_ms=40.0,
    )

    unauth = await client.get("/api/v1/analytics/overview")
    assert unauth.status_code == 401

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    overview = await client.get(
        "/api/v1/analytics/overview", headers=headers, params={"range": "30d"}
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["success"] is True
    cards = body["data"]["cards"]
    assert "documents" in cards
    assert "llm_calls" in cards
    assert "estimated_cost_usd" in cards
    assert "alerts" in body["data"]

    for path in (
        "/api/v1/analytics/users",
        "/api/v1/analytics/documents",
        "/api/v1/analytics/rag",
        "/api/v1/analytics/agents",
        "/api/v1/analytics/system",
        "/api/v1/analytics/llm",
        "/api/v1/analytics/cost",
    ):
        resp = await client.get(path, headers=headers, params={"range": "7d"})
        assert resp.status_code == 200, f"{path}: {resp.text}"

    csv_export = await client.get(
        "/api/v1/analytics/export",
        headers=headers,
        params={"format": "csv", "range": "30d"},
    )
    assert csv_export.status_code == 200
    assert b"metric" in csv_export.content

    xlsx = await client.get(
        "/api/v1/analytics/export",
        headers=headers,
        params={"format": "xlsx", "range": "30d"},
    )
    assert xlsx.status_code == 200
    assert len(xlsx.content) > 100

    pdf = await client.get(
        "/api/v1/analytics/export",
        headers=headers,
        params={"format": "pdf", "range": "30d"},
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
