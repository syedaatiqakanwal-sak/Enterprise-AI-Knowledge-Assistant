"""System / infrastructure probes — Ollama status, model discovery, LLM info."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.llm.provider import (
    OllamaProvider,
    _model_in_installed,
    _model_names_equivalent,
    clear_llm_provider_cache,
    get_active_llm_info,
    get_llm_provider,
)
from app.core.config import settings
from app.middlewares.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.response import ApiResponse

router = APIRouter()


class OllamaTestRequest(BaseModel):
    """Optional model override for Admin connection test."""

    model: Optional[str] = Field(
        default=None,
        description="Model name to probe (defaults to configured OLLAMA_MODEL / LLM_MODEL)",
    )


class OllamaSelectModelRequest(BaseModel):
    model: str = Field(..., min_length=1, description="Installed Ollama model name")


@router.get(
    "/llm",
    response_model=ApiResponse[dict[str, Any]],
    summary="Active LLM / embedding provider snapshot",
)
async def llm_runtime_info(
    _user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """Lightweight config snapshot for Chat badges (no remote calls)."""
    return ApiResponse.ok(get_active_llm_info(), message="LLM runtime info")


@router.get(
    "/ollama/status",
    response_model=ApiResponse[dict[str, Any]],
    summary="Ollama health: reachability, latency, version, models, GPU",
)
async def ollama_status(
    _user: User = Depends(require_admin),
) -> ApiResponse[dict[str, Any]]:
    provider = OllamaProvider()
    data = await provider.health()
    data["llm_provider_setting"] = settings.LLM_PROVIDER
    data["embedding_provider"] = settings.EMBEDDING_PROVIDER
    message = "Ollama reachable" if data.get("reachable") else "Ollama unreachable"
    return ApiResponse.ok(data, message=message)


@router.get(
    "/ollama/models",
    response_model=ApiResponse[dict[str, Any]],
    summary="Discover models installed in the local Ollama server",
)
async def ollama_models(
    _user: User = Depends(require_admin),
) -> ApiResponse[dict[str, Any]]:
    provider = OllamaProvider()
    try:
        models = await provider.list_models()
        return ApiResponse.ok(
            {
                "models": models,
                "selected_model": provider.selected_model,
                "base_url": provider.base_url,
            },
            message="Ollama models",
        )
    except RuntimeError as exc:
        return ApiResponse.fail(str(exc), errors={"code": "OLLAMA_UNAVAILABLE"})


@router.post(
    "/ollama/test",
    response_model=ApiResponse[dict[str, Any]],
    summary="Test Ollama connection (optional model selection)",
)
async def ollama_test(
    body: OllamaTestRequest | None = None,
    _user: User = Depends(require_admin),
) -> ApiResponse[dict[str, Any]]:
    model = (body.model if body else None) or None
    provider = OllamaProvider(model=model)
    data = await provider.health()
    # Extra chat round-trip only when reachable and model is known
    if data.get("reachable") and provider.selected_model:
        try:
            reply = await provider.generate(
                system="You are a connectivity probe. Reply with exactly: ok",
                context="Connectivity test context: the secret word is ok.",
                question="What is the secret word? Reply with one word.",
                history=None,
            )
            data["test_generate"] = True
            data["test_reply_preview"] = (reply or "")[:120]
        except RuntimeError as exc:
            data["test_generate"] = False
            data["error"] = str(exc)
            return ApiResponse.ok(data, message="Ollama reachable but generate failed")
    ok = bool(data.get("reachable") and not data.get("error"))
    return ApiResponse.ok(
        data,
        message="Ollama connection OK" if ok else "Ollama connection issue",
    )


@router.post(
    "/ollama/model",
    response_model=ApiResponse[dict[str, Any]],
    summary="Select active Ollama model for this process (runtime)",
)
async def ollama_select_model(
    body: OllamaSelectModelRequest,
    _user: User = Depends(require_admin),
) -> ApiResponse[dict[str, Any]]:
    """
    Updates process env ``OLLAMA_MODEL`` / ``LLM_MODEL`` and clears the LLM
    provider cache. Does not rewrite the ``.env`` file.
    """
    import os

    model = body.model.strip()
    provider = OllamaProvider()
    try:
        installed = await provider.list_models()
    except RuntimeError as exc:
        return ApiResponse.fail(str(exc), errors={"code": "OLLAMA_UNAVAILABLE"})

    if installed and not _model_in_installed(model, installed):
        return ApiResponse.fail(
            f"Model '{model}' is not installed. Available: {', '.join(installed)}",
            errors={"code": "MODEL_NOT_INSTALLED", "models": installed},
        )

    # Prefer the exact installed tag when config used a short name
    resolved = next(
        (m for m in installed if _model_names_equivalent(model, m)),
        model,
    )
    os.environ["OLLAMA_MODEL"] = resolved
    os.environ["LLM_MODEL"] = resolved
    object.__setattr__(settings, "OLLAMA_MODEL", resolved)
    object.__setattr__(settings, "LLM_MODEL", resolved)
    clear_llm_provider_cache()

    active = get_llm_provider()
    return ApiResponse.ok(
        {
            "selected_model": active.selected_model,
            "provider": active.name,
            "installed_models": installed,
        },
        message=f"Active Ollama model set to {resolved}",
    )
