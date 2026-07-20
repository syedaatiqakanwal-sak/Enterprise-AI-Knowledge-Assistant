"""Analytics persistence helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import (
    APIRequestLog,
    AgentExecutionMetric,
    AnalyticsEvent,
    LLMUsage,
    RAGMetric,
    SystemMetric,
)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sum_llm_tokens(self, *, since: datetime | None = None) -> dict:
        stmt = select(
            func.coalesce(func.sum(LLMUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LLMUsage.completion_tokens), 0),
            func.coalesce(func.sum(LLMUsage.embedding_tokens), 0),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            func.coalesce(func.sum(LLMUsage.estimated_cost_usd), 0.0),
            func.count(),
            func.coalesce(func.avg(LLMUsage.latency_ms), 0.0),
        )
        if since:
            stmt = stmt.where(LLMUsage.created_at >= since)
        row = (await self._session.execute(stmt)).one()
        return {
            "prompt_tokens": int(row[0]),
            "completion_tokens": int(row[1]),
            "embedding_tokens": int(row[2]),
            "total_tokens": int(row[3]),
            "estimated_cost_usd": float(row[4]),
            "llm_calls": int(row[5]),
            "avg_latency_ms": float(row[6]),
        }

    async def list_llm(
        self, *, since: datetime | None = None, limit: int = 100
    ) -> Sequence[LLMUsage]:
        stmt = select(LLMUsage).order_by(LLMUsage.created_at.desc()).limit(limit)
        if since:
            stmt = stmt.where(LLMUsage.created_at >= since)
        return (await self._session.execute(stmt)).scalars().all()

    async def rag_stats(self, *, since: datetime | None = None) -> dict:
        stmt = select(
            func.count(),
            func.coalesce(func.avg(RAGMetric.retrieval_ms), 0.0),
            func.coalesce(func.avg(RAGMetric.chunks_retrieved), 0.0),
            func.coalesce(func.avg(RAGMetric.avg_similarity), 0.0),
            func.coalesce(func.sum(cast(RAGMetric.no_result, Integer)), 0),
            func.coalesce(func.sum(RAGMetric.citation_count), 0),
            func.coalesce(func.sum(cast(RAGMetric.grounded, Integer)), 0),
        )
        if since:
            stmt = stmt.where(RAGMetric.created_at >= since)
        row = (await self._session.execute(stmt)).one()
        total = int(row[0])
        grounded = int(row[6])
        return {
            "searches": total,
            "avg_retrieval_ms": float(row[1]),
            "avg_chunks": float(row[2]),
            "avg_similarity": float(row[3]),
            "no_result_queries": int(row[4]),
            "citation_frequency": int(row[5]),
            "success_rate": (grounded / total) if total else 1.0,
        }

    async def agent_stats(self, *, since: datetime | None = None) -> dict:
        stmt = select(
            func.count(),
            func.coalesce(func.sum(cast(AgentExecutionMetric.success, Integer)), 0),
            func.coalesce(func.avg(AgentExecutionMetric.execution_ms), 0.0),
            func.coalesce(func.avg(AgentExecutionMetric.planner_ms), 0.0),
            func.coalesce(func.sum(AgentExecutionMetric.tool_calls), 0),
            func.coalesce(func.sum(AgentExecutionMetric.failures), 0),
            func.coalesce(func.sum(AgentExecutionMetric.retries), 0),
        )
        if since:
            stmt = stmt.where(AgentExecutionMetric.created_at >= since)
        row = (await self._session.execute(stmt)).one()
        total = int(row[0])
        ok = int(row[1])
        return {
            "runs": total,
            "success_rate": (ok / total) if total else 1.0,
            "avg_execution_ms": float(row[2]),
            "avg_planner_ms": float(row[3]),
            "tool_calls": int(row[4]),
            "failures": int(row[5]),
            "retries": int(row[6]),
        }

    async def api_stats(self, *, since: datetime | None = None) -> dict:
        from sqlalchemy import case

        stmt = select(
            func.count(),
            func.coalesce(func.avg(APIRequestLog.latency_ms), 0.0),
            func.coalesce(
                func.sum(case((APIRequestLog.status_code >= 500, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((APIRequestLog.status_code >= 400, 1), else_=0)),
                0,
            ),
        )
        if since:
            stmt = stmt.where(APIRequestLog.created_at >= since)
        row = (await self._session.execute(stmt)).one()
        total = int(row[0])
        errors = int(row[3])
        return {
            "api_calls": total,
            "avg_latency_ms": float(row[1]),
            "server_errors": int(row[2]),
            "client_errors": errors,
            "error_rate": (errors / total) if total else 0.0,
        }

    async def event_timeline(
        self, *, since: datetime | None = None, limit: int = 30
    ) -> list[dict]:
        day = func.date_trunc("day", AnalyticsEvent.created_at).label("day")
        stmt = (
            select(day, func.count())
            .group_by(day)
            .order_by(day.asc())
            .limit(limit)
        )
        if since:
            stmt = stmt.where(AnalyticsEvent.created_at >= since)
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "date": r[0].date().isoformat() if r[0] else None,
                "count": int(r[1]),
            }
            for r in rows
        ]

    async def top_tools(self, *, since: datetime | None = None, limit: int = 10) -> list[dict]:
        # Flatten tools_used arrays is hard in SQL — approximate via agent metrics meta
        stmt = (
            select(AgentExecutionMetric.tools_used, AgentExecutionMetric.tool_calls)
            .order_by(AgentExecutionMetric.created_at.desc())
            .limit(200)
        )
        if since:
            stmt = stmt.where(AgentExecutionMetric.created_at >= since)
        rows = (await self._session.execute(stmt)).all()
        counts: dict[str, int] = {}
        for tools, _calls in rows:
            for t in tools or []:
                counts[str(t)] = counts.get(str(t), 0) + 1
        ordered = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"tool": k, "count": v} for k, v in ordered]

    async def latest_system(self) -> SystemMetric | None:
        stmt = select(SystemMetric).order_by(SystemMetric.created_at.desc()).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def system_history(
        self, *, since: datetime | None = None, limit: int = 48
    ) -> Sequence[SystemMetric]:
        stmt = select(SystemMetric).order_by(SystemMetric.created_at.desc()).limit(limit)
        if since:
            stmt = stmt.where(SystemMetric.created_at >= since)
        return (await self._session.execute(stmt)).scalars().all()
