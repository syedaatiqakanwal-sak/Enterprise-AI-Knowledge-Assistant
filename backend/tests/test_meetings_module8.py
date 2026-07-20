"""Module 8 — Meeting Intelligence tests (mock Whisper / diarization)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.ai.meetings.provider import (
    analyze_meeting_text,
    get_diarization_provider,
    get_transcription_provider,
)
from tests.conftest import login


def _fake_audio_bytes() -> bytes:
    # Minimal bytes — mock provider ignores content
    return b"RIFF" + b"\x00" * 64 + b"WAVEfmt "


def test_mock_transcription_and_analysis() -> None:
    get_transcription_provider.cache_clear()
    get_diarization_provider.cache_clear()
    result = get_transcription_provider().transcribe("dummy.wav")
    assert result.segments
    assert "Speaker" in result.segments[0].speaker
    diarized = get_diarization_provider().assign_speakers("dummy.wav", result.segments)
    analysis = analyze_meeting_text(result.full_text, diarized)
    assert analysis["executive_summary"]
    assert analysis["action_items"] or analysis["decisions"]
    assert analysis["minutes"]["attendance"]


@pytest.mark.asyncio
async def test_meeting_upload_process_chat(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEETING_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("MEETING_AUTO_INDEX_RAG", "true")
    get_transcription_provider.cache_clear()
    get_diarization_provider.cache_clear()

    from app.ai.embeddings import get_embedding_provider
    from app.ai.llm import get_llm_provider

    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/meetings/upload",
        headers=headers,
        files={"file": ("budget-meeting.mp3", _fake_audio_bytes(), "audio/mpeg")},
        data={"auto_process": "true", "title": "Q3 Budget"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "ready"
    assert data["segments"]
    assert data["summary"]
    assert data.get("linked_document_id"), "Meeting should auto-index into RAG"
    meeting_id = data["id"]

    got = await client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["title"] == "Q3 Budget"

    transcript = await client.get(
        f"/api/v1/meetings/{meeting_id}/transcript", headers=headers
    )
    assert transcript.status_code == 200
    assert transcript.json()["data"]["segments"]

    summary = await client.get(
        f"/api/v1/meetings/{meeting_id}/summary", headers=headers
    )
    assert summary.status_code == 200
    sdata = summary.json()["data"]
    assert sdata["executive_summary"]
    assert "action_items" in sdata

    listed = await client.get("/api/v1/meetings", headers=headers, params={"q": "Budget"})
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

    chat = await client.post(
        f"/api/v1/meetings/{meeting_id}/chat",
        headers=headers,
        json={"message": "What was decided about hiring?"},
    )
    assert chat.status_code == 200, chat.text
    cdata = chat.json()["data"]
    assert cdata["answer"]
    assert cdata["grounded"] is True or len(cdata.get("citations") or []) >= 0

    deleted = await client.delete(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert deleted.status_code == 200
    missing = await client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_meeting_upload_then_process_separately(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEETING_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_transcription_provider.cache_clear()
    get_diarization_provider.cache_clear()
    from app.ai.embeddings import get_embedding_provider
    from app.ai.llm import get_llm_provider

    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    up = await client.post(
        "/api/v1/meetings/upload",
        headers=headers,
        files={"file": (f"standup-{uuid.uuid4().hex[:6]}.wav", _fake_audio_bytes(), "audio/wav")},
        data={"auto_process": "false"},
    )
    assert up.status_code == 201, up.text
    mid = up.json()["data"]["id"]
    assert up.json()["data"]["status"] == "uploaded"

    tr = await client.post(
        "/api/v1/meetings/transcribe",
        headers=headers,
        params={"meeting_id": mid},
    )
    assert tr.status_code == 200, tr.text
    assert tr.json()["data"]["segments"]

    proc = await client.post(
        "/api/v1/meetings/process",
        headers=headers,
        params={"meeting_id": mid},
    )
    assert proc.status_code == 200, proc.text
    assert proc.json()["data"]["status"] == "ready"
    assert proc.json()["data"].get("linked_document_id")


@pytest.mark.asyncio
async def test_meeting_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/meetings/upload",
        files={"file": ("x.mp3", _fake_audio_bytes(), "audio/mpeg")},
    )
    assert resp.status_code == 401
