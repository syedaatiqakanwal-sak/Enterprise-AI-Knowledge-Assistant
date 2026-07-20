"""Agent API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = None
    agent_type: Optional[str] = None
    confirm: bool = False


class AgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = None
    agent_type: Optional[str] = None
    confirm: bool = False
    workflow_id: Optional[str] = None


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = "draft"
    graph: Optional[dict[str, Any]] = None
    steps: Optional[list[dict[str, Any]]] = None


class AgentRunOut(BaseModel):
    session_id: str
    task_id: str
    agent_type: str
    answer: str
    plan: dict[str, Any] = Field(default_factory=dict)
    reasoning: list[Any] = Field(default_factory=list)
    tool_executions: list[dict[str, Any]] = Field(default_factory=list)
    waiting_confirmation: bool = False
    confirmation_action: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    memory: dict[str, Any] = Field(default_factory=dict)


class AgentListOut(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
