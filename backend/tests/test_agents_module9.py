"""Module 9 — Enterprise AI Agent Platform tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.agents.memory import AgentMemory
from app.ai.agents.planner import TaskPlanner
from app.ai.agents.registry import (
    ensure_tools_loaded,
    tool_registry,
)
from app.ai.agents.registry.base_tool import BaseTool, ToolContext, ToolResult
from app.ai.agents.registry.tool_registry import register_tool
from tests.conftest import login


def test_tool_registry_discovers_plugins() -> None:
    tool_registry.clear()
    ensure_tools_loaded(force=True)
    names = tool_registry.list_names()
    assert "rag_search" in names
    assert "meeting_search" in names
    assert "calculator" in names
    assert "email_sender" in names
    assert "current_time" in names
    assert len(names) >= 10


def test_register_custom_plugin_tool() -> None:
    tool_registry.clear()
    ensure_tools_loaded(force=True)

    @register_tool
    class EchoTool(BaseTool):
        name = "echo_plugin"
        description = "Echo"
        input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

        async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
            _ = ctx
            return ToolResult(True, data={"echo": kwargs.get("text")})

    assert tool_registry.has("echo_plugin")
    tool_registry.clear()
    ensure_tools_loaded(force=True)
    assert tool_registry.has("calculator")
    assert not tool_registry.has("echo_plugin")


def test_planner_meeting_email_sequence() -> None:
    tool_registry.clear()
    ensure_tools_loaded(force=True)
    tools = tool_registry.list_tools()
    plan = TaskPlanner().plan(
        "Summarize yesterday's meeting and email it to my manager.",
        agent_type="meeting",
        available_tools=tools,
    )
    tool_names = [s.tool for s in plan.steps]
    assert "meeting_search" in tool_names
    assert "meeting_summarizer" in tool_names
    assert "email_sender" in tool_names
    assert plan.reasoning


@pytest.mark.asyncio
async def test_agent_memory_short_term() -> None:
    import uuid

    mem = AgentMemory(user_id=uuid.uuid4(), session_id=uuid.uuid4())
    await mem.set_short_term({"foo": "bar"})
    got = await mem.get_short_term()
    assert got.get("foo") == "bar"
    await mem.append_conversation("user", "hi")
    hist = await mem.get_short_term()
    assert hist["conversation"][-1]["content"] == "hi"


@pytest.mark.asyncio
async def test_agent_chat_calculator_and_permissions(
    client: AsyncClient,
    admin_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("AGENT_PROVIDER", "mock")
    tool_registry.clear()
    ensure_tools_loaded(force=True)

    from app.ai.embeddings import get_embedding_provider
    from app.ai.llm import get_llm_provider

    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    unauth = await client.post("/api/v1/agent/chat", json={"message": "hi"})
    assert unauth.status_code == 401

    auth = await login(
        client, admin_credentials["email"], admin_credentials["password"]
    )
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={"message": "Calculate 12 * 8", "agent_type": "general_assistant"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["answer"]
    assert data["tool_executions"]
    assert any(e["tool_name"] == "calculator" for e in data["tool_executions"])
    assert data["session_id"]
    session_id = data["session_id"]

    # Meeting + email should pause for confirmation
    meet = await client.post(
        "/api/v1/agent/run",
        headers=headers,
        json={
            "goal": "Summarize yesterday's meeting and email it to manager@example.com",
            "agent_type": "meeting",
            "session_id": session_id,
        },
    )
    assert meet.status_code == 201, meet.text
    mdata = meet.json()["data"]
    assert mdata["waiting_confirmation"] is True or "email_sender" in [
        e["tool_name"] for e in mdata["tool_executions"]
    ]

    tools = await client.get("/api/v1/agent/tools", headers=headers)
    assert tools.status_code == 200
    assert len(tools.json()["data"]["tools"]) >= 8

    hist = await client.get("/api/v1/agent/history", headers=headers)
    assert hist.status_code == 200
    assert hist.json()["data"]["total"] >= 1

    tasks = await client.get("/api/v1/agent/tasks", headers=headers)
    assert tasks.status_code == 200
    assert tasks.json()["data"]["total"] >= 1
    task_id = tasks.json()["data"]["items"][0]["id"]

    wf = await client.post(
        "/api/v1/agent/workflows",
        headers=headers,
        json={
            "name": "Time check",
            "status": "active",
            "steps": [
                {
                    "node_id": "a",
                    "node_type": "tool",
                    "label": "Time",
                    "config": {"tool": "current_time", "args": {}},
                    "next_on_success": "b",
                },
                {
                    "node_id": "b",
                    "node_type": "output",
                    "label": "Done",
                    "config": {"message": "ok"},
                },
            ],
        },
    )
    assert wf.status_code == 201, wf.text
    assert wf.json()["data"]["name"] == "Time check"

    deleted = await client.delete(f"/api/v1/agent/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 200
