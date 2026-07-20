"""Module 3 authentication and user-management API tests."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.conftest import login

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "app.log"


def _latest_auth_token(*, kind: str) -> str | None:
    if not LOG_PATH.exists():
        return None
    lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        if kind == "reset" and "reset" not in line.lower():
            continue
        if kind == "verify" and "verify" not in line.lower():
            continue
        match = re.search(r"AUTH_TOKEN=([A-Za-z0-9_-]+)", line)
        if match and match.group(1):
            return match.group(1)
        match = re.search(r"Or use this token: ([A-Za-z0-9_-]+)", line)
        if match:
            return match.group(1)
    return None


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    email = f"reg-{uuid.uuid4().hex[:10]}@example.com"
    password = "StrongPass1!"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Reg User",
            "phone": "+1 555-0199",
        },
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == email
    assert body["data"]["user"]["phone"] == "+1 555-0199"
    assert "employee" in [r["name"] for r in body["data"]["user"]["roles"]]
    assert body["data"]["tokens"]["access_token"]

    login_body = await login(client, email, password)
    assert login_body["tokens"]["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_token_rotation(
    client: AsyncClient, employee_credentials: dict[str, str]
) -> None:
    data = await login(
        client, employee_credentials["email"], employee_credentials["password"]
    )
    old_refresh = data["tokens"]["refresh_token"]

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert refreshed.status_code == 200, refreshed.text
    new_refresh = refreshed.json()["data"]["refresh_token"]
    assert new_refresh != old_refresh

    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert reused.status_code == 401
    assert reused.json()["success"] is False


@pytest.mark.asyncio
async def test_protected_routes_require_auth(client: AsyncClient) -> None:
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 401
    assert me.json()["success"] is False

    profile = await client.put(
        "/api/v1/users/profile", json={"full_name": "Nobody"}
    )
    assert profile.status_code == 401


@pytest.mark.asyncio
async def test_me_and_update_profile(
    client: AsyncClient, employee_credentials: dict[str, str]
) -> None:
    data = await login(
        client, employee_credentials["email"], employee_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {data['tokens']['access_token']}"}

    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["email"] == employee_credentials["email"]

    updated = await client.put(
        "/api/v1/users/profile",
        headers=headers,
        json={"full_name": "Updated Name", "phone": "+15550200"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["full_name"] == "Updated Name"
    assert updated.json()["data"]["phone"] == "+15550200"


@pytest.mark.asyncio
async def test_change_password(
    client: AsyncClient, employee_credentials: dict[str, str]
) -> None:
    data = await login(
        client, employee_credentials["email"], employee_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {data['tokens']['access_token']}"}
    new_password = "ChangedPass1!"

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": employee_credentials["password"],
            "new_password": new_password,
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["success"] is True

    # Old password fails
    old_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": employee_credentials["email"],
            "password": employee_credentials["password"],
        },
    )
    assert old_login.status_code == 401

    # New password works
    await login(client, employee_credentials["email"], new_password)


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient, db_session) -> None:
    from app.repositories.user_repository import UserRepository
    from app.services.token_service import TokenService

    email = f"reset-{uuid.uuid4().hex[:10]}@example.com"
    password = "ResetPass1!"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Reset User"},
    )
    assert reg.status_code == 201, reg.text

    user = await UserRepository(db_session).get_by_email(email)
    assert user is not None
    raw_token = await TokenService(db_session).issue_password_reset(user)
    await db_session.commit()

    new_password = "BrandNew1!"
    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["success"] is True

    await login(client, email, new_password)


@pytest.mark.asyncio
async def test_admin_list_and_delete_users(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    employee_credentials: dict[str, str],
) -> None:
    admin = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {admin['tokens']['access_token']}"}

    listed = await client.get("/api/v1/users?limit=50", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] >= 1

    # Employee cannot list users
    emp = await login(
        client, employee_credentials["email"], employee_credentials["password"]
    )
    emp_headers = {"Authorization": f"Bearer {emp['tokens']['access_token']}"}
    forbidden = await client.get("/api/v1/users", headers=emp_headers)
    assert forbidden.status_code == 403

    # Admin deletes employee
    emp_id = emp["user"]["id"]
    deleted = await client.delete(f"/api/v1/users/{emp_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text

    gone = await client.get(f"/api/v1/users/{emp_id}", headers=headers)
    assert gone.status_code == 404
