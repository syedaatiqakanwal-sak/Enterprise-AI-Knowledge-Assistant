from __future__ import annotations

from typing import Any
from uuid import UUID

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class MeetingSummarizerTool(BaseTool):
    name = "meeting_summarizer"
    description = "Load executive summary, action items, and decisions for a meeting."
    tags = ["meeting", "summarize"]
    agent_types = ["meeting", "general_assistant"]
    required_permissions = ["meetings:read"]
    input_schema = {
        "type": "object",
        "properties": {
            "meeting_id": {"type": "string"},
            "query": {"type": "string", "description": "Optional — used to find a meeting if id missing"},
        },
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from app.services.meeting_service import MeetingService

        svc = MeetingService(ctx.session)
        meeting_id = kwargs.get("meeting_id") or ctx.memory.get("last_meeting_id")
        if not meeting_id and kwargs.get("query"):
            listed = await svc.list_meetings(ctx.user, q=str(kwargs["query"]), limit=1)
            items = listed.get("items") or []
            if items:
                meeting_id = items[0]["id"]
                ctx.memory["last_meeting_id"] = meeting_id
        if not meeting_id:
            return ToolResult(
                True,
                data={
                    "meeting_id": None,
                    "executive_summary": (
                        "No matching meeting was found. "
                        "Upload/process a meeting first, or pass meeting_id."
                    ),
                    "action_items": [],
                    "decisions": [],
                },
            )
        try:
            summary = await svc.get_summary(ctx.user, UUID(str(meeting_id)))
        except Exception as exc:
            # Fall back to detail if summary not ready
            try:
                detail = await svc.get(ctx.user, UUID(str(meeting_id)))
            except Exception:
                return ToolResult(
                    True,
                    data={
                        "meeting_id": str(meeting_id),
                        "executive_summary": f"Meeting {meeting_id} is not ready ({exc}).",
                        "action_items": [],
                        "decisions": [],
                    },
                )
            return ToolResult(
                True,
                data={
                    "meeting_id": str(meeting_id),
                    "title": detail.get("title"),
                    "executive_summary": (
                        (detail.get("summary") or {}).get("executive_summary")
                        if isinstance(detail.get("summary"), dict)
                        else "Transcript available; summary pending."
                    ),
                    "summary": detail.get("summary"),
                    "action_items": detail.get("action_items") or [],
                    "decisions": detail.get("decisions") or [],
                    "note": str(exc),
                },
            )
        ctx.memory["last_meeting_summary"] = summary.get("executive_summary")
        return ToolResult(True, data=summary)
