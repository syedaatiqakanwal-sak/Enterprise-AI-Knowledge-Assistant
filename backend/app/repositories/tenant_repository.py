"""Tenant / organization / team / admin data access (Module 11)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tenant import (
    ApiKey,
    AuditLog,
    Invitation,
    Membership,
    Organization,
    StorageQuota,
    Subscription,
    Team,
    Tenant,
    UsageLimit,
    Workspace,
)
from app.models.user import User


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        stmt = select(Tenant).where(
            Tenant.slug == slug, Tenant.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        stmt = select(Tenant).where(
            Tenant.id == tenant_id, Tenant.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_tenant(
        self,
        *,
        name: str,
        slug: str,
        plan: str = "free",
        region: str = "us-east",
    ) -> Tenant:
        tenant = Tenant(name=name, slug=slug, plan=plan, region=region, status="active")
        self._session.add(tenant)
        await self._session.flush()
        return tenant


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[Organization]:
        stmt = (
            select(Organization)
            .where(
                Organization.tenant_id == tenant_id,
                Organization.deleted_at.is_(None),
            )
            .order_by(Organization.name)
            .limit(limit)
            .offset(offset)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def get(self, org_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Organization]:
        stmt = select(Organization).where(
            Organization.id == org_id,
            Organization.tenant_id == tenant_id,
            Organization.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, **kwargs) -> Organization:
        org = Organization(**kwargs)
        self._session.add(org)
        await self._session.flush()
        return org

    async def soft_delete(self, org: Organization) -> None:
        org.deleted_at = datetime.now(timezone.utc)
        org.status = "deleted"
        await self._session.flush()


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_org(
        self, tenant_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> Sequence[Team]:
        stmt = select(Team).where(
            Team.tenant_id == tenant_id, Team.deleted_at.is_(None)
        )
        if organization_id:
            stmt = stmt.where(Team.organization_id == organization_id)
        stmt = stmt.order_by(Team.name)
        return (await self._session.execute(stmt)).scalars().all()

    async def get(self, team_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Team]:
        stmt = select(Team).where(
            Team.id == team_id,
            Team.tenant_id == tenant_id,
            Team.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, **kwargs) -> Team:
        team = Team(**kwargs)
        self._session.add(team)
        await self._session.flush()
        return team

    async def soft_delete(self, team: Team) -> None:
        team.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> Membership:
        m = Membership(**kwargs)
        self._session.add(m)
        await self._session.flush()
        return m

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Membership]:
        stmt = select(Membership).where(
            Membership.user_id == user_id, Membership.is_active.is_(True)
        )
        return (await self._session.execute(stmt)).scalars().all()


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> Invitation:
        inv = Invitation(**kwargs)
        self._session.add(inv)
        await self._session.flush()
        return inv

    async def get_by_token(self, token: str) -> Optional[Invitation]:
        stmt = select(Invitation).where(
            Invitation.token == token, Invitation.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_pending(self, tenant_id: uuid.UUID) -> Sequence[Invitation]:
        stmt = (
            select(Invitation)
            .where(
                Invitation.tenant_id == tenant_id,
                Invitation.status == "pending",
                Invitation.deleted_at.is_(None),
            )
            .order_by(Invitation.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> AuditLog:
        row = AuditLog(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def list(
        self,
        tenant_id: uuid.UUID,
        *,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        filters = [AuditLog.tenant_id == tenant_id]
        if action:
            filters.append(AuditLog.action == action)
        count_stmt = select(func.count()).select_from(AuditLog).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        stmt = (
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> ApiKey:
        key = ApiKey(**kwargs)
        self._session.add(key)
        await self._session.flush()
        return key

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.tenant_id == tenant_id, ApiKey.deleted_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def get(self, key_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == tenant_id,
            ApiKey.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
            ApiKey.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def soft_delete(self, key: ApiKey) -> None:
        key.deleted_at = datetime.now(timezone.utc)
        key.is_active = False
        await self._session.flush()


class QuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_storage(self, tenant_id: uuid.UUID) -> Optional[StorageQuota]:
        stmt = select(StorageQuota).where(StorageQuota.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_subscription(self, tenant_id: uuid.UUID) -> Optional[Subscription]:
        stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_usage(self, tenant_id: uuid.UUID) -> Optional[UsageLimit]:
        stmt = select(UsageLimit).where(UsageLimit.tenant_id == tenant_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def ensure_defaults(self, tenant_id: uuid.UUID, plan: str = "enterprise") -> None:
        if await self.get_storage(tenant_id) is None:
            self._session.add(
                StorageQuota(tenant_id=tenant_id, quota_bytes=10 * 1024**3)
            )
        if await self.get_subscription(tenant_id) is None:
            self._session.add(
                Subscription(tenant_id=tenant_id, plan=plan, status="active", seats=100)
            )
        if await self.get_usage(tenant_id) is None:
            self._session.add(UsageLimit(tenant_id=tenant_id))
        await self._session.flush()


class AdminUserRepository:
    """Tenant-scoped user listing for admin console."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_users(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[Sequence[User], int]:
        filters = [User.tenant_id == tenant_id, User.deleted_at.is_(None)]
        if status:
            filters.append(User.status == status)
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(User).where(*filters)
                )
            ).scalar_one()
        )
        stmt = (
            select(User)
            .where(*filters)
            .options(selectinload(User.roles))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self._session.execute(stmt)).scalars().all()
        return items, total

    async def get_in_tenant(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Optional[User]:
        stmt = (
            select(User)
            .where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.roles))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
