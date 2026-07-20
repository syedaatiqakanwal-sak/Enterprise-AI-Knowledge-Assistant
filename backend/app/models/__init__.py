"""
SQLAlchemy ORM models.

Import concrete models here so Alembic's ``env.py`` can discover metadata via:

    from app.models import Base
"""

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.agent import (
    AgentSession,
    AgentTask,
    AgentWorkflow,
    ToolExecution,
    WorkflowStep,
)
from app.models.analytics import (
    APIRequestLog,
    AgentExecutionMetric,
    AnalyticsEvent,
    AnalyticsUserSession,
    LLMUsage,
    RAGMetric,
    SystemMetric,
)
from app.models.associations import RolePermission, UserRole
from app.models.chat import Chat, ChatMessage
from app.models.document import Document, DocumentFavorite, DocumentVersion
from app.models.enums import (
    ActionItemPriority,
    ActionItemStatus,
    AgentSessionStatus,
    AgentTaskStatus,
    AgentType,
    DocumentClassification,
    DocumentStatus,
    DocumentVisibility,
    EmbeddingProviderName,
    LLMProviderName,
    MeetingStatus,
    OCRJobStatus,
    OCRProviderName,
    RoleName,
    StorageBackendType,
    ToolExecutionStatus,
    WorkflowStatus,
)
from app.models.folder import Folder
from app.models.meeting import (
    Meeting,
    MeetingActionItem,
    MeetingChatMessage,
    MeetingDecision,
    MeetingSpeaker,
    MeetingSummary,
    MeetingTranscriptSegment,
)
from app.models.ocr import (
    DetectedObject,
    ImageAnalysis,
    OCRDocument,
    OCRJob,
    OCRResult,
)
from app.models.password_reset import PasswordResetToken
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.tenant import (
    ApiKey,
    AuditLog,
    Invitation,
    Membership,
    Organization,
    StorageQuota,
    Subscription,
    Team,
    Tenant,
    UsageLimit,
    Workspace,
)
from app.models.user import User
from app.models.verification_token import EmailVerificationToken

__all__ = [
    "APIRequestLog",
    "ActionItemPriority",
    "ActionItemStatus",
    "AgentExecutionMetric",
    "AgentSession",
    "AgentSessionStatus",
    "AgentTask",
    "AgentTaskStatus",
    "AgentType",
    "AgentWorkflow",
    "AnalyticsEvent",
    "AnalyticsUserSession",
    "ApiKey",
    "AuditLog",
    "Base",
    "Chat",
    "ChatMessage",
    "DetectedObject",
    "Document",
    "DocumentClassification",
    "DocumentFavorite",
    "DocumentStatus",
    "DocumentVersion",
    "DocumentVisibility",
    "EmailVerificationToken",
    "EmbeddingProviderName",
    "Folder",
    "ImageAnalysis",
    "Invitation",
    "LLMProviderName",
    "LLMUsage",
    "Meeting",
    "MeetingActionItem",
    "MeetingChatMessage",
    "MeetingDecision",
    "MeetingSpeaker",
    "MeetingStatus",
    "MeetingSummary",
    "MeetingTranscriptSegment",
    "Membership",
    "OCRDocument",
    "OCRJob",
    "OCRJobStatus",
    "OCRProviderName",
    "OCRResult",
    "Organization",
    "PasswordResetToken",
    "Permission",
    "RAGMetric",
    "RefreshToken",
    "Role",
    "RoleName",
    "RolePermission",
    "SoftDeleteMixin",
    "StorageBackendType",
    "StorageQuota",
    "Subscription",
    "SystemMetric",
    "Team",
    "Tenant",
    "TimestampMixin",
    "ToolExecution",
    "ToolExecutionStatus",
    "UsageLimit",
    "User",
    "UserRole",
    "WorkflowStatus",
    "WorkflowStep",
    "Workspace",
]
