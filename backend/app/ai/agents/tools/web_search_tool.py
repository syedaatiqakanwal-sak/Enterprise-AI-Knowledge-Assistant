from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool
from app.core.config import settings


@register_tool
class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the public web (disabled by default)."
    tags = ["web", "search"]
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        _ = ctx
        query = str(kwargs.get("query") or "").strip()
        if not settings.AGENT_WEB_SEARCH_ENABLED:
            return ToolResult(
                True,
                data={
                    "enabled": False,
                    "query": query,
                    "results": [],
                    "message": "Web search disabled. Set AGENT_WEB_SEARCH_ENABLED=true.",
                },
            )
        return ToolResult(
            True,
            data={
                "enabled": True,
                "query": query,
                "results": [
                    {
                        "title": f"Result for {query}",
                        "snippet": "Stub web result.",
                        "url": "https://example.com",
                    }
                ],
            },
        )
