"""
Application configuration via Pydantic Settings.

Loads environment variables from the project-root `.env` file and the process
environment. Secrets are never hardcoded — every sensitive value must come
from the environment.

Environment profiles
--------------------
- development: verbose logging, SQL echo, permissive CORS defaults
- testing: isolated settings suitable for pytest / CI
- production: strict CORS, no SQL echo, info-level logging
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/app/core/config.py → project root is parents[3]
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Environment(str, Enum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Central application settings.

    Values are resolved in this order (highest priority first):
    1. Process environment variables
    2. `.env` file at the repository root
    3. Field defaults defined below
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "Enterprise AI Knowledge Assistant"
    PROJECT_DESCRIPTION: str = (
        "Chat with your Company's Knowledge — an enterprise RAG platform "
        "for documents, meetings, OCR, and AI agents."
    )
    PROJECT_VERSION: str = "0.3.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = True

    # Contact (shown in OpenAPI / Swagger)
    CONTACT_NAME: str = "Enterprise AI Knowledge Assistant Team"
    CONTACT_EMAIL: str = "support@example.com"
    CONTACT_URL: str = "https://github.com/syedaatiqakanwal-sak/Enterprise-AI-Knowledge-Assistant"

    # ------------------------------------------------------------------
    # Security / JWT
    # ------------------------------------------------------------------
    SECRET_KEY: str = Field(..., min_length=16)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_EXPIRE_HOURS: int = 1

    # Frontend base URL used in email links
    FRONTEND_URL: str = "http://localhost:3000"

    # Optional SMTP (when unset, emails are logged in development)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    SMTP_TLS: bool = True

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Seed admin (optional — created on startup if set)
    SEED_ADMIN_EMAIL: Optional[str] = None
    SEED_ADMIN_PASSWORD: Optional[str] = None
    SEED_ADMIN_FULL_NAME: str = "System Administrator"

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    DATABASE_URL: Optional[str] = None

    # Pool tuning
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    # ------------------------------------------------------------------
    # MongoDB
    # ------------------------------------------------------------------
    MONGO_URL: str
    MONGO_DB: str
    MONGO_MIN_POOL_SIZE: int = 1
    MONGO_MAX_POOL_SIZE: int = 50

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50

    # ------------------------------------------------------------------
    # Qdrant (wired in a later module; required for env completeness)
    # ------------------------------------------------------------------
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # ------------------------------------------------------------------
    # CORS — stored as a comma-separated string for .env compatibility
    # ------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = str(_BACKEND_DIR / "logs")
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # ------------------------------------------------------------------
    # Optional AI keys (used by later modules)
    # ------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value: Any) -> Any:
        """Accept case-insensitive environment names."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: Any) -> str:
        """Normalize list/JSON CORS values into a comma-separated string."""
        if value is None:
            return "http://localhost:3000,http://localhost:8000"
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return ",".join(str(item).strip() for item in parsed if str(item).strip())
            return stripped
        raise ValueError(f"Invalid BACKEND_CORS_ORIGINS: {value!r}")

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        """Build async DATABASE_URL when it is not supplied explicitly."""
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    @model_validator(mode="after")
    def apply_environment_defaults(self) -> "Settings":
        """Derive DEBUG / LOG_LEVEL from ENVIRONMENT when left at defaults."""
        if self.ENVIRONMENT == Environment.PRODUCTION:
            object.__setattr__(self, "DEBUG", False)
            if self.LOG_LEVEL == "DEBUG":
                object.__setattr__(self, "LOG_LEVEL", "INFO")
        elif self.ENVIRONMENT == Environment.TESTING:
            object.__setattr__(self, "DEBUG", True)
            if self.LOG_LEVEL == "DEBUG":
                object.__setattr__(self, "LOG_LEVEL", "WARNING")
        return self

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == Environment.TESTING

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def cors_origins(self) -> List[str]:
        """Parsed CORS origin list; production must not use wildcard."""
        origins = [
            item.strip()
            for item in self.BACKEND_CORS_ORIGINS.split(",")
            if item.strip()
        ]
        if self.is_production and ("*" in origins):
            raise ValueError("Wildcard CORS is not allowed in production")
        return origins

@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton (safe for FastAPI Depends)."""
    return Settings()


settings = get_settings()
