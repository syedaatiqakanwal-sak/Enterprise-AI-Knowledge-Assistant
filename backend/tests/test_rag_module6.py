"""
Module 6 — RAG / Chat / indexing tests.

Uses mock embeddings + mock LLM (configured via env / provider defaults).
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient

from app.ai.chunking import normalize_text, recursive_chunk
from app.ai.embeddings import MockEmbeddingProvider, get_embedding_provider
from app.ai.llm import MockLLMProvider, get_llm_provider
from app.ai.parsers import ParserFactory
from tests.conftest import login


def test_recursive_chunking() -> None:
    text = ("Enterprise knowledge. " * 80).strip()
    chunks = recursive_chunk(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert all(c.char_count <= 140 for c in chunks)  # size + overlap slack


def test_normalize_and_txt_parser() -> None:
    raw = b"Hello\r\n\r\nWorld\x00!"
    cleaned = normalize_text(raw.decode("utf-8", errors="replace"))
    assert "\x00" not in cleaned
    doc = ParserFactory.get("txt").extract(b"Policy section A\nPolicy section B")
    assert "Policy section A" in doc.text


def test_embedding_provider_is_mock_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_embedding_provider.cache_clear()
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)
    vecs = provider.embed_documents(["alpha", "beta"])
    assert len(vecs) == 2
    assert len(vecs[0]) == provider.dimension


@pytest.mark.asyncio
async def test_index_upload_chat_flow(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    content = (
        "Remote Work Policy\n"
        "Employees may work remotely up to three days per week.\n"
        "Managers must approve remote schedules in advance.\n"
    )
    fname = f"policy-{uuid.uuid4().hex[:6]}.txt"
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (fname, io.BytesIO(content.encode()), "text/plain")},
        data={"visibility": "company"},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["data"]["document"]["id"]

    indexed = await client.post(
        f"/api/v1/documents/{doc_id}/index",
        headers=headers,
        params={"sync": "true"},
    )
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["data"]["success"] is True
    assert indexed.json()["data"].get("chunks", 0) >= 1

    search = await client.get(
        "/api/v1/search",
        headers=headers,
        params={"q": "remote work policy", "top_k": 3},
    )
    assert search.status_code == 200, search.text
    assert search.json()["success"] is True

    ask = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "What is the remote work policy?"},
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()
    assert body["success"] is True
    assert body["data"]["assistant_message"]["content"]
    assert "citations" in body["data"]
    chat_id = body["data"]["chat_id"]

    history = await client.get("/api/v1/chat/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["data"]["total"] >= 1

    detail = await client.get(f"/api/v1/chat/{chat_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["data"]["messages"]) >= 2

    renamed = await client.patch(
        f"/api/v1/chat/{chat_id}",
        headers=headers,
        json={"title": "Remote policy Q&A", "is_pinned": True},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["is_pinned"] is True

    deleted = await client.delete(f"/api/v1/chat/{chat_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_chat_stream_sse(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    # Pre-index a tiny doc so retrieval has something
    fname = f"stream-{uuid.uuid4().hex[:6]}.txt"
    upload = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                fname,
                io.BytesIO(b"Vacation policy allows 20 days per year."),
                "text/plain",
            )
        },
    )
    doc_id = upload.json()["data"]["document"]["id"]
    await client.post(
        f"/api/v1/documents/{doc_id}/index",
        headers=headers,
        params={"sync": "true"},
    )

    resp = await client.post(
        "/api/v1/chat/stream",
        headers=headers,
        json={"message": "How many vacation days?"},
    )
    assert resp.status_code == 200
    text = resp.text
    assert "event:" in text
    assert "data:" in text


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/chat", json={"message": "hello"})
    assert resp.status_code == 401
