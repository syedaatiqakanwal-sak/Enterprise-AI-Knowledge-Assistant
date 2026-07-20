"""Domain enumerations for ORM models and application logic."""

from __future__ import annotations

from enum import StrEnum


class RoleName(StrEnum):
    """Canonical role identifiers used across authorization checks."""

    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class DocumentStatus(StrEnum):
    """Lifecycle status for managed documents."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    INDEXED = "indexed"
    ARCHIVED = "archived"
    DELETED = "deleted"
    FAILED = "failed"


class LLMProviderName(StrEnum):
    """Selectable LLM backends via LLM_PROVIDER env."""

    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class DocumentClassification(StrEnum):
    """Auto-detected document types for OCR intelligence."""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    BUSINESS_CARD = "business_card"
    CONTRACT = "contract"
    REPORT = "report"
    RESUME = "resume"
    FORM = "form"
    LETTER = "letter"
    SCREENSHOT = "screenshot"
    CHART = "chart"
    UNKNOWN = "unknown"


class OCRJobStatus(StrEnum):
    """Background OCR / vision job lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OCRProviderName(StrEnum):
    PADDLE = "paddle"
    EASYOCR = "easyocr"
    MOCK = "mock"


class MeetingStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    ANALYZING = "analyzing"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class ActionItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class ActionItemPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AgentType(StrEnum):
    KNOWLEDGE = "knowledge"
    DOCUMENT = "document"
    MEETING = "meeting"
    OCR = "ocr"
    VISION = "vision"
    SQL = "sql"
    EMAIL = "email"
    CALENDAR = "calendar"
    ANALYTICS = "analytics"
    GENERAL = "general_assistant"


class AgentSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class EmbeddingProviderName(StrEnum):
    """Selectable embedding backends."""

    BGE = "bge"
    MINILM = "minilm"
    MOCK = "mock"


class DocumentVisibility(StrEnum):
    """Who can access a document beyond the owner."""

    PRIVATE = "private"
    COMPANY = "company"
    PUBLIC = "public"
    ADMIN_ONLY = "admin_only"


class StorageBackendType(StrEnum):
    """Pluggable object-storage backends."""

    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"
