from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class CurrentTimeTool(BaseTool):
    name = "current_time"
    description = "Return the current UTC and local ISO timestamps."
    tags = ["time", "utility"]
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        _ = ctx, kwargs
        now = datetime.now(timezone.utc)
        return ToolResult(
            True,
            data={
                "utc": now.isoformat(),
                "unix": int(now.timestamp()),
                "day_of_week": now.strftime("%A"),
            },
        )
