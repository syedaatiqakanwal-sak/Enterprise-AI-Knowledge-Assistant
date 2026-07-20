"""Module 11 — Enterprise Multi-Tenant SaaS Administration tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import RoleName
from app.models.tenant import Tenant
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.services.tenancy_bootstrap import ensure_default_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import login


@pytest.mark.asyncio
async def test_tenant_isolation_and_admin_apis(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    db_session: AsyncSession,
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    # JWT must contain tenant claims
    payload = jwt.decode(
        auth["tokens"]["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload.get("tenant_id")
    assert payload.get("organization_id")

    # Employee cannot access admin
    emp_email = f"emp11-{uuid.uuid4().hex[:8]}@example.com"
    emp_pass = "TestPass123!"
    users = UserRepository(db_session)
    roles = RoleRepository(db_session)
    emp_role = await roles.get_by_name(RoleName.EMPLOYEE.value)
    assert emp_role is not None
    emp = await users.create(
        email=emp_email,
        hashed_password=get_password_hash(emp_pass),
        full_name="Emp 11",
        is_verified=True,
    )
    await users.assign_role(emp, emp_role)
    await db_session.commit()
    await ensure_default_tenant(db_session)
    await db_session.commit()

    emp_auth = await login(client, emp_email, emp_pass)
    emp_headers = {
        "Authorization": f"Bearer {emp_auth['tokens']['access_token']}"
    }
    forbidden = await client.get("/api/v1/admin/organizations", headers=emp_headers)
    assert forbidden.status_code == 403

    # Organizations CRUD
    create_org = await client.post(
        "/api/v1/admin/organizations",
        headers=headers,
        json={"name": f"Org-{uuid.uuid4().hex[:6]}", "domain": "acme.test"},
    )
    assert create_org.status_code == 200, create_org.text
    org = create_org.json()["data"]
    org_id = org["id"]

    list_orgs = await client.get("/api/v1/admin/organizations", headers=headers)
    assert list_orgs.status_code == 200
    assert any(o["id"] == org_id for o in list_orgs.json()["data"])

    upd = await client.put(
        f"/api/v1/admin/organizations/{org_id}",
        headers=headers,
        json={"timezone": "America/New_York", "language": "en"},
    )
    assert upd.status_code == 200
    assert upd.json()["data"]["timezone"] == "America/New_York"

    # Teams
    team_resp = await client.post(
        "/api/v1/admin/teams",
        headers=headers,
        json={"name": "Engineering", "organization_id": org_id},
    )
    assert team_resp.status_code == 200, team_resp.text
    team_id = team_resp.json()["data"]["id"]

    teams = await client.get(
        "/api/v1/admin/teams",
        headers=headers,
        params={"organization_id": org_id},
    )
    assert teams.status_code == 200
    assert any(t["id"] == team_id for t in teams.json()["data"])

    # Invite user
    invite_email = f"invite-{uuid.uuid4().hex[:8]}@example.com"
    invite = await client.post(
        "/api/v1/admin/users/invite",
        headers=headers,
        json={
            "email": invite_email,
            "role": "employee",
            "organization_id": org_id,
            "team_id": team_id,
        },
    )
    assert invite.status_code == 200, invite.text
    assert invite.json()["data"]["email"] == invite_email
    invited_user_id = invite.json()["data"]["user_id"]

    users_list = await client.get("/api/v1/admin/users", headers=headers)
    assert users_list.status_code == 200
    assert users_list.json()["data"]["total"] >= 1

    # Suspend / activate
    suspend = await client.put(
        f"/api/v1/admin/users/{invited_user_id}",
        headers=headers,
        json={"status": "suspended"},
    )
    assert suspend.status_code == 200
    assert suspend.json()["data"]["status"] == "suspended"

    # API keys
    key_resp = await client.post(
        "/api/v1/admin/api-keys",
        headers=headers,
        json={"name": "ci-key", "scopes": ["read"]},
    )
    assert key_resp.status_code == 200, key_resp.text
    key_data = key_resp.json()["data"]
    assert key_data["api_key"].startswith(settings.API_KEY_PREFIX)
    key_id = key_data["id"]

    keys = await client.get("/api/v1/admin/api-keys", headers=headers)
    assert keys.status_code == 200
    assert any(k["id"] == key_id for k in keys.json()["data"])

    rotate = await client.post(
        f"/api/v1/admin/api-keys/{key_id}/rotate", headers=headers
    )
    assert rotate.status_code == 200
    assert rotate.json()["data"]["api_key"].startswith(settings.API_KEY_PREFIX)

    # Audit logs should record admin actions
    audit = await client.get("/api/v1/admin/audit", headers=headers)
    assert audit.status_code == 200
    actions = {a["action"] for a in audit.json()["data"]["items"]}
    assert "admin.organization.create" in actions
    assert "admin.user.invite" in actions
    assert "admin.api_key.create" in actions

    # Storage + subscription placeholders
    storage = await client.get("/api/v1/admin/storage", headers=headers)
    assert storage.status_code == 200
    assert "quota_bytes" in storage.json()["data"]
    assert "subscription" in storage.json()["data"]

    sub = await client.get("/api/v1/admin/subscription", headers=headers)
    assert sub.status_code == 200
    assert sub.json()["data"]["payment"] is None
    assert "enterprise" in sub.json()["data"]["plans"]

    # Cross-tenant isolation: foreign org id must 404
    fake_org = uuid.uuid4()
    missing = await client.put(
        f"/api/v1/admin/organizations/{fake_org}",
        headers=headers,
        json={"name": "Nope"},
    )
    assert missing.status_code == 404

    # Delete API key
    del_key = await client.delete(
        f"/api/v1/admin/api-keys/{key_id}", headers=headers
    )
    assert del_key.status_code == 200

    # Delete org (soft)
    del_org = await client.delete(
        f"/api/v1/admin/organizations/{org_id}", headers=headers
    )
    assert del_org.status_code == 200


@pytest.mark.asyncio
async def test_default_tenant_bootstrap(db_session: AsyncSession) -> None:
    tenant = await ensure_default_tenant(db_session)
    await db_session.commit()
    assert isinstance(tenant, Tenant)
    assert tenant.slug == settings.DEFAULT_TENANT_SLUG
