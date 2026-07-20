"""Agent platform service — chat, run, history, workflows."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.executors import AgentExecutor
from app.ai.agents.memory import AgentMemory
from app.ai.agents.planner import TaskPlanner
from app.ai.agents.registry import ToolContext, ensure_tools_loaded
from app.ai.agents.workflows import WorkflowEngine
from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import (
    AgentSessionStatus,
    AgentTaskStatus,
    ToolExecutionStatus,
    WorkflowStatus,
)
from app.models.user import User
from app.repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AgentRepository(session)
        self._planner = TaskPlanner()
        self._executor = AgentExecutor()
        self._workflows = WorkflowEngine()

    async def chat(
        self,
        user: User,
        message: str,
        *,
        session_id: uuid.UUID | None = None,
        agent_type: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return await self.run(
            user,
            message,
            session_id=session_id,
            agent_type=agent_type,
            confirm=confirm,
        )

    async def run(
        self,
        user: User,
        goal: str,
        *,
        session_id: uuid.UUID | None = None,
        agent_type: str | None = None,
        confirm: bool = False,
        workflow_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if not settings.AGENT_ENABLED:
            raise AppException("Agent platform disabled", code="AGENT_DISABLED", status_code=503)

        registry = ensure_tools_loaded()
        agent_type = agent_type or settings.AGENT_DEFAULT_TYPE

        if session_id:
            ag_session = await self._repo.get_session(session_id, owner_id=user.id)
            if ag_session is None:
                raise AppException("Agent session not found", code="SESSION_NOT_FOUND", status_code=404)
        else:
            ag_session = await self._repo.create_session(
                owner_id=user.id,
                title=goal[:80] or "Agent session",
                agent_type=agent_type,
                status=AgentSessionStatus.ACTIVE.value,
                messages=[],
            )

        memory = AgentMemory(user_id=user.id, session_id=ag_session.id)
        short = await memory.get_short_term()
        await memory.append_conversation("user", goal)

        task = await self._repo.create_task(
            session_id=ag_session.id,
            owner_id=user.id,
            goal=goal,
            status=AgentTaskStatus.PLANNING.value,
        )

        tools = registry.list_tools(agent_type=agent_type)
        ctx = ToolContext(
            user=user,
            session=self._session,
            agent_type=agent_type,
            session_id=ag_session.id,
            task_id=task.id,
            memory=dict(short),
        )

        if workflow_id:
            wf = await self._repo.get_workflow(workflow_id, owner_id=user.id)
            if wf is None:
                raise AppException("Workflow not found", code="WORKFLOW_NOT_FOUND", status_code=404)
            task.status = AgentTaskStatus.RUNNING.value
            await self._session.flush()
            run = await self._workflows.run(wf.graph or {}, ctx)
            task.status = (
                AgentTaskStatus.COMPLETED.value
                if run.success
                else AgentTaskStatus.FAILED.value
            )
            task.result = run.to_dict()
            task.reasoning_steps = [f"Workflow path: {' → '.join(run.path)}"]
            await self._session.flush()
            return {
                "session_id": str(ag_session.id),
                "task_id": str(task.id),
                "agent_type": agent_type,
                "answer": "Workflow finished" if run.success else (run.error or "Failed"),
                "plan": {"workflow_id": str(workflow_id), "path": run.path},
                "reasoning": task.reasoning_steps or [],
                "tool_executions": run.outputs,
                "waiting_confirmation": False,
                "metrics": {},
                "status": task.status,
                "memory": dict(ctx.memory),
            }

        plan = self._planner.plan(
            goal, agent_type=agent_type, available_tools=tools, memory=ctx.memory
        )
        task.plan = plan.to_dict()
        task.reasoning_steps = plan.reasoning
        task.status = AgentTaskStatus.RUNNING.value
        await self._session.flush()

        result = await self._executor.run_plan(plan, ctx, memory, confirm=confirm)

        for ev in result.events:
            await self._repo.add_tool_execution(
                task_id=task.id,
                tool_name=ev.tool_name,
                step_index=ev.step_index,
                status=(
                    ToolExecutionStatus.SUCCESS.value
                    if ev.status == "success"
                    else ToolExecutionStatus.FAILED.value
                    if ev.status == "failed"
                    else ev.status
                ),
                input_payload=ev.input,
                output_payload=ev.output,
                error=ev.error,
                latency_ms=ev.latency_ms,
                retries=ev.retries,
            )

        if result.waiting_confirmation:
            task.status = AgentTaskStatus.WAITING_CONFIRMATION.value
        elif result.success:
            task.status = AgentTaskStatus.COMPLETED.value
        else:
            task.status = AgentTaskStatus.FAILED.value
            task.error = result.final_response

        task.result = result.to_dict()
        task.metrics = result.metrics

        try:
            from app.services.telemetry import TelemetryCollector

            tel = TelemetryCollector(self._session)
            tools_used = [e.tool_name for e in result.events]
            await tel.record_agent(
                user_id=user.id,
                agent_type=agent_type,
                session_id=str(ag_session.id),
                task_id=str(task.id),
                planner_ms=0.0,
                execution_ms=float((result.metrics or {}).get("total_ms") or 0),
                tool_calls=int((result.metrics or {}).get("tool_calls") or len(result.events)),
                failures=int((result.metrics or {}).get("failures") or 0),
                retries=sum(e.retries for e in result.events),
                success=result.success and not result.waiting_confirmation,
                tools_used=tools_used,
            )
            await tel.emit_event(
                event_type="agent_run",
                category="agent",
                user_id=user.id,
                success=result.success,
                latency_ms=float((result.metrics or {}).get("total_ms") or 0),
                resource_type="agent_task",
                resource_id=str(task.id),
                payload={"tools": tools_used},
            )
        except Exception:
            logger.debug("Agent analytics telemetry skipped", exc_info=True)

        messages = list(ag_session.messages or [])
        messages.append({"role": "user", "content": goal})
        messages.append(
            {
                "role": "assistant",
                "content": result.final_response,
                "task_id": str(task.id),
                "waiting_confirmation": result.waiting_confirmation,
            }
        )
        ag_session.messages = messages[-50:]
        ag_session.memory_snapshot = await memory.get_short_term()
        ag_session.metrics = {
            "tasks": len(messages) // 2,
            "last_tool_calls": len(result.events),
        }
        await memory.append_conversation("assistant", result.final_response)
        await memory.save_long_term(
            {"last_goal": goal, "last_answer": result.final_response, "plan": plan.to_dict()}
        )
        await self._session.flush()

        # Reload task with executions
        task = await self._repo.get_task(task.id, owner_id=user.id)
        assert task is not None

        return {
            "session_id": str(ag_session.id),
            "task_id": str(task.id),
            "agent_type": agent_type,
            "answer": result.final_response,
            "plan": plan.to_dict(),
            "reasoning": result.reasoning,
            "tool_executions": [self._serialize_exec(e) for e in task.tool_executions],
            "waiting_confirmation": result.waiting_confirmation,
            "confirmation_action": result.confirmation_action,
            "metrics": result.metrics,
            "status": task.status,
            "memory": ag_session.memory_snapshot or {},
        }

    async def history(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows, total = await self._repo.list_sessions(user.id, limit=limit, offset=offset)
        return {
            "items": [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "agent_type": s.agent_type,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "message_count": len(s.messages or []),
                }
                for s in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def list_tasks(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows, total = await self._repo.list_tasks(user.id, limit=limit, offset=offset)
        return {
            "items": [self._serialize_task(t) for t in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def delete_task(self, user: User, task_id: uuid.UUID) -> None:
        task = await self._repo.get_task(task_id, owner_id=user.id)
        if task is None:
            raise AppException("Task not found", code="TASK_NOT_FOUND", status_code=404)
        await self._repo.soft_delete_task(task)

    async def list_workflows(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows, total = await self._repo.list_workflows(user.id, limit=limit, offset=offset)
        return {
            "items": [self._serialize_workflow(w) for w in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def create_workflow(
        self,
        user: User,
        *,
        name: str,
        description: str | None = None,
        graph: dict[str, Any] | None = None,
        steps: list[dict[str, Any]] | None = None,
        status: str = WorkflowStatus.DRAFT.value,
    ) -> dict[str, Any]:
        wf = await self._repo.create_workflow(
            owner_id=user.id,
            name=name,
            description=description,
            status=status,
            graph=graph or {"entry": None, "nodes": []},
        )
        if steps:
            await self._repo.add_workflow_steps(wf.id, steps)
            # Mirror into graph.nodes for engine
            nodes = []
            for i, s in enumerate(steps):
                nodes.append(
                    {
                        "id": s.get("node_id") or s.get("id") or f"n{i}",
                        "type": s.get("node_type") or s.get("type") or "tool",
                        "label": s.get("label") or "",
                        "config": s.get("config") or {},
                        "next_on_success": s.get("next_on_success"),
                        "next_on_failure": s.get("next_on_failure"),
                    }
                )
            wf.graph = {
                "entry": nodes[0]["id"] if nodes else None,
                "nodes": nodes,
            }
            await self._session.flush()
        wf = await self._repo.get_workflow(wf.id, owner_id=user.id)
        assert wf is not None
        return self._serialize_workflow(wf)

    async def list_tools(self, *, agent_type: str | None = None) -> dict[str, Any]:
        registry = ensure_tools_loaded()
        return {"tools": registry.schemas(agent_type=agent_type)}

    def _serialize_exec(self, e) -> dict[str, Any]:
        return {
            "id": str(e.id),
            "tool_name": e.tool_name,
            "step_index": e.step_index,
            "status": e.status,
            "input": e.input_payload or {},
            "output": e.output_payload or {},
            "error": e.error,
            "latency_ms": e.latency_ms,
            "retries": e.retries,
        }

    def _serialize_task(self, t) -> dict[str, Any]:
        return {
            "id": str(t.id),
            "session_id": str(t.session_id),
            "goal": t.goal,
            "status": t.status,
            "plan": t.plan,
            "result": t.result,
            "reasoning_steps": t.reasoning_steps or [],
            "error": t.error,
            "metrics": t.metrics or {},
            "tool_executions": [self._serialize_exec(e) for e in (t.tool_executions or [])],
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    def _serialize_workflow(self, w) -> dict[str, Any]:
        return {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "status": w.status,
            "graph": w.graph or {},
            "steps": [
                {
                    "id": str(s.id),
                    "node_id": s.node_id,
                    "node_type": s.node_type,
                    "label": s.label,
                    "position": s.position,
                    "config": s.config or {},
                    "next_on_success": s.next_on_success,
                    "next_on_failure": s.next_on_failure,
                }
                for s in (w.steps or [])
            ],
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
