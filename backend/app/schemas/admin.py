"""Pydantic schemas for Multi-Tenant SaaS Administration (Module 11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    region: str = "us-east"
    logo_url: Optional[str] = None
    brand_primary: Optional[str] = None
    brand_secondary: Optional[str] = None
    ai_settings: Optional[dict[str, Any]] = None
    storage_settings: Optional[dict[str, Any]] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    region: Optional[str] = None
    logo_url: Optional[str] = None
    brand_primary: Optional[str] = None
    brand_secondary: Optional[str] = None
    ai_settings: Optional[dict[str, Any]] = None
    storage_settings: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization_id: UUID
    description: Optional[str] = None
    manager_id: Optional[UUID] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[UUID] = None


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "employee"
    organization_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    full_name: Optional[str] = None


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    status: Optional[str] = None  # active | suspended | disabled
    is_active: Optional[bool] = None
    organization_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    roles: Optional[list[str]] = None
    reset_password: Optional[str] = Field(default=None, min_length=8)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    organization_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None


class AssignTeamRequest(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list)
    manager_id: Optional[UUID] = None
