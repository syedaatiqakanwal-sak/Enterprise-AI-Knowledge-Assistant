"""
Authentication and user Pydantic schemas (API contracts).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$"
)


def _validate_password_strength(value: str) -> str:
    if not _PASSWORD_PATTERN.match(value):
        raise ValueError(
            "Password must be 8–128 characters and include uppercase, lowercase, "
            "digit, and special character"
        )
    return value


class RegisterRequest(BaseModel):
    """User registration payload."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower().strip()

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("full_name must contain at least 2 characters")
        return cleaned

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower().strip()


class RefreshRequest(BaseModel):
    """Refresh-token rotation request."""

    refresh_token: str = Field(..., min_length=20)


class LogoutRequest(BaseModel):
    """Logout / revoke refresh token."""

    refresh_token: str = Field(..., min_length=20)


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset email."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower().strip()


class ResetPasswordRequest(BaseModel):
    """Complete a password reset with a one-time token."""

    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class VerifyEmailRequest(BaseModel):
    """Confirm email ownership with a one-time token."""

    token: str = Field(..., min_length=20)


class TokenResponse(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class MessageResponse(BaseModel):
    """Generic success message."""

    message: str
    success: bool = True


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
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    roles: list[RoleOut] = Field(default_factory=list)


class AuthResponse(BaseModel):
    """Login / register response combining tokens and user profile."""

    user: UserOut
    tokens: TokenResponse
