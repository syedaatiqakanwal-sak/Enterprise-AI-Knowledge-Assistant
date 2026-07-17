"""
Authentication endpoints — Module 2B.

POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
POST /api/v1/auth/verify-email
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.rate_limit import enforce_rate_limit
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService
from app.utils.sanitize import sanitize_email, sanitize_text

router = APIRouter()


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )
    return ip, request.headers.get("User-Agent")


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Create an employee account, send verification email, and return tokens."""
    await enforce_rate_limit(request, scope="auth_register")
    ip, ua = _client_meta(request)
    service = AuthService(db)
    return await service.register(
        email=sanitize_email(str(payload.email)),
        password=payload.password,
        full_name=sanitize_text(payload.full_name),
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate and issue access + refresh tokens."""
    await enforce_rate_limit(request, scope="auth_login")
    ip, ua = _client_meta(request)
    service = AuthService(db)
    return await service.login(
        email=sanitize_email(str(payload.email)),
        password=payload.password,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout and revoke refresh token",
)
async def logout(
    payload: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Revoke the provided refresh token."""
    await enforce_rate_limit(request, scope="auth_logout")
    service = AuthService(db)
    return await service.logout(refresh_token=payload.refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate refresh token and return a new access token pair."""
    await enforce_rate_limit(request, scope="auth_refresh")
    ip, ua = _client_meta(request)
    service = AuthService(db)
    return await service.refresh(
        refresh_token=payload.refresh_token,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset email",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a password-reset token if the account exists (anti-enumeration)."""
    await enforce_rate_limit(request, scope="auth_forgot", limit=5)
    service = AuthService(db)
    return await service.forgot_password(email=sanitize_email(str(payload.email)))


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Set a new password using a one-time reset token."""
    await enforce_rate_limit(request, scope="auth_reset", limit=5)
    service = AuthService(db)
    return await service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email with token",
)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Confirm email ownership using the verification token from registration."""
    await enforce_rate_limit(request, scope="auth_verify")
    service = AuthService(db)
    return await service.verify_email(token=payload.token)
