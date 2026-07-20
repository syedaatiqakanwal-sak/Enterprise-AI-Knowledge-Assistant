"""Enterprise Multi-Tenant SaaS Administration API — Module 11."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_admin
from app.middlewares.portal import require_admin_portal
from app.models.user import User
from app.schemas.admin import (
    AdminUserUpdate,
    ApiKeyCreate,
    AssignTeamRequest,
    InviteUserRequest,
    OrganizationCreate,
    OrganizationUpdate,
    TeamCreate,
    TeamUpdate,
)
from app.schemas.response import ApiResponse
from app.services.admin_service import AdminService
from app.services.sso import list_sso_providers

router = APIRouter()


@router.get("/organizations", response_model=ApiResponse[list])
async def list_organizations(
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list]:
    data = await AdminService(db).list_organizations(current_user)
    return ApiResponse.ok(data, message="Organizations")


@router.post("/organizations", response_model=ApiResponse[dict])
async def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).create_organization(current_user, payload)
    return ApiResponse.ok(data, message="Organization created")


@router.put("/organizations/{org_id}", response_model=ApiResponse[dict])
async def update_organization(
    org_id: UUID,
    payload: OrganizationUpdate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).update_organization(current_user, org_id, payload)
    return ApiResponse.ok(data, message="Organization updated")


@router.delete("/organizations/{org_id}", response_model=ApiResponse[dict])
async def delete_organization(
    org_id: UUID,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await AdminService(db).delete_organization(current_user, org_id)
    return ApiResponse.ok({"id": str(org_id)}, message="Organization deleted")


@router.get("/users", response_model=ApiResponse[dict])
async def list_admin_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).list_users(
        current_user, limit=limit, offset=offset, status_filter=status
    )
    return ApiResponse.ok(data, message="Users")


@router.post("/users/invite", response_model=ApiResponse[dict])
async def invite_user(
    payload: InviteUserRequest,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).invite_user(current_user, payload)
    return ApiResponse.ok(data, message="Invitation created")


@router.put("/users/{user_id}", response_model=ApiResponse[dict])
async def update_admin_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).update_user(current_user, user_id, payload)
    return ApiResponse.ok(data, message="User updated")


@router.delete("/users/{user_id}", response_model=ApiResponse[dict])
async def delete_admin_user(
    user_id: UUID,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await AdminService(db).delete_user(current_user, user_id)
    return ApiResponse.ok({"id": str(user_id)}, message="User deleted")


@router.get("/teams", response_model=ApiResponse[list])
async def list_teams(
    organization_id: Optional[UUID] = None,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list]:
    data = await AdminService(db).list_teams(current_user, organization_id)
    return ApiResponse.ok(data, message="Teams")


@router.post("/teams", response_model=ApiResponse[dict])
async def create_team(
    payload: TeamCreate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).create_team(current_user, payload)
    return ApiResponse.ok(data, message="Team created")


@router.put("/teams/{team_id}", response_model=ApiResponse[dict])
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).update_team(current_user, team_id, payload)
    return ApiResponse.ok(data, message="Team updated")


@router.delete("/teams/{team_id}", response_model=ApiResponse[dict])
async def delete_team(
    team_id: UUID,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await AdminService(db).delete_team(current_user, team_id)
    return ApiResponse.ok({"id": str(team_id)}, message="Team deleted")


@router.post("/teams/{team_id}/assign", response_model=ApiResponse[dict])
async def assign_team(
    team_id: UUID,
    payload: AssignTeamRequest,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).assign_team_members(
        current_user, team_id, payload.user_ids, payload.manager_id
    )
    return ApiResponse.ok(data, message="Team members assigned")


@router.get("/audit", response_model=ApiResponse[dict])
async def list_audit(
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).list_audit(
        current_user, action=action, limit=limit, offset=offset
    )
    return ApiResponse.ok(data, message="Audit logs")


@router.get("/storage", response_model=ApiResponse[dict])
async def storage_dashboard(
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).storage_dashboard(current_user)
    return ApiResponse.ok(data, message="Storage dashboard")


@router.get("/api-keys", response_model=ApiResponse[list])
async def list_api_keys(
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list]:
    data = await AdminService(db).list_api_keys(current_user)
    return ApiResponse.ok(data, message="API keys")


@router.post("/api-keys", response_model=ApiResponse[dict])
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).create_api_key(current_user, payload)
    return ApiResponse.ok(data, message="API key created")


@router.delete("/api-keys/{key_id}", response_model=ApiResponse[dict])
async def delete_api_key(
    key_id: UUID,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await AdminService(db).delete_api_key(current_user, key_id)
    return ApiResponse.ok({"id": str(key_id)}, message="API key deleted")


@router.post("/api-keys/{key_id}/rotate", response_model=ApiResponse[dict])
async def rotate_api_key(
    key_id: UUID,
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).rotate_api_key(current_user, key_id)
    return ApiResponse.ok(data, message="API key rotated")


@router.get("/sso/providers", response_model=ApiResponse[list])
async def sso_providers(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list]:
    _ = current_user, db
    return ApiResponse.ok(list_sso_providers(), message="SSO providers (planned)")


@router.get("/subscription", response_model=ApiResponse[dict])
async def subscription_info(
    current_user: User = Depends(require_admin_portal),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AdminService(db).storage_dashboard(current_user)
    return ApiResponse.ok(
        {
            "subscription": data.get("subscription"),
            "usage_limits": data.get("usage_limits"),
            "plans": ["free", "starter", "professional", "enterprise"],
            "payment": None,
            "note": "Subscription architecture only — no payment gateway (Module 12)",
        },
        message="Subscription (placeholder)",
    )
