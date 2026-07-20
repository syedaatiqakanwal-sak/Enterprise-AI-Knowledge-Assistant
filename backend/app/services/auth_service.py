"""
Authentication application service (Module 3).

Orchestrates registration, login, refresh/logout, email verification,
password reset/change using repositories + TokenService / UserService.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import get_password_hash, verify_password
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthData
from app.schemas.token import TokenPair
from app.schemas.user import UserOut
from app.services.token_service import TokenService
from app.services.user_service import UserService
from app.utils.sanitize import sanitize_text
from fastapi import status

logger = logging.getLogger(__name__)


class AuthService:
    """Enterprise authentication use-cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._tokens = TokenService(session)
        self._user_service = UserService(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        phone: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthData:
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
            phone=phone,
            is_verified=False,
        )
        await self._users.assign_role(user, role)
        await self._attach_default_tenant(user)
        await self._tokens.issue_email_verification(user)

        user = await self._users.get_by_id(user.id)
        assert user is not None
        tokens = await self._tokens.issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )
        return AuthData(user=self._user_service.to_user_out(user), tokens=tokens)

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthData:
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
        user_status = getattr(user, "status", None) or "active"
        if user_status in ("suspended", "disabled"):
            raise AppException(
                f"Account is {user_status}",
                code="ACCOUNT_SUSPENDED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if user.tenant_id is None:
            await self._attach_default_tenant(user)

        await self._users.update_last_login(user)
        user = await self._users.get_by_id(user.id)
        assert user is not None
        tokens = await self._tokens.issue_token_pair(
            user, ip_address=ip_address, user_agent=user_agent
        )
        return AuthData(user=self._user_service.to_user_out(user), tokens=tokens)

    async def _attach_default_tenant(self, user: User) -> None:
        from app.services.tenancy_bootstrap import ensure_default_tenant

        tenant = await ensure_default_tenant(self._session)
        if user.tenant_id is None:
            user.tenant_id = tenant.id
        from sqlalchemy import select
        from app.models.tenant import Organization

        if user.organization_id is None:
            org = (
                await self._session.execute(
                    select(Organization)
                    .where(
                        Organization.tenant_id == tenant.id,
                        Organization.deleted_at.is_(None),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if org is not None:
                user.organization_id = org.id
        if not getattr(user, "status", None):
            user.status = "active"
        await self._session.flush()

    async def refresh(
        self,
        *,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        """Rotate refresh token and issue a new access token."""
        stored = await self._tokens.get_valid_refresh(refresh_token)
        if stored is None:
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
        return await self._tokens.rotate_refresh_token(
            refresh_token=refresh_token,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def logout(self, *, refresh_token: str) -> str:
        """Revoke the provided refresh token (idempotent)."""
        await self._tokens.revoke_refresh_token(refresh_token=refresh_token)
        return "Logged out successfully"

    async def forgot_password(self, *, email: str) -> str:
        """Start password reset without revealing whether the account exists."""
        user = await self._users.get_by_email(email)
        if user is not None and user.is_active:
            await self._tokens.issue_password_reset(user)
        return "If an account exists for that email, a reset link has been sent"

    async def reset_password(self, *, token: str, new_password: str) -> str:
        """Complete password reset and revoke all refresh tokens."""
        stored = await self._tokens.consume_password_reset(token)
        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise AppException(
                "Invalid or expired password reset token",
                code="INVALID_RESET_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._users.set_password(user, get_password_hash(new_password))
        await self._tokens.revoke_all_for_user(user.id)
        return "Password has been reset successfully"

    async def verify_email(self, *, token: str) -> str:
        """Mark the user email as verified using a one-time token."""
        stored = await self._tokens.consume_email_verification(token)
        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise AppException(
                "Invalid or expired verification token",
                code="INVALID_VERIFICATION_TOKEN",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        await self._users.mark_verified(user)
        return "Email verified successfully"

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> str:
        """Change password for the authenticated user."""
        await self._user_service.change_password(
            user,
            current_password=current_password,
            new_password=new_password,
        )
        return "Password changed successfully"

    async def get_current_user_profile(self, user: User) -> UserOut:
        """Return the authenticated user's public profile."""
        return await self._user_service.get_me(user)
