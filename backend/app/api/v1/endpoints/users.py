"""
User profile endpoints.

GET /api/v1/users/me — current authenticated user
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.services.auth_service import AuthService

router = APIRouter()


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user",
)
async def read_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Return the profile of the user identified by the Bearer access token."""
    service = AuthService(db)
    return await service.get_current_user_profile(current_user)
