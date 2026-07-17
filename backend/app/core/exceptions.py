"""
Centralized exception types and FastAPI exception handlers.

All API errors are returned as a consistent JSON envelope:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable summary",
    "details": [...]
  },
  "path": "/api/v1/...",
  "request_id": "..."
}
```
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception with an HTTP status and machine code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


def _request_id(request: Request) -> str:
    """Read or create a correlation id for the request."""
    return request.headers.get("X-Request-ID") or str(uuid4())


def _error_payload(
    *,
    code: str,
    message: str,
    path: str,
    request_id: str,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "path": path,
        "request_id": request_id,
    }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle known application exceptions."""
    request_id = _request_id(request)
    logger.warning(
        "AppException | code=%s | path=%s | request_id=%s | message=%s",
        exc.code,
        request.url.path,
        request_id,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            request_id=request_id,
            details=exc.details,
        ),
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI / Starlette HTTPException."""
    request_id = _request_id(request)
    detail = exc.detail
    message = detail if isinstance(detail, str) else "HTTP error"
    details = None if isinstance(detail, str) else detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code="HTTP_ERROR",
            message=message,
            path=request.url.path,
            request_id=request_id,
            details=details,
        ),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic / FastAPI request validation errors."""
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            path=request.url.path,
            request_id=request_id,
            details=exc.errors(),
        ),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions (never leak internals in production)."""
    request_id = _request_id(request)
    logger.exception(
        "Unhandled exception | path=%s | request_id=%s",
        request.url.path,
        request_id,
    )
    from app.core.config import settings

    message = (
        str(exc) if settings.is_development else "An unexpected error occurred"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message=message,
            path=request.url.path,
            request_id=request_id,
            details=None,
        ),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
