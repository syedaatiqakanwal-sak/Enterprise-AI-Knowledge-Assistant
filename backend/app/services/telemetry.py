"""Telemetry collector — emit analytics events from app services / middleware buffer."""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analytics import (
    APIRequestLog,
    AgentExecutionMetric,
    AnalyticsEvent,
    AnalyticsUserSession,
    LLMUsage,
    RAGMetric,
    SystemMetric,
)

logger = logging.getLogger(__name__)

# Middleware-safe ring buffer (no DB session in ASGI middleware)
_API_BUFFER: deque[dict[str, Any]] = deque(maxlen=5000)
_BUFFER_LOCK = threading.Lock()


def buffer_api_request(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    user_id: str | None = None,
    error: str | None = None,
) -> None:
    if not settings.ANALYTICS_ENABLED or not settings.ANALYTICS_LOG_API_REQUESTS:
        return
    if path.startswith("/api/v1/health") or path.startswith("/docs"):
        return
    with _BUFFER_LOCK:
        _API_BUFFER.append(
            {
                "request_id": request_id,
                "method": method,
                "path": path[:512],
                "status_code": status_code,
                "latency_ms": latency_ms,
                "user_id": user_id,
                "error": error,
            }
        )


def drain_api_buffer(limit: int = 200) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with _BUFFER_LOCK:
        while _API_BUFFER and len(items) < limit:
            items.append(_API_BUFFER.popleft())
    return items


def estimate_cost(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    embedding_tokens: int = 0,
) -> float:
    return (
        (prompt_tokens / 1000.0) * settings.ANALYTICS_COST_PER_1K_PROMPT
        + (completion_tokens / 1000.0) * settings.ANALYTICS_COST_PER_1K_COMPLETION
        + (embedding_tokens / 1000.0) * settings.ANALYTICS_COST_PER_1K_EMBEDDING
    )


class TelemetryCollector:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def flush_api_buffer(self) -> int:
        rows = drain_api_buffer()
        for r in rows:
            uid = None
            if r.get("user_id"):
                try:
                    uid = UUID(str(r["user_id"]))
                except Exception:
                    uid = None
            self._session.add(
                APIRequestLog(
                    request_id=r["request_id"],
                    user_id=uid,
                    method=r["method"],
                    path=r["path"],
                    status_code=r["status_code"],
                    latency_ms=r["latency_ms"],
                    error=r.get("error"),
                )
            )
        if rows:
            await self._session.flush()
        return len(rows)

    async def emit_event(
        self,
        *,
        event_type: str,
        category: str,
        user_id: UUID | None = None,
        success: bool = True,
        latency_ms: float = 0.0,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        row = AnalyticsEvent(
            event_type=event_type,
            category=category,
            user_id=user_id,
            success=success,
            latency_ms=latency_ms,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            payload=payload,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def record_llm(
        self,
        *,
        user_id: UUID | None,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        embedding_tokens: int = 0,
        latency_ms: float = 0.0,
        context_size: int = 0,
        streaming: bool = False,
        operation: str = "generate",
        request_id: str | None = None,
        success: bool = True,
        meta: dict[str, Any] | None = None,
    ) -> LLMUsage:
        total = prompt_tokens + completion_tokens + embedding_tokens
        row = LLMUsage(
            user_id=user_id,
            provider=provider,
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            embedding_tokens=embedding_tokens,
            total_tokens=total,
            estimated_cost_usd=estimate_cost(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                embedding_tokens=embedding_tokens,
            ),
            latency_ms=latency_ms,
            context_size=context_size,
            request_id=request_id,
            streaming=streaming,
            success=success,
            meta=meta,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def record_rag(
        self,
        *,
        user_id: UUID | None,
        query: str,
        chunks_retrieved: int,
        avg_similarity: float,
        metrics: dict[str, float],
        grounded: bool,
        citation_count: int,
        top_document_ids: list[str] | None = None,
        request_id: str | None = None,
    ) -> RAGMetric:
        row = RAGMetric(
            user_id=user_id,
            query=query[:2000] if query else None,
            chunks_retrieved=chunks_retrieved,
            avg_similarity=avg_similarity,
            retrieval_ms=float(metrics.get("retrieval_ms") or 0),
            embedding_ms=float(metrics.get("embedding_ms") or 0),
            llm_ms=float(metrics.get("llm_ms") or 0),
            total_ms=float(metrics.get("total_ms") or 0),
            grounded=grounded,
            no_result=chunks_retrieved == 0 or not grounded,
            citation_count=citation_count,
            top_document_ids=top_document_ids,
            hallucination_flag=False,
            request_id=request_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def record_agent(
        self,
        *,
        user_id: UUID | None,
        agent_type: str,
        session_id: str | None,
        task_id: str | None,
        planner_ms: float,
        execution_ms: float,
        tool_calls: int,
        failures: int,
        retries: int,
        success: bool,
        tools_used: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AgentExecutionMetric:
        row = AgentExecutionMetric(
            user_id=user_id,
            agent_type=agent_type,
            session_id=session_id,
            task_id=task_id,
            planner_ms=planner_ms,
            reasoning_ms=0.0,
            execution_ms=execution_ms,
            tool_calls=tool_calls,
            failures=failures,
            retries=retries,
            success=success,
            tools_used=tools_used,
            meta=meta,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def record_login(
        self,
        *,
        user_id: UUID | None,
        session_key: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AnalyticsUserSession:
        row = AnalyticsUserSession(
            user_id=user_id,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
            login_success=success,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(row)
        await self.emit_event(
            event_type="login_success" if success else "login_failed",
            category="auth",
            user_id=user_id,
            success=success,
            payload={"session_key": session_key},
        )
        await self._session.flush()
        return row

    async def record_system_snapshot(self, **kwargs: Any) -> SystemMetric:
        row = SystemMetric(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row
