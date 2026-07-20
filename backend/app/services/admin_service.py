"""Enterprise Multi-Tenant SaaS Administration service (Module 11)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import get_password_hash
from app.middlewares.tenant_context import get_tenant_context, set_tenant_context, TenantContext
from app.models.document import Document
from app.models.meeting import Meeting
from app.models.ocr import OCRDocument
from app.models.tenant import Organization, Team, Workspace
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.tenant_repository import (
    AdminUserRepository,
    ApiKeyRepository,
    AuditLogRepository,
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    QuotaRepository,
    TeamRepository,
    TenantRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.admin import (
    AdminUserUpdate,
    ApiKeyCreate,
    InviteUserRequest,
    OrganizationCreate,
    OrganizationUpdate,
    TeamCreate,
    TeamUpdate,
)
from app.utils.tokens import generate_url_safe_token, hash_token


def _serialize_org(org: Organization) -> dict[str, Any]:
    return {
        "id": str(org.id),
        "tenant_id": str(org.tenant_id),
        "name": org.name,
        "logo_url": org.logo_url,
        "brand_primary": org.brand_primary,
        "brand_secondary": org.brand_secondary,
        "domain": org.domain,
        "timezone": org.timezone,
        "language": org.language,
        "region": org.region,
        "ai_settings": org.ai_settings or {},
        "storage_settings": org.storage_settings or {},
        "status": org.status,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


def _serialize_team(team: Team) -> dict[str, Any]:
    return {
        "id": str(team.id),
        "tenant_id": str(team.tenant_id),
        "organization_id": str(team.organization_id),
        "name": team.name,
        "description": team.description,
        "manager_id": str(team.manager_id) if team.manager_id else None,
        "created_at": team.created_at.isoformat() if team.created_at else None,
    }


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "status": getattr(user, "status", None) or ("active" if user.is_active else "disabled"),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "team_id": str(user.team_id) if user.team_id else None,
        "roles": [r.name for r in (user.roles or [])],
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tenants = TenantRepository(session)
        self._orgs = OrganizationRepository(session)
        self._teams = TeamRepository(session)
        self._memberships = MembershipRepository(session)
        self._invites = InvitationRepository(session)
        self._audit = AuditLogRepository(session)
        self._api_keys = ApiKeyRepository(session)
        self._quotas = QuotaRepository(session)
        self._admin_users = AdminUserRepository(session)
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)

    async def resolve_tenant_id(self, actor: User) -> uuid.UUID:
        tid = actor.tenant_id or get_tenant_context().tenant_id
        if tid is None:
            default = await self._tenants.get_by_slug(settings.DEFAULT_TENANT_SLUG)
            if default is None:
                raise AppException(
                    "No tenant configured",
                    code="TENANT_MISSING",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            tid = default.id
            if actor.tenant_id is None:
                actor.tenant_id = tid
                if default.organizations:
                    pass
                orgs = await self._orgs.list_for_tenant(tid, limit=1)
                if orgs and actor.organization_id is None:
                    actor.organization_id = orgs[0].id
                await self._session.flush()
        set_tenant_context(
            TenantContext(
                tenant_id=tid,
                organization_id=actor.organization_id,
                team_id=actor.team_id,
                user_id=actor.id,
                auth_mode="jwt",
            )
        )
        return tid

    async def audit(
        self,
        *,
        tenant_id: uuid.UUID | None,
        actor: User | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict | None = None,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> None:
        await self._audit.create(
            tenant_id=tenant_id,
            actor_id=actor.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    # --- Organizations ---

    async def list_organizations(self, actor: User) -> list[dict[str, Any]]:
        tid = await self.resolve_tenant_id(actor)
        orgs = await self._orgs.list_for_tenant(tid)
        return [_serialize_org(o) for o in orgs]

    async def create_organization(
        self, actor: User, payload: OrganizationCreate
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        org = await self._orgs.create(
            tenant_id=tid,
            name=payload.name,
            domain=payload.domain,
            timezone=payload.timezone,
            language=payload.language,
            region=payload.region,
            logo_url=payload.logo_url,
            brand_primary=payload.brand_primary,
            brand_secondary=payload.brand_secondary,
            ai_settings=payload.ai_settings,
            storage_settings=payload.storage_settings,
            status="active",
        )
        self._session.add(
            Workspace(
                tenant_id=tid,
                organization_id=org.id,
                name="Default Workspace",
                is_default=True,
            )
        )
        await self._session.flush()
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.organization.create",
            resource_type="organization",
            resource_id=str(org.id),
            details={"name": org.name},
        )
        await self._session.commit()
        return _serialize_org(org)

    async def update_organization(
        self, actor: User, org_id: uuid.UUID, payload: OrganizationUpdate
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        org = await self._orgs.get(org_id, tid)
        if org is None:
            raise AppException(
                "Organization not found",
                code="ORG_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(org, key, value)
        await self._session.flush()
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.organization.update",
            resource_type="organization",
            resource_id=str(org.id),
            details=data,
        )
        await self._session.commit()
        return _serialize_org(org)

    async def delete_organization(self, actor: User, org_id: uuid.UUID) -> None:
        tid = await self.resolve_tenant_id(actor)
        org = await self._orgs.get(org_id, tid)
        if org is None:
            raise AppException(
                "Organization not found",
                code="ORG_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._orgs.soft_delete(org)
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.organization.delete",
            resource_type="organization",
            resource_id=str(org.id),
        )
        await self._session.commit()

    # --- Teams ---

    async def list_teams(
        self, actor: User, organization_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        tid = await self.resolve_tenant_id(actor)
        teams = await self._teams.list_for_org(tid, organization_id)
        return [_serialize_team(t) for t in teams]

    async def create_team(self, actor: User, payload: TeamCreate) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        org = await self._orgs.get(payload.organization_id, tid)
        if org is None:
            raise AppException(
                "Organization not found",
                code="ORG_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        team = await self._teams.create(
            tenant_id=tid,
            organization_id=org.id,
            name=payload.name,
            description=payload.description,
            manager_id=payload.manager_id,
        )
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.team.create",
            resource_type="team",
            resource_id=str(team.id),
            details={"name": team.name},
        )
        await self._session.commit()
        return _serialize_team(team)

    async def update_team(
        self, actor: User, team_id: uuid.UUID, payload: TeamUpdate
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        team = await self._teams.get(team_id, tid)
        if team is None:
            raise AppException(
                "Team not found",
                code="TEAM_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(team, key, value)
        await self._session.flush()
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.team.update",
            resource_type="team",
            resource_id=str(team.id),
            details=data,
        )
        await self._session.commit()
        return _serialize_team(team)

    async def delete_team(self, actor: User, team_id: uuid.UUID) -> None:
        tid = await self.resolve_tenant_id(actor)
        team = await self._teams.get(team_id, tid)
        if team is None:
            raise AppException(
                "Team not found",
                code="TEAM_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._teams.soft_delete(team)
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.team.delete",
            resource_type="team",
            resource_id=str(team.id),
        )
        await self._session.commit()

    async def assign_team_members(
        self,
        actor: User,
        team_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        manager_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        team = await self._teams.get(team_id, tid)
        if team is None:
            raise AppException(
                "Team not found",
                code="TEAM_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if manager_id is not None:
            team.manager_id = manager_id
        assigned = 0
        for uid in user_ids:
            user = await self._admin_users.get_in_tenant(uid, tid)
            if user is None:
                continue
            user.team_id = team.id
            user.organization_id = team.organization_id
            await self._memberships.create(
                tenant_id=tid,
                user_id=user.id,
                organization_id=team.organization_id,
                team_id=team.id,
                role_in_org="member",
                is_active=True,
            )
            assigned += 1
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.team.assign",
            resource_type="team",
            resource_id=str(team.id),
            details={"assigned": assigned, "manager_id": str(manager_id) if manager_id else None},
        )
        await self._session.commit()
        return _serialize_team(team)

    # --- Users ---

    async def list_users(
        self,
        actor: User,
        *,
        limit: int = 100,
        offset: int = 0,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        items, total = await self._admin_users.list_users(
            tid, limit=limit, offset=offset, status=status_filter
        )
        return {
            "items": [_serialize_user(u) for u in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def invite_user(
        self, actor: User, payload: InviteUserRequest
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        org_id = payload.organization_id or actor.organization_id
        if org_id is None:
            orgs = await self._orgs.list_for_tenant(tid, limit=1)
            if not orgs:
                raise AppException(
                    "No organization available",
                    code="ORG_REQUIRED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            org_id = orgs[0].id
        else:
            org = await self._orgs.get(org_id, tid)
            if org is None:
                raise AppException(
                    "Organization not found",
                    code="ORG_NOT_FOUND",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        existing = await self._users.get_by_email(str(payload.email))
        if existing and existing.tenant_id == tid:
            raise AppException(
                "User already exists in this tenant",
                code="USER_EXISTS",
                status_code=status.HTTP_409_CONFLICT,
            )

        token = generate_url_safe_token(32)
        expires = datetime.now(timezone.utc) + timedelta(
            hours=settings.INVITE_EXPIRE_HOURS
        )
        invite = await self._invites.create(
            tenant_id=tid,
            organization_id=org_id,
            team_id=payload.team_id,
            email=str(payload.email).lower(),
            role=payload.role,
            token=token,
            invited_by=actor.id,
            status="pending",
            expires_at=expires,
        )

        # Provision a disabled placeholder account until invite accepted
        temp_password = secrets.token_urlsafe(16)
        user = await self._users.create(
            email=str(payload.email),
            hashed_password=get_password_hash(temp_password),
            full_name=payload.full_name or str(payload.email).split("@")[0],
            is_verified=False,
            tenant_id=tid,
            organization_id=org_id,
            team_id=payload.team_id,
            status="disabled",
        )
        user.is_active = False
        role = await self._roles.get_by_name(payload.role)
        if role is None:
            role = await self._roles.get_by_name("employee")
        if role is not None:
            await self._users.assign_role(user, role)
        await self._memberships.create(
            tenant_id=tid,
            user_id=user.id,
            organization_id=org_id,
            team_id=payload.team_id,
            role_in_org=payload.role,
            is_active=False,
        )
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.user.invite",
            resource_type="invitation",
            resource_id=str(invite.id),
            details={"email": invite.email, "role": invite.role},
        )
        await self._session.commit()
        return {
            "invitation_id": str(invite.id),
            "email": invite.email,
            "role": invite.role,
            "token": token,
            "expires_at": invite.expires_at.isoformat(),
            "user_id": str(user.id),
            "status": invite.status,
        }

    async def update_user(
        self, actor: User, user_id: uuid.UUID, payload: AdminUserUpdate
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        user = await self._admin_users.get_in_tenant(user_id, tid)
        if user is None:
            raise AppException(
                "User not found in tenant",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        data = payload.model_dump(exclude_unset=True)
        if "full_name" in data and data["full_name"] is not None:
            user.full_name = data["full_name"]
        if "organization_id" in data:
            user.organization_id = data["organization_id"]
        if "team_id" in data:
            user.team_id = data["team_id"]
        if "status" in data and data["status"] is not None:
            user.status = data["status"]
            if data["status"] in ("suspended", "disabled"):
                user.is_active = False
            elif data["status"] == "active":
                user.is_active = True
        if "is_active" in data and data["is_active"] is not None:
            user.is_active = data["is_active"]
            if not data["is_active"] and user.status == "active":
                user.status = "disabled"
            elif data["is_active"]:
                user.status = "active"
        if data.get("reset_password"):
            await self._users.set_password(
                user, get_password_hash(data["reset_password"])
            )
        if data.get("roles") is not None:
            # Replace role assignments
            from app.models.associations import UserRole
            from sqlalchemy import delete

            await self._session.execute(
                delete(UserRole).where(UserRole.user_id == user.id)
            )
            for role_name in data["roles"]:
                role = await self._roles.get_by_name(role_name)
                if role is not None:
                    await self._users.assign_role(user, role)
        await self._session.flush()
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.user.update",
            resource_type="user",
            resource_id=str(user.id),
            details={k: v for k, v in data.items() if k != "reset_password"},
        )
        await self._session.commit()
        fresh = await self._admin_users.get_in_tenant(user_id, tid)
        return _serialize_user(fresh or user)

    async def delete_user(self, actor: User, user_id: uuid.UUID) -> None:
        tid = await self.resolve_tenant_id(actor)
        user = await self._admin_users.get_in_tenant(user_id, tid)
        if user is None:
            raise AppException(
                "User not found in tenant",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if user.id == actor.id:
            raise AppException(
                "Cannot delete yourself",
                code="SELF_DELETE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._users.soft_delete(user)
        user.status = "disabled"
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.user.delete",
            resource_type="user",
            resource_id=str(user.id),
        )
        await self._session.commit()

    # --- Audit / Storage / API keys / Subscription ---

    async def list_audit(
        self,
        actor: User,
        *,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        items, total = await self._audit.list(
            tid, action=action, limit=limit, offset=offset
        )
        return {
            "items": [
                {
                    "id": str(r.id),
                    "tenant_id": str(r.tenant_id) if r.tenant_id else None,
                    "actor_id": str(r.actor_id) if r.actor_id else None,
                    "action": r.action,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "details": r.details or {},
                    "success": r.success,
                    "ip_address": r.ip_address,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def storage_dashboard(self, actor: User) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        await self._quotas.ensure_defaults(tid)
        quota = await self._quotas.get_storage(tid)
        usage = await self._quotas.get_usage(tid)
        subscription = await self._quotas.get_subscription(tid)

        # Live counts (best-effort; company_id may equal tenant_id)
        doc_bytes = int(
            (
                await self._session.execute(
                    select(func.coalesce(func.sum(Document.size), 0)).where(
                        Document.deleted_at.is_(None),
                        (Document.company_id == tid) | (Document.company_id.is_(None)),
                    )
                )
            ).scalar_one()
            or 0
        )
        meetings_count = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Meeting).where(
                        Meeting.deleted_at.is_(None)
                    )
                )
            ).scalar_one()
        )
        ocr_count = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(OCRDocument).where(
                        OCRDocument.deleted_at.is_(None)
                    )
                )
            ).scalar_one()
        )

        used = doc_bytes
        if quota:
            quota.documents_bytes = doc_bytes
            quota.used_bytes = used
            await self._session.flush()

        return {
            "tenant_id": str(tid),
            "quota_bytes": quota.quota_bytes if quota else 0,
            "used_bytes": used,
            "breakdown": {
                "documents": doc_bytes,
                "ocr": quota.ocr_bytes if quota else 0,
                "meetings": quota.meetings_bytes if quota else 0,
                "embeddings": quota.embeddings_bytes if quota else 0,
                "images": quota.images_bytes if quota else 0,
            },
            "counts": {
                "meetings": meetings_count,
                "ocr_documents": ocr_count,
            },
            "usage_limits": {
                "max_documents": usage.max_documents if usage else 0,
                "max_meetings": usage.max_meetings if usage else 0,
                "max_ocr": usage.max_ocr if usage else 0,
                "max_chats": usage.max_chats if usage else 0,
                "max_agent_runs": usage.max_agent_runs if usage else 0,
                "max_embeddings": usage.max_embeddings if usage else 0,
                "max_storage_bytes": usage.max_storage_bytes if usage else 0,
                "used_documents": usage.used_documents if usage else 0,
                "used_meetings": usage.used_meetings if usage else 0,
                "used_ocr": usage.used_ocr if usage else 0,
                "used_chats": usage.used_chats if usage else 0,
                "used_agent_runs": usage.used_agent_runs if usage else 0,
                "used_embeddings": usage.used_embeddings if usage else 0,
            }
            if usage
            else {},
            "subscription": {
                "plan": subscription.plan if subscription else "free",
                "status": subscription.status if subscription else "active",
                "seats": subscription.seats if subscription else 5,
                "renews_at": (
                    subscription.renews_at.isoformat()
                    if subscription and subscription.renews_at
                    else None
                ),
            },
        }

    async def list_api_keys(self, actor: User) -> list[dict[str, Any]]:
        tid = await self.resolve_tenant_id(actor)
        keys = await self._api_keys.list_for_tenant(tid)
        return [
            {
                "id": str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "scopes": k.scopes or [],
                "is_active": k.is_active,
                "usage_count": k.usage_count,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in keys
        ]

    async def create_api_key(
        self, actor: User, payload: ApiKeyCreate
    ) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        raw = settings.API_KEY_PREFIX + secrets.token_urlsafe(32)
        prefix = raw[:12]
        key = await self._api_keys.create(
            tenant_id=tid,
            organization_id=payload.organization_id or actor.organization_id,
            name=payload.name,
            key_prefix=prefix,
            key_hash=hash_token(raw),
            scopes=payload.scopes,
            created_by=actor.id,
            expires_at=payload.expires_at,
            is_active=True,
        )
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.api_key.create",
            resource_type="api_key",
            resource_id=str(key.id),
            details={"name": key.name, "scopes": payload.scopes},
        )
        await self._session.commit()
        return {
            "id": str(key.id),
            "name": key.name,
            "key_prefix": key.key_prefix,
            "scopes": key.scopes or [],
            "api_key": raw,  # shown once
            "is_active": True,
            "created_at": key.created_at.isoformat() if key.created_at else None,
        }

    async def delete_api_key(self, actor: User, key_id: uuid.UUID) -> None:
        tid = await self.resolve_tenant_id(actor)
        key = await self._api_keys.get(key_id, tid)
        if key is None:
            raise AppException(
                "API key not found",
                code="API_KEY_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        await self._api_keys.soft_delete(key)
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.api_key.delete",
            resource_type="api_key",
            resource_id=str(key.id),
        )
        await self._session.commit()

    async def rotate_api_key(self, actor: User, key_id: uuid.UUID) -> dict[str, Any]:
        tid = await self.resolve_tenant_id(actor)
        key = await self._api_keys.get(key_id, tid)
        if key is None:
            raise AppException(
                "API key not found",
                code="API_KEY_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        raw = settings.API_KEY_PREFIX + secrets.token_urlsafe(32)
        key.key_prefix = raw[:12]
        key.key_hash = hash_token(raw)
        key.usage_count = 0
        key.last_used_at = None
        await self._session.flush()
        await self.audit(
            tenant_id=tid,
            actor=actor,
            action="admin.api_key.rotate",
            resource_type="api_key",
            resource_id=str(key.id),
        )
        await self._session.commit()
        return {
            "id": str(key.id),
            "name": key.name,
            "key_prefix": key.key_prefix,
            "api_key": raw,
            "scopes": key.scopes or [],
        }
