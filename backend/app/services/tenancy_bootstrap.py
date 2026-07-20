"""Ensure default tenant / org / quotas exist and attach orphan users (Module 11)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant import (
    Membership,
    Organization,
    StorageQuota,
    Subscription,
    Tenant,
    UsageLimit,
    Workspace,
)
from app.models.user import User

logger = logging.getLogger(__name__)


async def ensure_default_tenant(session: AsyncSession) -> Tenant:
    """Idempotently create the default tenant hierarchy and attach users without a tenant."""
    result = await session.execute(
        select(Tenant).where(
            Tenant.slug == settings.DEFAULT_TENANT_SLUG,
            Tenant.deleted_at.is_(None),
        )
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            name=settings.DEFAULT_TENANT_NAME,
            slug=settings.DEFAULT_TENANT_SLUG,
            status="active",
            plan="enterprise",
            region="us-east",
        )
        session.add(tenant)
        await session.flush()
        logger.info("Created default tenant %s", tenant.slug)

    org_result = await session.execute(
        select(Organization).where(
            Organization.tenant_id == tenant.id,
            Organization.deleted_at.is_(None),
        ).limit(1)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        org = Organization(
            tenant_id=tenant.id,
            name="Default Organization",
            timezone="UTC",
            language="en",
            region="us-east",
            brand_primary="#0ea5e9",
            status="active",
        )
        session.add(org)
        await session.flush()
        session.add(
            Workspace(
                tenant_id=tenant.id,
                organization_id=org.id,
                name="Default Workspace",
                is_default=True,
            )
        )

    sq = (
        await session.execute(
            select(StorageQuota).where(StorageQuota.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if sq is None:
        session.add(StorageQuota(tenant_id=tenant.id, quota_bytes=10 * 1024**3))

    sub = (
        await session.execute(
            select(Subscription).where(Subscription.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        session.add(
            Subscription(
                tenant_id=tenant.id, plan="enterprise", status="active", seats=100
            )
        )

    ul = (
        await session.execute(
            select(UsageLimit).where(UsageLimit.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if ul is None:
        session.add(UsageLimit(tenant_id=tenant.id))

    orphans = (
        await session.execute(
            select(User).where(User.deleted_at.is_(None), User.tenant_id.is_(None))
        )
    ).scalars().all()
    for user in orphans:
        user.tenant_id = tenant.id
        user.organization_id = org.id
        user.status = user.status or "active"
        session.add(
            Membership(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=user.id,
                organization_id=org.id,
                role_in_org="member",
                is_active=True,
            )
        )
        logger.info("Attached user %s to default tenant", user.email)

    await session.flush()
    return tenant
