"""
Token service — access/refresh issuance, rotation, and revocation.

Stores only hashed refresh tokens. No SQL outside repositories.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.token_repository import (
    EmailVerificationRepository,
    PasswordResetRepository,
)
from app.schemas.token import TokenPair
from app.services.email_service import email_service
from app.utils.tokens import generate_url_safe_token, hash_token
from fastapi import status


class TokenService:
    """Token lifecycle: access JWT + opaque refresh + verification/reset tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._refresh = RefreshTokenRepository(session)
        self._email_tokens = EmailVerificationRepository(session)
        self._reset_tokens = PasswordResetRepository(session)

    async def issue_token_pair(
        self,
        user: User,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        """Create access JWT and persist a hashed refresh token."""
        roles = [role.name for role in (user.roles or [])]
        permissions: list[str] = []
        for role in user.roles or []:
            for perm in role.permissions or []:
                if perm.code not in permissions:
                    permissions.append(perm.code)
        # Primary role: admin > manager > employee
        primary = "employee"
        if "admin" in roles:
            primary = "admin"
        elif "manager" in roles:
            primary = "manager"
        extra: dict = {
            "role": primary,
            "roles": roles,
            "permissions": permissions,
        }
        if user.tenant_id:
            extra["tenant_id"] = str(user.tenant_id)
        if user.organization_id:
            extra["organization_id"] = str(user.organization_id)
        if user.team_id:
            extra["team_id"] = str(user.team_id)
        access = create_access_token(user.id, roles=roles, extra_claims=extra)
        refresh_expires = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        raw_refresh = generate_url_safe_token(48)
        await self._refresh.create(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=refresh_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def rotate_refresh_token(
        self,
        *,
        refresh_token: str,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        """Revoke the presented refresh token and issue a new pair."""
        stored = await self._refresh.get_valid_by_hash(hash_token(refresh_token))
        if stored is None:
            raise AppException(
                "Invalid or expired refresh token",
                code="INVALID_REFRESH_TOKEN",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if stored.user_id != user.id:
            raise AppException(
                "Invalid or expired refresh token",
                code="INVALID_REFRESH_TOKEN",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        await self._refresh.revoke(stored)
        return await self.issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )

    async def revoke_refresh_token(self, *, refresh_token: str) -> None:
        """Idempotently revoke a refresh token."""
        stored = await self._refresh.get_valid_by_hash(hash_token(refresh_token))
        if stored is not None:
            await self._refresh.revoke(stored)

    async def revoke_all_for_user(self, user_id) -> int:
        """Revoke every active refresh token for a user."""
        return await self._refresh.revoke_all_for_user(user_id)

    async def get_valid_refresh(self, refresh_token: str):
        """Return a valid stored refresh-token row or None."""
        return await self._refresh.get_valid_by_hash(hash_token(refresh_token))

    async def issue_email_verification(self, user: User) -> str:
        """Create a one-time email verification token and email it. Returns raw token."""
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
        return raw

    async def consume_email_verification(self, token: str):
        """Validate and mark a verification token used. Returns the token row."""
        stored = await self._email_tokens.get_valid_by_hash(hash_token(token))
        if stored is None:
            raise AppException(
                "Invalid or expired verification token",
                code="INVALID_VERIFICATION_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._email_tokens.mark_used(stored)
        return stored

    async def issue_password_reset(self, user: User) -> str:
        """Create a one-time password-reset token (30 min) and email it."""
        await self._reset_tokens.invalidate_pending_for_user(user.id)
        raw = generate_url_safe_token(32)
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES
        )
        await self._reset_tokens.create(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=expires,
        )
        email_service.send_password_reset_email(to_email=user.email, token=raw)
        return raw

    async def consume_password_reset(self, token: str):
        """Validate and mark a reset token used. Returns the token row."""
        stored = await self._reset_tokens.get_valid_by_hash(hash_token(token))
        if stored is None:
            raise AppException(
                "Invalid or expired password reset token",
                code="INVALID_RESET_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._reset_tokens.mark_used(stored)
        return stored
