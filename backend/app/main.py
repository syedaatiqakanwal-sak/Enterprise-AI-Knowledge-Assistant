"""
FastAPI application entrypoint.

Responsibilities
----------------
- Configure OpenAPI / Swagger metadata (logo placeholder, contact, version)
- Wire lifespan: logging + Postgres / Mongo / Redis connect & disconnect
- Register global exception handlers and middleware
- Mount versioned API under ``/api/v1``
- Expose root welcome + ``GET /health`` for infrastructure probes
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.mongodb import MongoDBManager
from app.db.postgres import AsyncSessionLocal, close_postgres, init_postgres
from app.db.redis import RedisManager
from app.db.seed import seed_rbac
from app.middlewares.jwt_auth import JWTAuthMiddleware
from app.middlewares.request_context import RequestContextMiddleware
from app.schemas.health import HealthResponse, RootResponse
from app.services.health_service import health_service

logger = logging.getLogger(__name__)

# Placeholder brand mark for Swagger UI (replace with a real asset later).
SWAGGER_LOGO_URL = (
    "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown lifecycle."""
    setup_logging()
    logger.info(
        "Starting %s v%s [%s]",
        settings.PROJECT_NAME,
        settings.PROJECT_VERSION,
        settings.ENVIRONMENT.value,
    )

    # Connect data stores. Production fails fast; development logs and continues
    # so local tooling can start without full Docker infra when needed.
    await _connect_infrastructure()

    # Seed RBAC roles/permissions when Postgres is available
    try:
        async with AsyncSessionLocal() as session:
            await seed_rbac(session)
        logger.info("RBAC seed completed")
    except Exception as exc:  # noqa: BLE001
        if settings.is_production:
            raise
        logger.warning("RBAC seed skipped: %s", exc)

    yield

    logger.info("Shutting down — closing infrastructure connections")
    await RedisManager.close()
    await MongoDBManager.close()
    await close_postgres()


async def _connect_infrastructure() -> None:
    """Establish Postgres, MongoDB, and Redis connections with env-aware policy."""
    errors: list[str] = []

    try:
        await init_postgres()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"PostgreSQL: {exc}")

    try:
        MongoDBManager.connect()
        if not await MongoDBManager.check_health():
            raise RuntimeError("MongoDB ping failed")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"MongoDB: {exc}")

    try:
        await RedisManager.connect()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Redis: {exc}")

    if errors:
        joined = " | ".join(errors)
        if settings.is_production:
            logger.error("Infrastructure startup failed: %s", joined)
            raise RuntimeError(f"Required infrastructure unavailable: {joined}")
        logger.warning(
            "Infrastructure partially unavailable (continuing in %s): %s",
            settings.ENVIRONMENT.value,
            joined,
        )
    else:
        logger.info("All infrastructure connections established")


def create_application() -> FastAPI:
    """Application factory (Clean Architecture / testability)."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=(
            f"{settings.PROJECT_DESCRIPTION}\n\n"
            f"![Logo]({SWAGGER_LOGO_URL})\n\n"
            "## Module 2B — Enterprise Authentication\n\n"
            "JWT access/refresh tokens, RBAC (Admin / Manager / Employee), "
            "email verification, password reset, rate limiting.\n\n"
            "Core infrastructure from Module 2A remains available."
        ),
        version=settings.PROJECT_VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=None,  # custom Swagger UI below
        redoc_url="/redoc",
        contact={
            "name": settings.CONTACT_NAME,
            "email": settings.CONTACT_EMAIL,
            "url": settings.CONTACT_URL,
        },
        license_info={
            "name": "Proprietary",
            "url": settings.CONTACT_URL,
        },
        lifespan=lifespan,
    )

    # --- Middleware (order: last added = outermost) ---
    application.add_middleware(JWTAuthMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    # Versioned API — all future endpoints mount under /api/v1
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get(
        "/docs",
        include_in_schema=False,
        response_class=HTMLResponse,
    )
    async def custom_swagger_ui() -> HTMLResponse:
        """Swagger UI with project branding."""
        return get_swagger_ui_html(
            openapi_url=application.openapi_url or f"{settings.API_V1_STR}/openapi.json",
            title=f"{settings.PROJECT_NAME} — API Docs",
            swagger_favicon_url=SWAGGER_LOGO_URL,
            swagger_ui_parameters={
                "docExpansion": "list",
                "defaultModelsExpandDepth": 1,
                "displayRequestDuration": True,
                "filter": True,
            },
        )

    @application.get(
        "/",
        response_model=RootResponse,
        tags=["Root"],
        summary="API welcome",
    )
    async def root() -> RootResponse:
        """Root welcome payload with discoverable links."""
        return RootResponse(
            message=f"Welcome to {settings.PROJECT_NAME}",
            version=settings.PROJECT_VERSION,
            environment=settings.ENVIRONMENT.value,
            docs="/docs",
            health="/health",
            api_v1=settings.API_V1_STR,
        )

    @application.get(
        "/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        tags=["Health"],
        summary="Infrastructure health probe",
        description=(
            "Load-balancer / Docker health endpoint. Returns backend status, "
            "Postgres / Mongo / Redis status, version, and environment."
        ),
    )
    async def root_health() -> HealthResponse:
        """Unauthenticated infrastructure health check at ``GET /health``."""
        return await health_service.check()

    return application


app = create_application()
