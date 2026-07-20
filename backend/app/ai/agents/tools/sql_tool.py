from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool
from app.core.config import settings


@register_tool
class SQLQueryTool(BaseTool):
    name = "sql_query"
    description = "Run a read-only analytic query (mock-safe)."
    tags = ["sql", "analytics"]
    agent_types = ["sql", "analytics", "general_assistant"]
    required_permissions = ["agents:write"]
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        lowered = query.lower()
        if any(tok in lowered for tok in ("drop ", "delete ", "update ", "insert ", "alter ")):
            return ToolResult(False, error="Only read-only SELECT queries are allowed")
        if settings.AGENT_SQL_READONLY and not lowered.startswith("select"):
            return ToolResult(
                True,
                data={
                    "mode": "mock",
                    "query": query,
                    "rows": [{"metric": "document_count", "value": 42}],
                },
            )
        try:
            from sqlalchemy import text

            if "document" in lowered:
                result = await ctx.session.execute(
                    text("SELECT COUNT(*) AS value FROM documents WHERE deleted_at IS NULL")
                )
                return ToolResult(
                    True,
                    data={
                        "mode": "live",
                        "rows": [{"metric": "documents", "value": result.scalar_one()}],
                    },
                )
            return ToolResult(
                True, data={"mode": "mock", "rows": [{"metric": "ok", "value": 1}]}
            )
        except Exception as exc:
            return ToolResult(False, error=str(exc))
