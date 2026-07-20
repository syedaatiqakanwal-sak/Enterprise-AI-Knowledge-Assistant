from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class OCRSearchTool(BaseTool):
    name = "ocr_search"
    description = "Search previously extracted OCR text and invoice fields."
    tags = ["ocr", "search"]
    agent_types = ["ocr", "document", "general_assistant"]
    required_permissions = ["ocr:read"]
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from app.services.ocr_service import OCRService

        q = str(kwargs.get("query") or "").strip()
        data = await OCRService(ctx.session).list_docs(
            ctx.user, q=q, limit=int(kwargs.get("limit") or 20)
        )
        return ToolResult(True, data=data)
