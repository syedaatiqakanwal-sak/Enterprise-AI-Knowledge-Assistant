"""Agent platform repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import (
    AgentSession,
    AgentTask,
    AgentWorkflow,
    ToolExecution,
    WorkflowStep,
)


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, **kwargs) -> AgentSession:
        row = AgentSession(**kwargs)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_session(
        self, session_id: uuid.UUID, *, owner_id: uuid.UUID | None = None
    ) -> Optional[AgentSession]:
        stmt = (
            select(AgentSession)
            .where(AgentSession.id == session_id, AgentSession.deleted_at.is_(None))
            .options(
                selectinload(AgentSession.tasks).selectinload(AgentTask.tool_executions)
            )
        )
        if owner_id:
            stmt = stmt.where(AgentSession.owner_id == owner_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_sessions(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[AgentSession], int]:
        where = and_(AgentSession.owner_id == owner_id, AgentSession.deleted_at.is_(None))
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(AgentSession).where(where)
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(AgentSession)
                .where(where)
                .order_by(AgentSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return rows, total

    async def create_task(self, **kwargs) -> AgentTask:
        row = AgentTask(**kwargs)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_task(
        self, task_id: uuid.UUID, *, owner_id: uuid.UUID | None = None
    ) -> Optional[AgentTask]:
        stmt = (
            select(AgentTask)
            .where(AgentTask.id == task_id, AgentTask.deleted_at.is_(None))
            .options(selectinload(AgentTask.tool_executions))
        )
        if owner_id:
            stmt = stmt.where(AgentTask.owner_id == owner_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_tasks(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[AgentTask], int]:
        where = and_(AgentTask.owner_id == owner_id, AgentTask.deleted_at.is_(None))
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(AgentTask).where(where)
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(AgentTask)
                .where(where)
                .options(selectinload(AgentTask.tool_executions))
                .order_by(AgentTask.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return rows, total

    async def soft_delete_task(self, task: AgentTask) -> None:
        task.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def add_tool_execution(self, **kwargs) -> ToolExecution:
        row = ToolExecution(**kwargs)
        self._session.add(row)
        await self._session.flush()
        return row

    async def create_workflow(self, **kwargs) -> AgentWorkflow:
        row = AgentWorkflow(**kwargs)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get_workflow(
        self, workflow_id: uuid.UUID, *, owner_id: uuid.UUID | None = None
    ) -> Optional[AgentWorkflow]:
        stmt = (
            select(AgentWorkflow)
            .where(AgentWorkflow.id == workflow_id, AgentWorkflow.deleted_at.is_(None))
            .options(selectinload(AgentWorkflow.steps))
        )
        if owner_id:
            stmt = stmt.where(AgentWorkflow.owner_id == owner_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_workflows(
        self, owner_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[AgentWorkflow], int]:
        where = and_(
            AgentWorkflow.owner_id == owner_id, AgentWorkflow.deleted_at.is_(None)
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(AgentWorkflow).where(where)
                )
            ).scalar_one()
        )
        rows = (
            await self._session.execute(
                select(AgentWorkflow)
                .where(where)
                .options(selectinload(AgentWorkflow.steps))
                .order_by(AgentWorkflow.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return rows, total

    async def add_workflow_steps(
        self, workflow_id: uuid.UUID, steps: list[dict]
    ) -> None:
        for i, s in enumerate(steps):
            self._session.add(
                WorkflowStep(
                    workflow_id=workflow_id,
                    node_id=s.get("node_id") or s.get("id") or f"n{i}",
                    node_type=s.get("node_type") or s.get("type") or "tool",
                    label=s.get("label") or "",
                    position=int(s.get("position", i)),
                    config=s.get("config"),
                    next_on_success=s.get("next_on_success"),
                    next_on_failure=s.get("next_on_failure"),
                )
            )
        await self._session.flush()
