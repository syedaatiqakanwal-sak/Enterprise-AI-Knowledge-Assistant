"""
Unified API response envelope (Module 3).

Success:
  { "success": true, "message": "...", "data": {}, "errors": null }

Error:
  { "success": false, "message": "...", "errors": {} }
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard envelope for every Module 3 API response."""

    success: bool = True
    message: str = "OK"
    data: Optional[T] = None
    errors: Optional[Any] = None

    @classmethod
    def ok(
        cls,
        data: T | None = None,
        *,
        message: str = "OK",
    ) -> "ApiResponse[T]":
        """Build a successful response."""
        return cls(success=True, message=message, data=data, errors=None)

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        errors: Any = None,
    ) -> "ApiResponse[None]":
        """Build a failed response."""
        return cls(success=False, message=message, data=None, errors=errors or {})


class PaginatedUsers(BaseModel):
    """Paginated user list payload."""

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0
