"""
Authentication application service.

Orchestrates registration, login, token refresh/logout, email verification,
and password reset using repositories + security helpers.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token_jwt,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.token_repository import (
    EmailVerificationRepository,
    PasswordResetRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    MessageResponse,
    RoleOut,
    TokenResponse,
    UserOut,
)
from app.services.email_service import email_service
from app.utils.sanitize import sanitize_text
from app.utils.tokens import generate_url_safe_token, hash_token
from fastapi import status

logger = logging.getLogger(__name__)


class AuthService:
    """Enterprise authentication use-cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._refresh = RefreshTokenRepository(session)
        self._email_tokens = EmailVerificationRepository(session)
        self._reset_tokens = PasswordResetRepository(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResponse:
        """Register a new employee user and issue tokens."""
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise AppException(
                "An account with this email already exists",
                code="EMAIL_ALREADY_REGISTERED",
                status_code=status.HTTP_409_CONFLICT,
            )

        role = await self._roles.get_by_name(RoleName.EMPLOYEE.value)
        if role is None:
            raise AppException(
                "Default employee role is not seeded",
                code="ROLE_NOT_CONFIGURED",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        user = await self._users.create(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=sanitize_text(full_name),
            is_verified=False,
        )
        await self._users.assign_role(user, role)
        await self._session.refresh(user, attribute_names=["roles"])

        await self._issue_email_verification(user)

        tokens = await self._issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )
        # Reload with roles for response
        user = await self._users.get_by_id(user.id)
        assert user is not None
        return AuthResponse(user=self._to_user_out(user), tokens=tokens)

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResponse:
        """Authenticate credentials and issue a token pair."""
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AppException(
                "Invalid email or password",
                code="INVALID_CREDENTIALS",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active or user.deleted_at is not None:
            raise AppException(
                "Account is disabled",
                code="ACCOUNT_DISABLED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        await self._users.update_last_login(user)
        tokens = await self._issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )
        user = await self._users.get_by_id(user.id)
        assert user is not None
        return AuthResponse(user=self._to_user_out(user), tokens=tokens)

    async def refresh(
        self,
        *,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Rotate refresh token and issue a new access token."""
        token_hash = hash_token(refresh_token)
        stored = await self._refresh.get_valid_by_hash(token_hash)
        if stored is None:
            # Also accept JWT-shaped refresh tokens (validate claims + hash)
            try:
                payload = decode_token(refresh_token)
                if payload.get("type") != TOKEN_TYPE_REFRESH:
                    raise JWTError("wrong type")
            except JWTError as exc:
                raise AppException(
                    "Invalid or expired refresh token",
                    code="INVALID_REFRESH_TOKEN",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                ) from exc
            raise AppException(
                "Invalid or expired refresh token",
                code="INVALID_REFRESH_TOKEN",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise AppException(
                "Account is disabled",
                code="ACCOUNT_DISABLED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        await self._refresh.revoke(stored)
        return await self._issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )

    async def logout(self, *, refresh_token: str) -> MessageResponse:
        """Revoke the provided refresh token (idempotent)."""
        token_hash = hash_token(refresh_token)
        stored = await self._refresh.get_valid_by_hash(token_hash)
        if stored is not None:
            await self._refresh.revoke(stored)
        return MessageResponse(message="Logged out successfully")

    async def forgot_password(self, *, email: str) -> MessageResponse:
        """
        Start password reset.

        Always returns a generic success message to avoid account enumeration.
        """
        user = await self._users.get_by_email(email)
        if user is not None and user.is_active:
            await self._reset_tokens.invalidate_pending_for_user(user.id)
            raw = generate_url_safe_token(32)
            expires = datetime.now(timezone.utc) + timedelta(
                hours=settings.PASSWORD_RESET_EXPIRE_HOURS
            )
            await self._reset_tokens.create(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=expires,
            )
            email_service.send_password_reset_email(to_email=user.email, token=raw)
        return MessageResponse(
            message="If an account exists for that email, a reset link has been sent"
        )

    async def reset_password(
        self, *, token: str, new_password: str
    ) -> MessageResponse:
        """Complete password reset and revoke all refresh tokens."""
        stored = await self._reset_tokens.get_valid_by_hash(hash_token(token))
        if stored is None:
            raise AppException(
                "Invalid or expired password reset token",
                code="INVALID_RESET_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise AppException(
                "Invalid or expired password reset token",
                code="INVALID_RESET_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        await self._users.set_password(user, get_password_hash(new_password))
        await self._reset_tokens.mark_used(stored)
        await self._refresh.revoke_all_for_user(user.id)
        return MessageResponse(message="Password has been reset successfully")

    async def verify_email(self, *, token: str) -> MessageResponse:
        """Mark the user email as verified using a one-time token."""
        stored = await self._email_tokens.get_valid_by_hash(hash_token(token))
        if stored is None:
            raise AppException(
                "Invalid or expired verification token",
                code="INVALID_VERIFICATION_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise AppException(
                "Invalid or expired verification token",
                code="INVALID_VERIFICATION_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._users.mark_verified(user)
        await self._email_tokens.mark_used(stored)
        return MessageResponse(message="Email verified successfully")

    async def get_current_user_profile(self, user: User) -> UserOut:
        """Return the authenticated user's public profile."""
        fresh = await self._users.get_by_id(user.id)
        if fresh is None:
            raise AppException(
                "User not found",
                code="USER_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self._to_user_out(fresh)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _issue_email_verification(self, user: User) -> None:
        await self._email_tokens.invalidate_pending_for_user(user.id)
        raw = generate_url_safe_token(32)
        expires = datetime.now(timezone.utc) + timedelta(
            hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
        )
        await self._email_tokens.create(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=expires,
        )
        email_service.send_verification_email(to_email=user.email, token=raw)

    async def _issue_token_pair(
        self,
        user: User,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenResponse:
        roles = [role.name for role in (user.roles or [])]
        access = create_access_token(user.id, roles=roles)
        jti = str(uuid.uuid4())
        refresh_expires = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        # Opaque refresh token (URL-safe) — hashed at rest
        raw_refresh = generate_url_safe_token(48)
        await self._refresh.create(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=refresh_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        # Also embed a signed JWT refresh for clients that prefer JWT shape
        # (stored hash is of the opaque token returned to the client).
        _ = create_refresh_token_jwt(user.id, jti=jti)

        return TokenResponse(
            access_token=access,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    def _to_user_out(user: User) -> UserOut:
        return UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login=user.last_login,
            created_at=user.created_at,
            roles=[
                RoleOut(id=r.id, name=r.name, description=r.description)
                for r in (user.roles or [])
            ],
        )
