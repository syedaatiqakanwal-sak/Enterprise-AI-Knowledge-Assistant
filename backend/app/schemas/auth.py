"""
Authentication request/response schemas (Module 3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.token import TokenPair
from app.schemas.user import UserOut, validate_password_strength


class RegisterRequest(BaseModel):
    """User registration payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "jane@company.com",
                    "password": "StrongPass1!",
                    "full_name": "Jane Doe",
                    "phone": "+1 555-0100",
                }
            ]
        }
    )

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=20)

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
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    """Login credentials."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "jane@company.com", "password": "StrongPass1!"}]
        }
    )

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
        return validate_password_strength(value)


class VerifyEmailRequest(BaseModel):
    """Confirm email ownership with a one-time token."""

    token: str = Field(..., min_length=20)


class AuthData(BaseModel):
    """Auth success payload (user + tokens)."""

    user: UserOut
    tokens: TokenPair


# Backward-compatible aliases used by older imports
TokenResponse = TokenPair
AuthResponse = AuthData


class MessageData(BaseModel):
    """Simple message wrapper for envelope data when no entity is returned."""

    detail: str
