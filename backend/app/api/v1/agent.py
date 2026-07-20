"""Enterprise AI Agent Platform API — Module 9."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentListOut,
    AgentRunOut,
    AgentRunRequest,
    WorkflowCreateRequest,
)
from app.schemas.response import ApiResponse
from app.services.agent_service import AgentService

router = APIRouter()


@router.post(
    "/chat",
    response_model=ApiResponse[AgentRunOut],
    summary="Chat with the agent (plan + tools)",
)
async def agent_chat(
    body: AgentChatRequest,
    current_user: User = Depends(require_permissions("agents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentRunOut]:
    sid = uuid.UUID(body.session_id) if body.session_id else None
    data = await AgentService(db).chat(
        current_user,
        body.message,
        session_id=sid,
        agent_type=body.agent_type,
        confirm=body.confirm,
    )
    return ApiResponse.ok(AgentRunOut(**data), message="Agent response")


@router.post(
    "/run",
    response_model=ApiResponse[AgentRunOut],
    status_code=status.HTTP_201_CREATED,
    summary="Run an agent goal / workflow",
)
async def agent_run(
    body: AgentRunRequest,
    current_user: User = Depends(require_permissions("agents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentRunOut]:
    sid = uuid.UUID(body.session_id) if body.session_id else None
    wid = uuid.UUID(body.workflow_id) if body.workflow_id else None
    data = await AgentService(db).run(
        current_user,
        body.goal,
        session_id=sid,
        agent_type=body.agent_type,
        confirm=body.confirm,
        workflow_id=wid,
    )
    return ApiResponse.ok(AgentRunOut(**data), message="Agent run complete")


@router.get(
    "/history",
    response_model=ApiResponse[AgentListOut],
    summary="Agent session history",
)
async def agent_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("agents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentListOut]:
    data = await AgentService(db).history(current_user, limit=limit, offset=offset)
    return ApiResponse.ok(AgentListOut(**data), message="Agent history")


@router.get(
    "/tasks",
    response_model=ApiResponse[AgentListOut],
    summary="List agent tasks",
)
async def agent_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("agents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentListOut]:
    data = await AgentService(db).list_tasks(current_user, limit=limit, offset=offset)
    return ApiResponse.ok(AgentListOut(**data), message="Agent tasks")


@router.delete(
    "/tasks/{task_id}",
    response_model=ApiResponse[dict],
    summary="Soft-delete an agent task",
)
async def agent_delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(require_permissions("agents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await AgentService(db).delete_task(current_user, task_id)
    return ApiResponse.ok({"id": str(task_id)}, message="Task deleted")


@router.get(
    "/workflows",
    response_model=ApiResponse[AgentListOut],
    summary="List workflows",
)
async def agent_workflows(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permissions("agents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AgentListOut]:
    data = await AgentService(db).list_workflows(current_user, limit=limit, offset=offset)
    return ApiResponse.ok(AgentListOut(**data), message="Workflows")


@router.post(
    "/workflows",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow (visual builder payload)",
)
async def agent_create_workflow(
    body: WorkflowCreateRequest,
    current_user: User = Depends(require_permissions("agents:write")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    data = await AgentService(db).create_workflow(
        current_user,
        name=body.name,
        description=body.description,
        graph=body.graph,
        steps=body.steps,
        status=body.status,
    )
    return ApiResponse.ok(data, message="Workflow created")


@router.get(
    "/tools",
    response_model=ApiResponse[dict],
    summary="List registered plugin tools",
)
async def agent_tools(
    agent_type: Optional[str] = None,
    current_user: User = Depends(require_permissions("agents:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user, db
    data = await AgentService(db).list_tools(agent_type=agent_type)
    return ApiResponse.ok(data, message="Tool registry")
