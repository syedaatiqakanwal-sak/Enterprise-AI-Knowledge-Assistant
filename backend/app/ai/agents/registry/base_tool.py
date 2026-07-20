"""Plugin tool base — every tool implements name, description, input_schema, execute()."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@dataclass
class ToolContext:
    """Runtime context passed into every tool execution."""

    user: User
    session: AsyncSession
    agent_type: str = "general_assistant"
    session_id: UUID | None = None
    task_id: UUID | None = None
    memory: dict[str, Any] = field(default_factory=dict)
    confirmed_actions: set[str] = field(default_factory=set)


@dataclass
class ToolResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    requires_confirmation: bool = False
    confirmation_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_action": self.confirmation_action,
        }


class BaseTool(ABC):
    """Contract for all agent tools (plugin architecture)."""

    name: str = "base"
    description: str = ""
    input_schema: dict[str, Any] = {}
    required_permissions: list[str] = []
    agent_types: list[str] = []
    tags: list[str] = []

    def matches_agent(self, agent_type: str) -> bool:
        if not self.agent_types:
            return True
        return agent_type in self.agent_types or agent_type == "general_assistant"

    def schema_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "required_permissions": list(self.required_permissions),
            "agent_types": list(self.agent_types),
            "tags": list(self.tags),
        }

    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        ...


class ToolInput(BaseModel):
    """Optional typed wrapper for tool kwargs validation."""

    extra: dict[str, Any] = Field(default_factory=dict)
