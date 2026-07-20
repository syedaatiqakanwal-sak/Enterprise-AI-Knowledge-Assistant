"""
Centralized exception types and FastAPI exception handlers (Module 3 envelope).

Error response:
{
  "success": false,
  "message": "...",
  "errors": { "code": "...", "details": ... }
}
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
    return request.headers.get("X-Request-ID") or str(uuid4())


def _error_body(*, message: str, code: str, details: Any = None) -> dict[str, Any]:
    errors: dict[str, Any] = {"code": code}
    if details is not None:
        errors["details"] = details
    return {
        "success": False,
        "message": message,
        "errors": errors,
    }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
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
        content=_error_body(message=exc.message, code=exc.code, details=exc.details),
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = _request_id(request)
    detail = exc.detail
    message = detail if isinstance(detail, str) else "HTTP error"
    details = None if isinstance(detail, str) else detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(message=message, code="HTTP_ERROR", details=details),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(
            message="Request validation failed",
            code="VALIDATION_ERROR",
            details=exc.errors(),
        ),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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
        content=_error_body(
            message=message,
            code="INTERNAL_SERVER_ERROR",
        ),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
