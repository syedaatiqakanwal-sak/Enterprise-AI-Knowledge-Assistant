"""Dual-portal architecture — JWT claims + Admin/User portal guards."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.middlewares.portal import (
    is_admin_portal_user,
    is_user_portal_user,
)
from app.models.enums import RoleName
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.services.tenancy_bootstrap import ensure_default_tenant
from tests.conftest import login


async def _make_employee(db_session: AsyncSession) -> tuple[str, str]:
    email = f"portal-emp-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"
    users = UserRepository(db_session)
    roles = RoleRepository(db_session)
    emp_role = await roles.get_by_name(RoleName.EMPLOYEE.value)
    assert emp_role is not None
    emp = await users.create(
        email=email,
        hashed_password=get_password_hash(password),
        full_name="Portal Employee",
        is_verified=True,
    )
    await users.assign_role(emp, emp_role)
    await db_session.commit()
    await ensure_default_tenant(db_session)
    await db_session.commit()
    return email, password


@pytest.mark.asyncio
async def test_jwt_contains_portal_claims(
    client: AsyncClient,
    admin_credentials: dict[str, str],
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    token = auth["tokens"]["access_token"]
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload.get("role") in {"admin", "manager"}
    assert "roles" in payload
    assert isinstance(payload.get("permissions"), list)
    assert payload.get("tenant_id")
    assert payload.get("organization_id")

    user = auth["user"]
    assert user.get("role") in {"admin", "manager"}
    assert isinstance(user.get("permissions"), list)
    assert user.get("tenant_id")
    assert user.get("organization_id")


@pytest.mark.asyncio
async def test_employee_jwt_and_admin_portal_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email, password = await _make_employee(db_session)
    auth = await login(client, email, password)
    token = auth["tokens"]["access_token"]
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload.get("role") == "employee"
    assert "employee" in payload.get("roles", [])
    assert isinstance(payload.get("permissions"), list)

    headers = {"Authorization": f"Bearer {token}"}
    forbidden = await client.get("/api/v1/admin/organizations", headers=headers)
    assert forbidden.status_code == 403
    body = forbidden.json()
    # Envelope or detail depending on exception handler
    msg = str(body)
    assert "ADMIN_PORTAL" in msg or "403" in str(forbidden.status_code) or "forbidden" in msg.lower() or "denied" in msg.lower()


@pytest.mark.asyncio
async def test_admin_can_access_admin_apis(
    client: AsyncClient,
    admin_credentials: dict[str, str],
) -> None:
    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    ok = await client.get("/api/v1/admin/organizations", headers=headers)
    assert ok.status_code == 200
    assert ok.json().get("success") is True


@pytest.mark.asyncio
async def test_employee_can_use_chat_apis(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email, password = await _make_employee(db_session)
    auth = await login(client, email, password)
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}
    history = await client.get("/api/v1/chat/history", headers=headers)
    assert history.status_code == 200
    assert history.json().get("success") is True


@pytest.mark.asyncio
async def test_portal_role_helpers(db_session: AsyncSession) -> None:
    users = UserRepository(db_session)
    roles = RoleRepository(db_session)
    admin_role = await roles.get_by_name(RoleName.ADMIN.value)
    emp_role = await roles.get_by_name(RoleName.EMPLOYEE.value)
    assert admin_role and emp_role

    admin = await users.create(
        email=f"portal-admin-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Portal Admin",
        is_verified=True,
    )
    await users.assign_role(admin, admin_role)
    emp = await users.create(
        email=f"portal-u-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        full_name="Portal User",
        is_verified=True,
    )
    await users.assign_role(emp, emp_role)
    await db_session.commit()

    # Reload with roles
    admin = await users.get_by_id(admin.id)
    emp = await users.get_by_id(emp.id)
    assert admin and emp
    assert is_admin_portal_user(admin) is True
    assert is_user_portal_user(admin) is False
    assert is_admin_portal_user(emp) is False
    assert is_user_portal_user(emp) is True
