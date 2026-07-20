"""Analytics & AI Observability API — Module 10."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middlewares.dependencies import require_permissions
from app.models.user import User
from app.schemas.response import ApiResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def _range_params(
    range: str = Query("30d", alias="range", pattern="^(today|7d|30d|90d|custom)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    return {"range_key": range, "date_from": date_from, "date_to": date_to}


@router.get("/overview", response_model=ApiResponse[dict])
async def analytics_overview(
    range: str = Query("30d", alias="range"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).overview(
        range_key=range, date_from=date_from, date_to=date_to
    )
    return ApiResponse.ok(data, message="Analytics overview")


@router.get("/users", response_model=ApiResponse[dict])
async def analytics_users(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).users_analytics(range_key=range)
    return ApiResponse.ok(data, message="User analytics")


@router.get("/documents", response_model=ApiResponse[dict])
async def analytics_documents(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).documents_analytics(range_key=range)
    return ApiResponse.ok(data, message="Document analytics")


@router.get("/rag", response_model=ApiResponse[dict])
async def analytics_rag(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).rag_analytics(range_key=range)
    return ApiResponse.ok(data, message="RAG analytics")


@router.get("/agents", response_model=ApiResponse[dict])
async def analytics_agents(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).agents_analytics(range_key=range)
    return ApiResponse.ok(data, message="Agent analytics")


@router.get("/system", response_model=ApiResponse[dict])
async def analytics_system(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).system_analytics(range_key=range)
    return ApiResponse.ok(data, message="System analytics")


@router.get("/llm", response_model=ApiResponse[dict])
async def analytics_llm(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).llm_analytics(range_key=range)
    return ApiResponse.ok(data, message="LLM analytics")


@router.get("/cost", response_model=ApiResponse[dict])
async def analytics_cost(
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:read")),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    _ = current_user
    data = await AnalyticsService(db).cost_analytics(range_key=range)
    return ApiResponse.ok(data, message="Cost analytics")


@router.get("/export")
async def analytics_export(
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    range: str = Query("30d", alias="range"),
    current_user: User = Depends(require_permissions("analytics:export")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _ = current_user
    content, media, filename = await AnalyticsService(db).export(
        format=format, range_key=range
    )
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
