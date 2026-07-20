from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class VisionAnalysisTool(BaseTool):
    name = "vision_analysis"
    description = "List recent vision analyses or describe a prior analysis by id."
    tags = ["vision", "image"]
    agent_types = ["vision", "general_assistant"]
    required_permissions = ["vision:read"]
    input_schema = {
        "type": "object",
        "properties": {
            "analysis_id": {"type": "string"},
            "limit": {"type": "integer"},
        },
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        from uuid import UUID

        from app.repositories.ocr_repository import VisionRepository

        repo = VisionRepository(ctx.session)
        analysis_id = kwargs.get("analysis_id")
        if analysis_id:
            row = await repo.get(UUID(str(analysis_id)), owner_id=ctx.user.id)
            if row is None:
                return ToolResult(False, error="Vision analysis not found")
            return ToolResult(
                True,
                data={
                    "id": str(row.id),
                    "filename": row.filename,
                    "caption": row.caption,
                    "scene_description": row.scene_description,
                    "objects": [
                        {"label": o.label, "confidence": o.confidence}
                        for o in (row.objects or [])
                    ],
                },
            )
        rows, total = await repo.list_history(
            ctx.user.id, limit=int(kwargs.get("limit") or 20)
        )
        return ToolResult(
            True,
            data={
                "total": total,
                "items": [
                    {
                        "id": str(r.id),
                        "filename": r.filename,
                        "caption": r.caption,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            },
        )
