"""Analytics & observability ORM models (Module 10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AnalyticsEvent(Base, TimestampMixin):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class LLMUsage(Base, TimestampMixin):
    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    operation: Mapped[str] = mapped_column(String(64), nullable=False, default="generate")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    context_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class AgentExecutionMetric(Base, TimestampMixin):
    __tablename__ = "agent_execution_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, default="general_assistant")
    planner_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasoning_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    execution_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tools_used: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class RAGMetric(Base, TimestampMixin):
    __tablename__ = "rag_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retrieval_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    embedding_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    no_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_document_ids: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    hallucination_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SystemMetric(Base, TimestampMixin):
    __tablename__ = "system_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_used_mb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    queue_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    db_connections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redis_used_mb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    qdrant_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_response_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class AnalyticsUserSession(Base, TimestampMixin):
    __tablename__ = "analytics_user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    login_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class APIRequestLog(Base, TimestampMixin):
    __tablename__ = "api_request_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
