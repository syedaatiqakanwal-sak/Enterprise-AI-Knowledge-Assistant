"""Pydantic request/response schemas (API contracts)."""

from app.schemas.auth import (
    AuthData,
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.health import HealthResponse, RootResponse, ServicesHealth
from app.schemas.response import ApiResponse
from app.schemas.token import TokenPair
from app.schemas.user import (
    ChangePasswordRequest,
    RoleOut,
    UpdateProfileRequest,
    UserListOut,
    UserOut,
)

__all__ = [
    "ApiResponse",
    "AuthData",
    "AuthResponse",
    "ChangePasswordRequest",
    "ForgotPasswordRequest",
    "HealthResponse",
    "LoginRequest",
    "LogoutRequest",
    "RefreshRequest",
    "RegisterRequest",
    "ResetPasswordRequest",
    "RoleOut",
    "RootResponse",
    "ServicesHealth",
    "TokenPair",
    "TokenResponse",
    "UpdateProfileRequest",
    "UserListOut",
    "UserOut",
    "VerifyEmailRequest",
]
