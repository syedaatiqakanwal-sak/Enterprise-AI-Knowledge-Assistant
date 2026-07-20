"""
User management API routes — Module 3.

Presentation layer only; business logic lives in UserService.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import (
    get_current_user,
    require_admin,
    require_manager,
)
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.user import UpdateProfileRequest, UserListOut, UserOut
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "/me",
    response_model=ApiResponse[UserOut],
    summary="Get current authenticated user",
)
async def read_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    """Return the profile of the user identified by the Bearer access token."""
    data = await UserService(db).get_me(current_user)
    return ApiResponse.ok(data, message="Current user retrieved")


@router.put(
    "/profile",
    response_model=ApiResponse[UserOut],
    summary="Update current user profile",
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    """Update full name and/or phone for the authenticated user."""
    data = await UserService(db).update_profile(current_user, payload)
    return ApiResponse.ok(data, message="Profile updated")


@router.get(
    "",
    response_model=ApiResponse[UserListOut],
    summary="List users (Admin / Manager)",
)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserListOut]:
    """List active users. Requires Manager or Admin role."""
    data = await UserService(db).list_users(
        requester=current_user, limit=limit, offset=offset
    )
    return ApiResponse.ok(data, message="Users retrieved")


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserOut],
    summary="Get user by ID",
)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UserOut]:
    """
    Fetch a user by UUID.

    Employees may only read themselves; managers/admins may read any user.
    """
    data = await UserService(db).get_by_id(user_id, requester=current_user)
    return ApiResponse.ok(data, message="User retrieved")


@router.delete(
    "/{user_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Soft-delete user (Admin)",
)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    """Soft-delete a user account. Admin only. Cannot delete yourself."""
    await UserService(db).delete_user(user_id, requester=current_user)
    return ApiResponse.ok(None, message="User deleted")
