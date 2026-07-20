from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool


@register_tool
class WeatherTool(BaseTool):
    name = "weather"
    description = "Get a weather summary for a city (mock for CI)."
    tags = ["weather", "utility"]
    input_schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        _ = ctx
        city = str(kwargs.get("city") or "Unknown").strip()
        return ToolResult(
            True,
            data={
                "city": city,
                "provider": "mock",
                "temperature_c": 22.0,
                "conditions": "Partly cloudy",
            },
        )
