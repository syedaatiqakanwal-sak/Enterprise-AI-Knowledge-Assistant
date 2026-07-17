"""Role and permission persistence repository."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.associations import RolePermission
from app.models.permission import Permission
from app.models.role import Role


class RoleRepository:
    """Data-access methods for roles and permissions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> Optional[Role]:
        """Fetch a non-deleted role by unique name."""
        stmt = (
            select(Role)
            .where(Role.name == name, Role.deleted_at.is_(None))
            .options(selectinload(Role.permissions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_roles(self) -> Sequence[Role]:
        """Return all non-deleted roles."""
        stmt = (
            select(Role)
            .where(Role.deleted_at.is_(None))
            .options(selectinload(Role.permissions))
            .order_by(Role.name)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_permission_by_code(self, code: str) -> Optional[Permission]:
        """Fetch a permission by its unique code."""
        stmt = select(Permission).where(
            Permission.code == code,
            Permission.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(
        self, *, name: str, description: str | None = None
    ) -> Role:
        """Insert a role."""
        role = Role(name=name, description=description, is_active=True)
        self._session.add(role)
        await self._session.flush()
        return role

    async def create_permission(
        self,
        *,
        code: str,
        name: str,
        resource: str,
        action: str,
        description: str | None = None,
    ) -> Permission:
        """Insert a permission."""
        permission = Permission(
            code=code,
            name=name,
            resource=resource,
            action=action,
            description=description,
        )
        self._session.add(permission)
        await self._session.flush()
        return permission

    async def grant_permission(self, role: Role, permission: Permission) -> RolePermission:
        """Attach a permission to a role."""
        link = RolePermission(role_id=role.id, permission_id=permission.id)
        self._session.add(link)
        await self._session.flush()
        return link
