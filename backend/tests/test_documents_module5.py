"""
Module 5 — Document Management System API tests.

Covers upload, rename, delete, search, folders, and permission checks.
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import login


def _txt_file(name: str = "notes.txt", content: str = "hello enterprise dms") -> dict:
    return {
        "file": (name, io.BytesIO(content.encode("utf-8")), "text/plain"),
    }


@pytest.mark.asyncio
async def test_upload_list_rename_delete(
    client: AsyncClient, admin_credentials: dict[str, str]
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files=_txt_file(f"report-{uuid.uuid4().hex[:6]}.txt", "alpha beta gamma"),
        data={"visibility": "private", "tags": "finance,q1"},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["success"] is True
    doc = body["data"]["document"]
    doc_id = doc["id"]
    assert doc["status"] == "ready"
    assert doc["extension"] == "txt"
    assert "finance" in doc["tags"]

    listed = await client.get("/api/v1/documents", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["success"] is True
    assert listed.json()["data"]["total"] >= 1

    renamed = await client.put(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"filename": "renamed-report.txt", "description": "Q1 notes"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["filename"] == "renamed-report.txt"

    search = await client.get(
        "/api/v1/documents/search",
        headers=headers,
        params={"q": "renamed-report"},
    )
    assert search.status_code == 200
    assert search.json()["data"]["total"] >= 1

    fav = await client.post(f"/api/v1/documents/{doc_id}/favorite", headers=headers)
    assert fav.status_code == 200
    assert fav.json()["data"]["is_favorited"] is True

    deleted = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True


@pytest.mark.asyncio
async def test_folder_operations(
    client: AsyncClient, admin_credentials: dict[str, str]
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    name = f"Projects-{uuid.uuid4().hex[:6]}"

    created = await client.post(
        "/api/v1/folders",
        headers=headers,
        json={"name": name},
    )
    assert created.status_code == 201, created.text
    folder_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/folders", headers=headers)
    assert listed.status_code == 200
    names = [f["name"] for f in listed.json()["data"]["folders"]]
    assert name in names

    child_name = f"Nested-{uuid.uuid4().hex[:6]}"
    child = await client.post(
        "/api/v1/folders",
        headers=headers,
        json={"name": child_name, "parent_id": folder_id},
    )
    assert child.status_code == 201, child.text

    renamed = await client.put(
        f"/api/v1/folders/{folder_id}",
        headers=headers,
        json={"name": f"{name}-v2"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == f"{name}-v2"

    # Cannot delete non-empty parent
    blocked = await client.delete(f"/api/v1/folders/{folder_id}", headers=headers)
    assert blocked.status_code == 400

    child_id = child.json()["data"]["id"]
    assert (
        await client.delete(f"/api/v1/folders/{child_id}", headers=headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/folders/{folder_id}", headers=headers)
    ).status_code == 200


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/documents/upload",
        files=_txt_file(),
    )
    assert resp.status_code == 401
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_employee_can_upload_and_search(
    client: AsyncClient, employee_credentials: dict[str, str]
) -> None:
    auth = await login(
        client, employee_credentials["email"], employee_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    fname = f"emp-{uuid.uuid4().hex[:6]}.txt"

    upload = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files=_txt_file(fname, "employee owned file"),
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["data"]["document"]["id"]

    preview = await client.get(
        f"/api/v1/documents/{doc_id}/preview", headers=headers
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["preview"]["preview_type"] == "text"

    archive = await client.post(
        f"/api/v1/documents/{doc_id}/archive", headers=headers
    )
    assert archive.status_code == 200
    assert archive.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_reject_unsupported_extension(
    client: AsyncClient, admin_credentials: dict[str, str]
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    resp = await client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "malware.exe",
                io.BytesIO(b"MZ"),
                "application/octet-stream",
            )
        },
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
