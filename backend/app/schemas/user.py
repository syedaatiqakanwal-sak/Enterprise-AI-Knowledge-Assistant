"""User profile and management schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


_PHONE_PATTERN = re.compile(r"^\+?[0-9\s\-()]{7,20}$")
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$"
)


def validate_password_strength(value: str) -> str:
    """Enforce enterprise password policy."""
    if not _PASSWORD_PATTERN.match(value):
        raise ValueError(
            "Password must be 8–128 characters and include uppercase, lowercase, "
            "digit, and special character"
        )
    return value


class RoleOut(BaseModel):
    """Public role representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None


class UserOut(BaseModel):
    """Public user profile (never includes password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    roles: list[RoleOut] = Field(default_factory=list)
    role: Optional[str] = None  # primary: admin | manager | employee
    permissions: list[str] = Field(default_factory=list)
    tenant_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None


class UpdateProfileRequest(BaseModel):
    """Authenticated user profile update."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "full_name": "Jane Doe",
                    "phone": "+1 555-0100",
                }
            ]
        }
    )

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("full_name must contain at least 2 characters")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value.strip() == "":
            return None
        cleaned = value.strip()
        if not _PHONE_PATTERN.match(cleaned):
            raise ValueError("Invalid phone number format")
        return cleaned


class ChangePasswordRequest(BaseModel):
    """Change password while authenticated."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "current_password": "OldPass123!",
                    "new_password": "NewPass123!",
                }
            ]
        }
    )

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserListOut(BaseModel):
    """Paginated users list."""

    items: list[UserOut]
    total: int
    limit: int
    offset: int
