"""
Seed default RBAC roles, permissions, and optional admin user.

Idempotent — safe to run on every application startup.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import RoleName
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# code, name, resource, action, description
DEFAULT_PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("users:read", "Read users", "users", "read", "View user profiles"),
    ("users:write", "Write users", "users", "write", "Create or update users"),
    ("users:delete", "Delete users", "users", "delete", "Soft-delete users"),
    ("roles:read", "Read roles", "roles", "read", "View roles and permissions"),
    ("roles:write", "Write roles", "roles", "write", "Manage roles and permissions"),
    ("documents:read", "Read documents", "documents", "read", "View company documents"),
    ("documents:write", "Write documents", "documents", "write", "Upload or edit documents"),
    ("documents:delete", "Delete documents", "documents", "delete", "Remove documents"),
    ("chat:read", "Read chats", "chat", "read", "View AI chat history"),
    ("chat:write", "Write chats", "chat", "write", "Ask the knowledge assistant"),
    ("ocr:read", "Read OCR", "ocr", "read", "View OCR results"),
    ("ocr:write", "Write OCR", "ocr", "write", "Run OCR extraction"),
    ("vision:read", "Read vision", "vision", "read", "View vision analysis"),
    ("vision:write", "Write vision", "vision", "write", "Run vision / YOLO analysis"),
    ("meetings:read", "Read meetings", "meetings", "read", "View meeting intelligence"),
    ("meetings:write", "Write meetings", "meetings", "write", "Upload and process meetings"),
    ("agents:read", "Read agents", "agents", "read", "View agent sessions, tasks, workflows"),
    ("agents:write", "Write agents", "agents", "write", "Run agents and manage workflows"),
    ("analytics:read", "Read analytics", "analytics", "read", "View analytics and AI observability"),
    ("analytics:export", "Export analytics", "analytics", "export", "Export analytics reports"),
    ("admin:all", "Full admin", "admin", "all", "Unrestricted administrative access"),
]

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    RoleName.ADMIN.value: [p[0] for p in DEFAULT_PERMISSIONS],
    RoleName.MANAGER.value: [
        "users:read",
        "documents:read",
        "documents:write",
        "chat:read",
        "chat:write",
        "ocr:read",
        "ocr:write",
        "vision:read",
        "vision:write",
        "meetings:read",
        "meetings:write",
        "agents:read",
        "agents:write",
        "roles:read",
    ],
    RoleName.EMPLOYEE.value: [
        "documents:read",
        "documents:write",
        "chat:read",
        "chat:write",
        "ocr:read",
        "ocr:write",
        "vision:read",
        "vision:write",
        "meetings:read",
        "meetings:write",
        "agents:read",
        "agents:write",
        "users:read",
    ],
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    RoleName.ADMIN.value: "Full system administrator",
    RoleName.MANAGER.value: "Team manager with elevated document access",
    RoleName.EMPLOYEE.value: "Standard employee access",
}


async def seed_rbac(session: AsyncSession) -> None:
    """Ensure roles and permissions exist and are linked correctly."""
    roles = RoleRepository(session)

    permission_by_code: dict[str, object] = {}
    for code, name, resource, action, description in DEFAULT_PERMISSIONS:
        existing = await roles.get_permission_by_code(code)
        if existing is None:
            existing = await roles.create_permission(
                code=code,
                name=name,
                resource=resource,
                action=action,
                description=description,
            )
            logger.info("Seeded permission %s", code)
        permission_by_code[code] = existing

    for role_name, description in ROLE_DESCRIPTIONS.items():
        role = await roles.get_by_name(role_name)
        if role is None:
            await roles.create_role(name=role_name, description=description)
            logger.info("Seeded role %s", role_name)
            role = await roles.get_by_name(role_name)
        if role is None:
            raise RuntimeError(f"Failed to load role {role_name} after seed")

        existing_codes = {p.code for p in (role.permissions or [])}
        for code in ROLE_PERMISSION_MAP.get(role_name, []):
            if code not in existing_codes:
                permission = permission_by_code[code]
                await roles.grant_permission(role, permission)  # type: ignore[arg-type]
                existing_codes.add(code)
                logger.info("Granted %s -> %s", code, role_name)

    await _seed_admin_if_configured(session)
    from app.services.tenancy_bootstrap import ensure_default_tenant

    await ensure_default_tenant(session)
    await session.commit()


async def _seed_admin_if_configured(session: AsyncSession) -> None:
    if not settings.SEED_ADMIN_EMAIL or not settings.SEED_ADMIN_PASSWORD:
        return

    users = UserRepository(session)
    roles = RoleRepository(session)
    existing = await users.get_by_email(settings.SEED_ADMIN_EMAIL)
    if existing is not None:
        return

    admin_role = await roles.get_by_name(RoleName.ADMIN.value)
    if admin_role is None:
        logger.error("Cannot seed admin — admin role missing")
        return

    user = await users.create(
        email=settings.SEED_ADMIN_EMAIL,
        hashed_password=get_password_hash(settings.SEED_ADMIN_PASSWORD),
        full_name=settings.SEED_ADMIN_FULL_NAME,
        is_verified=True,
    )
    await users.assign_role(user, admin_role)
    logger.info("Seeded admin user %s", settings.SEED_ADMIN_EMAIL)
