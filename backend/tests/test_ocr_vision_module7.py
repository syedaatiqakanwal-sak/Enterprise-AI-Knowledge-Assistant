"""Module 7 — OCR & Vision tests (mock providers)."""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from PIL import Image

from app.ai.ocr.provider import (
    classify_document,
    extract_key_values,
    extract_tables_heuristic,
    get_ocr_provider,
)
from app.ai.vision import analyze_vision, get_yolo_detector
from tests.conftest import login


def _png_bytes(color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    img = Image.new("RGB", (640, 480), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_classify_and_key_values() -> None:
    text = (
        "INVOICE\nInvoice Number: INV-9\nVendor: Acme\n"
        "Date: 2026-01-01\nGrand Total: 100.00\nCurrency: USD\n"
    )
    assert classify_document(text) == "invoice"
    kv = extract_key_values(text)
    assert kv.get("invoice_number") == "INV-9"
    assert "grand_total" in kv


def test_table_heuristic() -> None:
    text = "Item  Qty  Price\nPen  2  1.50\nPad  1  3.00\n"
    tables = extract_tables_heuristic(text)
    assert tables
    assert tables[0]["column_count"] >= 2


def test_mock_ocr_and_yolo() -> None:
    get_ocr_provider.cache_clear()
    get_yolo_detector.cache_clear()
    import numpy as np

    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    ocr = get_ocr_provider().extract(img)
    assert "INVOICE" in ocr.text.upper() or len(ocr.text) > 0
    vision = analyze_vision(img)
    assert vision.objects
    assert vision.caption


@pytest.mark.asyncio
async def test_ocr_upload_and_rag_link(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_ocr_provider.cache_clear()

    from app.ai.embeddings import get_embedding_provider
    from app.ai.llm import get_llm_provider

    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/ocr/upload",
        headers=headers,
        files={"file": ("invoice.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["document_type"] == "invoice"
    assert data["key_values"].get("invoice_number")
    assert data.get("linked_document_id"), "OCR should auto-index into RAG/DMS"
    ocr_id = data["id"]

    got = await client.get(f"/api/v1/ocr/{ocr_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["raw_text"]

    search = await client.get(
        "/api/v1/ocr/search",
        headers=headers,
        params={"q": "INV"},
    )
    assert search.status_code == 200
    assert search.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_vision_analyze_and_history(
    client: AsyncClient, admin_credentials: dict[str, str]
) -> None:
    get_yolo_detector.cache_clear()
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/vision/analyze",
        headers=headers,
        files={"file": (f"scene-{uuid.uuid4().hex[:6]}.png", _png_bytes((30, 30, 30)), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["caption"]
    assert len(data["objects"]) >= 1

    detect = await client.post(
        "/api/v1/vision/detect",
        headers=headers,
        files={"file": ("detect.png", _png_bytes(), "image/png")},
    )
    assert detect.status_code == 201
    assert detect.json()["data"]["objects"]

    hist = await client.get("/api/v1/vision/history", headers=headers)
    assert hist.status_code == 200
    assert hist.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_ocr_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/ocr/upload",
        files={"file": ("x.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 401
