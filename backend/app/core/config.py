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
    STAGING = "staging"
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
    PROJECT_VERSION: str = "0.12.0"
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
    # Module 3: password-reset tokens expire after 30 minutes (one-time use)
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    # Kept for backward-compatible env files; unused when MINUTES is set
    PASSWORD_RESET_EXPIRE_HOURS: int = 1

    # Frontend base URL used in email links
    FRONTEND_URL: str = "http://127.0.0.1:3000"

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
    # Qdrant + RAG (Module 6)
    # ------------------------------------------------------------------
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "company_documents"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_USE_MEMORY_FALLBACK: bool = True

    # Embeddings
    EMBEDDING_PROVIDER: str = "bge"  # bge | minilm | mock
    EMBEDDING_MODEL_PRIMARY: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_MODEL_FALLBACK: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Optional alias used when EMBEDDING_PROVIDER=minilm (HF id or short name)
    EMBEDDING_MODEL: Optional[str] = None
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_DIM_BGE: int = 1024
    EMBEDDING_DIM_MINILM: int = 384

    # Chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SCORE_THRESHOLD: float = 0.25

    # LLM provider abstraction
    LLM_PROVIDER: str = "gemini"  # openai|gemini|ollama|azure_openai|anthropic|mock
    LLM_MODEL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    # Default local model name — override via env; never hardcode in provider code
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: float = 120.0
    OLLAMA_CONNECT_TIMEOUT: float = 5.0
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Indexing
    AUTO_INDEX_ON_UPLOAD: bool = True
    INDEX_QUEUE_KEY: str = "eai:index_queue"

    # ------------------------------------------------------------------
    # OCR & Vision (Module 7)
    # ------------------------------------------------------------------
    OCR_PROVIDER: str = "mock"  # paddle | easyocr | mock
    OCR_LANG: str = "en"
    OCR_MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    OCR_AUTO_INDEX_RAG: bool = True
    OCR_STORAGE_ROOT: str = str(_BACKEND_DIR / "storage" / "ocr")
    VISION_STORAGE_ROOT: str = str(_BACKEND_DIR / "storage" / "vision")
    YOLO_MODEL: str = "yolov8n.pt"
    YOLO_CONFIDENCE: float = 0.35
    VISION_CAPTION_PROVIDER: str = "mock"  # mock | transformers

    # ------------------------------------------------------------------
    # Meeting Intelligence (Module 8)
    # ------------------------------------------------------------------
    MEETING_PROVIDER: str = "mock"  # whisper | mock
    WHISPER_MODEL: str = "large-v3"
    WHISPER_FALLBACK_MODEL: str = "small"
    MEETING_MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024
    MEETING_AUTO_INDEX_RAG: bool = True
    MEETING_STORAGE_ROOT: str = str(_BACKEND_DIR / "storage" / "meetings")
    MEETING_DIARIZATION_ENABLED: bool = True
    FFMPEG_PATH: str = "ffmpeg"

    # ------------------------------------------------------------------
    # Enterprise AI Agent Platform (Module 9)
    # ------------------------------------------------------------------
    AGENT_ENABLED: bool = True
    AGENT_PROVIDER: str = "mock"  # mock | llm (planner uses LLM when available)
    AGENT_MAX_TOOL_CALLS: int = 8
    AGENT_TIMEOUT_SECONDS: int = 120
    AGENT_MAX_RETRIES: int = 2
    AGENT_MEMORY_TTL_SECONDS: int = 3600
    AGENT_EMAIL_ENABLED: bool = False
    AGENT_EMAIL_REQUIRE_CONFIRMATION: bool = True
    AGENT_WEB_SEARCH_ENABLED: bool = False
    AGENT_SQL_READONLY: bool = True
    AGENT_DEFAULT_TYPE: str = "general_assistant"

    # ------------------------------------------------------------------
    # Analytics & AI Observability (Module 10)
    # ------------------------------------------------------------------
    ANALYTICS_ENABLED: bool = True
    ANALYTICS_LOG_API_REQUESTS: bool = True
    ANALYTICS_SAMPLE_RATE: float = 1.0
    ANALYTICS_COST_PER_1K_PROMPT: float = 0.0005
    ANALYTICS_COST_PER_1K_COMPLETION: float = 0.0015
    ANALYTICS_COST_PER_1K_EMBEDDING: float = 0.0001
    ANALYTICS_ALERT_ERROR_RATE: float = 0.05
    ANALYTICS_ALERT_LLM_LATENCY_MS: float = 5000.0
    ANALYTICS_ALERT_TOKEN_BUDGET: int = 1_000_000

    # ------------------------------------------------------------------
    # Multi-Tenant SaaS Administration (Module 11)
    # ------------------------------------------------------------------
    TENANCY_ENABLED: bool = True
    DEFAULT_TENANT_SLUG: str = "default"
    DEFAULT_TENANT_NAME: str = "Default Tenant"
    API_KEY_PREFIX: str = "eak_"
    INVITE_EXPIRE_HOURS: int = 72
    SSO_ENABLED: bool = False  # abstraction only — Azure AD / Google / Okta / SAML later

    # ------------------------------------------------------------------
    # Production / Observability (Module 12)
    # ------------------------------------------------------------------
    LOG_JSON: bool = False  # structured JSON logs (auto-on in staging/production)
    METRICS_ENABLED: bool = True
    SECURITY_HEADERS_ENABLED: bool = True
    READY_REQUIRE_QDRANT: bool = False  # set true when vector search is mandatory

    # ------------------------------------------------------------------
    # CORS — stored as a comma-separated string for .env compatibility
    # ------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "http://127.0.0.1:8000,http://localhost:8000"
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = str(_BACKEND_DIR / "logs")
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # ------------------------------------------------------------------
    # Document storage (Module 5) — swap STORAGE_BACKEND later for S3/Azure/GCS
    # ------------------------------------------------------------------
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_ROOT: str = str(_BACKEND_DIR / "storage" / "documents")
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS: str = (
        "pdf,docx,txt,csv,xlsx,pptx,png,jpg,jpeg,webp,zip"
    )

    # ------------------------------------------------------------------
    # Optional AI keys (Module 6+)
    # ------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.ALLOWED_EXTENSIONS.split(",")
            if ext.strip()
        }

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

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
            return (
                "http://127.0.0.1:3000,http://localhost:3000,"
                "http://127.0.0.1:8000,http://localhost:8000"
            )
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
            if not self.LOG_JSON:
                object.__setattr__(self, "LOG_JSON", True)
        elif self.ENVIRONMENT == Environment.STAGING:
            object.__setattr__(self, "DEBUG", False)
            if self.LOG_LEVEL == "DEBUG":
                object.__setattr__(self, "LOG_LEVEL", "INFO")
            if not self.LOG_JSON:
                object.__setattr__(self, "LOG_JSON", True)
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
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == Environment.STAGING

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def cors_origins(self) -> List[str]:
        """Parsed CORS origin list; production/staging must not use wildcard."""
        origins = [
            item.strip()
            for item in self.BACKEND_CORS_ORIGINS.split(",")
            if item.strip()
        ]
        if (self.is_production or self.is_staging) and ("*" in origins):
            raise ValueError("Wildcard CORS is not allowed in staging/production")
        return origins


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton (safe for FastAPI Depends)."""
    return Settings()


settings = get_settings()
