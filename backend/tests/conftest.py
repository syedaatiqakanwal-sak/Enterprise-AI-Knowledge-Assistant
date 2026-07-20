"""
Pytest fixtures for Module 3 authentication tests.

Uses a session-scoped event loop so the module-level AsyncEngine pool
stays bound to one loop for the entire test session.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.postgres import AsyncSessionLocal, engine
from app.db.seed import seed_rbac
from app.main import app
from app.models.enums import RoleName
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """One event loop for the whole pytest session (SQLAlchemy async pool)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database() -> AsyncGenerator[None, None]:
    await engine.dispose()
    async with AsyncSessionLocal() as session:
        await seed_rbac(session)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_connections() -> AsyncGenerator[None, None]:
    """Ensure pooled connections are not reused across event loops."""
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def employee_credentials(db_session: AsyncSession) -> dict[str, str]:
    email = f"emp-{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass123!"
    users = UserRepository(db_session)
    roles = RoleRepository(db_session)
    role = await roles.get_by_name(RoleName.EMPLOYEE.value)
    assert role is not None
    user = await users.create(
        email=email,
        hashed_password=get_password_hash(password),
        full_name="Test Employee",
        phone="+15550100",
        is_verified=True,
    )
    await users.assign_role(user, role)
    await db_session.commit()
    from app.services.tenancy_bootstrap import ensure_default_tenant

    await ensure_default_tenant(db_session)
    await db_session.commit()
    return {"email": email, "password": password}


@pytest_asyncio.fixture
async def admin_credentials(db_session: AsyncSession) -> dict[str, str]:
    email = f"adm-{uuid.uuid4().hex[:10]}@example.com"
    password = "AdminPass123!"
    users = UserRepository(db_session)
    roles = RoleRepository(db_session)
    role = await roles.get_by_name(RoleName.ADMIN.value)
    assert role is not None
    user = await users.create(
        email=email,
        hashed_password=get_password_hash(password),
        full_name="Test Admin",
        is_verified=True,
    )
    await users.assign_role(user, role)
    await db_session.commit()
    from app.services.tenancy_bootstrap import ensure_default_tenant

    await ensure_default_tenant(db_session)
    await db_session.commit()
    return {"email": email, "password": password}


async def login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]
