from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class MeetingSearchTool(BaseTool):
    name = "meeting_search"
    description = "Find meetings by title, keyword, or speaker."
    tags = ["meeting", "search"]
    agent_types = ["meeting", "general_assistant"]
    required_permissions = ["meetings:read"]
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "speaker": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from app.services.meeting_service import MeetingService

        svc = MeetingService(ctx.session)
        data = await svc.list_meetings(
            ctx.user,
            q=str(kwargs.get("query") or ""),
            speaker=kwargs.get("speaker"),
            limit=int(kwargs.get("limit") or 20),
        )
        # Prefer yesterday / recent ready meetings for planner memory
        items = data.get("items") or []
        if items:
            ctx.memory["last_meeting_id"] = items[0].get("id")
        return ToolResult(True, data=data)
