"""
Authentication API routes — Module 3.

Presentation layer only; business logic lives in AuthService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import get_current_user
from app.middlewares.rate_limit import enforce_rate_limit
from app.models.user import User
from app.schemas.auth import (
    AuthData,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.response import ApiResponse
from app.schemas.token import TokenPair
from app.schemas.user import ChangePasswordRequest
from app.services.auth_service import AuthService
from app.utils.sanitize import sanitize_email, sanitize_text

router = APIRouter()


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return ip, request.headers.get("User-Agent")


@router.post(
    "/register",
    response_model=ApiResponse[AuthData],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        201: {
            "description": "User registered",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Registration successful",
                        "data": {
                            "user": {"email": "jane@company.com", "is_verified": False},
                            "tokens": {"token_type": "bearer", "expires_in": 1800},
                        },
                        "errors": None,
                    }
                }
            },
        }
    },
)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AuthData]:
    """Create an employee account, send verification email, and return tokens."""
    await enforce_rate_limit(request, scope="auth_register")
    ip, ua = _client_meta(request)
    data = await AuthService(db).register(
        email=sanitize_email(str(payload.email)),
        password=payload.password,
        full_name=sanitize_text(payload.full_name),
        phone=payload.phone,
        ip_address=ip,
        user_agent=ua,
    )
    return ApiResponse.ok(data, message="Registration successful")


@router.post(
    "/login",
    response_model=ApiResponse[AuthData],
    summary="Login with email and password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AuthData]:
    """Authenticate and issue access + refresh tokens."""
    await enforce_rate_limit(request, scope="auth_login")
    ip, ua = _client_meta(request)
    data = await AuthService(db).login(
        email=sanitize_email(str(payload.email)),
        password=payload.password,
        ip_address=ip,
        user_agent=ua,
    )
    return ApiResponse.ok(data, message="Login successful")


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    summary="Logout and revoke refresh token",
)
async def logout(
    payload: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Revoke the provided refresh token."""
    await enforce_rate_limit(request, scope="auth_logout")
    message = await AuthService(db).logout(refresh_token=payload.refresh_token)
    return ApiResponse.ok(None, message=message)


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPair],
    summary="Refresh access token",
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenPair]:
    """Rotate refresh token and return a new access token pair."""
    await enforce_rate_limit(request, scope="auth_refresh")
    ip, ua = _client_meta(request)
    tokens = await AuthService(db).refresh(
        refresh_token=payload.refresh_token,
        ip_address=ip,
        user_agent=ua,
    )
    return ApiResponse.ok(tokens, message="Token refreshed")


@router.post(
    "/forgot-password",
    response_model=ApiResponse[None],
    summary="Request password reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Send a password-reset token if the account exists (anti-enumeration)."""
    await enforce_rate_limit(request, scope="auth_forgot", limit=5)
    message = await AuthService(db).forgot_password(
        email=sanitize_email(str(payload.email))
    )
    return ApiResponse.ok(None, message=message)


@router.post(
    "/reset-password",
    response_model=ApiResponse[None],
    summary="Reset password with token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Set a new password using a one-time reset token (30-minute expiry)."""
    await enforce_rate_limit(request, scope="auth_reset", limit=5)
    message = await AuthService(db).reset_password(
        token=payload.token,
        new_password=payload.new_password,
    )
    return ApiResponse.ok(None, message=message)


@router.post(
    "/verify-email",
    response_model=ApiResponse[None],
    summary="Verify email with token",
)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Confirm email ownership using the verification token from registration."""
    await enforce_rate_limit(request, scope="auth_verify")
    message = await AuthService(db).verify_email(token=payload.token)
    return ApiResponse.ok(None, message=message)


@router.post(
    "/change-password",
    response_model=ApiResponse[None],
    summary="Change password (authenticated)",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Change the authenticated user's password and revoke all sessions."""
    await enforce_rate_limit(request, scope="auth_change_password")
    message = await AuthService(db).change_password(
        current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return ApiResponse.ok(None, message=message)
