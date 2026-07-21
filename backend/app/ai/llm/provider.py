"""LLM provider abstraction — switch models via LLM_PROVIDER env."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Enterprise AI Knowledge Assistant for a company.
You answer ONLY using the retrieved document context provided below.
Rules:
1. Never invent facts that are not in the context.
2. If the context does not contain the answer, reply exactly:
I couldn't find information about that in your uploaded documents.
3. Cite sources inline using the format [filename, page X] when possible.
4. Be concise, professional, and accurate.
"""


class LLMProvider(ABC):
    """
    Unified chat completion interface.

    Public surface for providers:
    - generate()
    - stream()
    - health()
    - list_models()
    """

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        ...

    async def stream(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        """Default stream: yield the full response in small chunks."""
        text = await self.generate(
            system=system, context=context, question=question, history=history
        )
        step = 24
        for i in range(0, len(text), step):
            yield text[i : i + step]

    async def health(self) -> dict[str, Any]:
        """Provider health probe. Override for remote backends."""
        return {
            "provider": self.name,
            "reachable": True,
            "selected_model": self.selected_model,
            "installed_models": [],
            "version": None,
            "gpu_available": None,
            "latency_ms": 0.0,
            "error": None,
        }

    async def list_models(self) -> list[str]:
        """Discover available models. Override for remote backends."""
        return []

    @property
    def selected_model(self) -> str | None:
        return settings.LLM_MODEL


def _build_user_prompt(context: str, question: str) -> str:
    return (
        f"Retrieved context from company documents:\n"
        f"-----\n{context}\n-----\n\n"
        f"User question: {question}\n\n"
        f"Answer only from the context. Include citations."
    )


class MockLLMProvider(LLMProvider):
    """Deterministic offline LLM for tests / missing API keys."""

    name = "mock"

    @property
    def selected_model(self) -> str | None:
        return "mock"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        _ = (system, history)
        if not context.strip() or context.strip() == "(no relevant passages)":
            return (
                "I couldn't find information about that in your uploaded documents."
            )
        snippet = context.strip()[:400].replace("\n", " ")
        return (
            f"Based on your uploaded documents: {snippet}…\n\n"
            f"(Generated via mock LLM for offline/dev mode.)"
        )

    async def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "reachable": True,
            "selected_model": self.selected_model,
            "installed_models": ["mock"],
            "version": "mock",
            "gpu_available": False,
            "latency_ms": 0.0,
            "error": None,
        }

    async def list_models(self) -> list[str]:
        return ["mock"]


class OpenAIProvider(LLMProvider):
    name = "openai"

    @property
    def selected_model(self) -> str | None:
        return settings.LLM_MODEL or "gpt-4o-mini"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        model = self.selected_model
        messages = [{"role": "system", "content": system}]
        for h in history or []:
            messages.append(h)
        messages.append(
            {"role": "user", "content": _build_user_prompt(context, question)}
        )
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()


class GeminiProvider(LLMProvider):
    name = "gemini"

    @property
    def selected_model(self) -> str | None:
        return settings.LLM_MODEL or "gemini-1.5-flash"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        import google.generativeai as genai

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model_name = self.selected_model
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system,
        )
        prompt = _build_user_prompt(context, question)
        if history:
            hist_txt = "\n".join(
                f"{m['role']}: {m['content']}" for m in history[-6:]
            )
            prompt = f"Prior conversation:\n{hist_txt}\n\n{prompt}"
        resp = await model.generate_content_async(prompt)
        return (resp.text or "").strip()


def _normalize_ollama_model_name(name: str | None) -> str:
    """Strip registry tags so ``llama3.2`` matches ``llama3.2:latest``."""
    if not name:
        return ""
    n = name.strip()
    if ":" in n:
        n = n.split(":", 1)[0]
    return n


def _model_names_equivalent(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    if a.strip() == b.strip():
        return True
    return _normalize_ollama_model_name(a) == _normalize_ollama_model_name(b)


def _model_in_installed(selected: str | None, installed: list[str]) -> bool:
    if not selected:
        return False
    return any(_model_names_equivalent(selected, m) for m in installed)


class OllamaProvider(LLMProvider):
    """
    Local Ollama backend via the official REST API.

    Model is always read from configuration (``OLLAMA_MODEL`` / ``LLM_MODEL``),
    never hardcoded. Supports true token streaming, health probes, and model
    discovery.
    """

    name = "ollama"

    def __init__(self, *, model: str | None = None) -> None:
        # Optional override for Admin "Test Connection" with a selected model
        self._model_override = model

    @property
    def base_url(self) -> str:
        return settings.OLLAMA_BASE_URL.rstrip("/")

    @property
    def selected_model(self) -> str | None:
        if self._model_override:
            return self._model_override
        return (settings.LLM_MODEL or settings.OLLAMA_MODEL or "").strip() or None

    @property
    def _timeout(self) -> httpx.Timeout:
        connect = float(getattr(settings, "OLLAMA_CONNECT_TIMEOUT", 5.0))
        read = float(getattr(settings, "OLLAMA_TIMEOUT", 120.0))
        return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)

    def _messages(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": system}]
        for h in history or []:
            role = h.get("role")
            content = h.get("content")
            if role in {"user", "assistant", "system"} and content:
                messages.append({"role": role, "content": content})
        messages.append(
            {"role": "user", "content": _build_user_prompt(context, question)}
        )
        return messages

    def _require_model(self) -> str:
        model = self.selected_model
        if not model:
            raise RuntimeError(
                "No Ollama model configured. Set OLLAMA_MODEL or LLM_MODEL."
            )
        return model

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        model = self._require_model()
        messages = self._messages(
            system=system, context=context, question=question, history=history
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return (data.get("message", {}) or {}).get("content", "").strip()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama timed out talking to {self.base_url} (model={model})"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = (exc.response.text or "")[:300]
            raise RuntimeError(
                f"Ollama HTTP {exc.response.status_code} for model={model}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama is unreachable at {self.base_url}. "
                f"Is the Ollama server running? ({exc})"
            ) from exc

    async def stream(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[str]:
        """True token streaming via Ollama ``/api/chat`` with ``stream: true``."""
        model = self._require_model()
        messages = self._messages(
            system=system, context=context, question=question, history=history
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                    },
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        raise RuntimeError(
                            f"Ollama HTTP {resp.status_code} for model={model}: "
                            f"{body[:300]}"
                        )
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = (data.get("message") or {}).get("content") or ""
                        if token:
                            yield token
                        if data.get("done"):
                            break
        except RuntimeError:
            raise
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama stream timed out at {self.base_url} (model={model})"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama is unreachable at {self.base_url}. "
                f"Is the Ollama server running? ({exc})"
            ) from exc

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                models = resp.json().get("models") or []
                names = [
                    str(m.get("name") or m.get("model") or "").strip()
                    for m in models
                ]
                return sorted({n for n in names if n})
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Failed to list Ollama models at {self.base_url}: {exc}"
            ) from exc

    async def health(self) -> dict[str, Any]:
        """
        Probe Ollama: reachability, latency, version, installed models,
        GPU availability (best-effort via ``/api/ps`` VRAM), selected model.
        """
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "provider": self.name,
            "reachable": False,
            "selected_model": self.selected_model,
            "installed_models": [],
            "version": None,
            "gpu_available": None,
            "latency_ms": None,
            "base_url": self.base_url,
            "error": None,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                version_resp = await client.get(f"{self.base_url}/api/version")
                version_resp.raise_for_status()
                payload["version"] = (version_resp.json() or {}).get("version")

                tags_resp = await client.get(f"{self.base_url}/api/tags")
                tags_resp.raise_for_status()
                models = tags_resp.json().get("models") or []
                payload["installed_models"] = sorted(
                    {
                        str(m.get("name") or m.get("model") or "").strip()
                        for m in models
                        if (m.get("name") or m.get("model"))
                    }
                )

                gpu_available: bool | None = None
                try:
                    ps_resp = await client.get(f"{self.base_url}/api/ps")
                    if ps_resp.status_code == 200:
                        running = ps_resp.json().get("models") or []
                        if running:
                            gpu_available = any(
                                float(m.get("size_vram") or 0) > 0 for m in running
                            )
                        else:
                            gpu_available = None
                except httpx.HTTPError:
                    gpu_available = None
                payload["gpu_available"] = gpu_available

            payload["reachable"] = True
            payload["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            selected = self.selected_model
            if selected and not _model_in_installed(
                selected, payload["installed_models"]
            ):
                payload["error"] = (
                    f"Selected model '{selected}' is not installed. "
                    f"Run: ollama pull {selected}"
                )
        except httpx.HTTPError as exc:
            payload["reachable"] = False
            payload["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            payload["error"] = f"Ollama unreachable at {self.base_url}: {exc}"
        except Exception as exc:  # noqa: BLE001 — health must never crash the app
            payload["reachable"] = False
            payload["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            payload["error"] = str(exc)
        return payload


class AzureOpenAIProvider(LLMProvider):
    name = "azure_openai"

    @property
    def selected_model(self) -> str | None:
        return settings.AZURE_OPENAI_DEPLOYMENT or settings.LLM_MODEL or "gpt-4o"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        from openai import AsyncAzureOpenAI

        if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
            raise RuntimeError("Azure OpenAI is not configured")
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        deployment = self.selected_model
        messages = [{"role": "system", "content": system}]
        for h in history or []:
            messages.append(h)
        messages.append(
            {"role": "user", "content": _build_user_prompt(context, question)}
        )
        resp = await client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    @property
    def selected_model(self) -> str | None:
        return settings.LLM_MODEL or "claude-3-5-sonnet-20240620"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        from anthropic import AsyncAnthropic

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        model = self.selected_model
        messages: list[dict[str, str]] = []
        for h in history or []:
            if h["role"] in {"user", "assistant"}:
                messages.append(h)
        messages.append(
            {"role": "user", "content": _build_user_prompt(context, question)}
        )
        resp = await client.messages.create(
            model=model,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=system,
            messages=messages,
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Factory — select provider from ``LLM_PROVIDER`` setting."""
    name = (settings.LLM_PROVIDER or "gemini").lower().strip()
    if name in {"mock"} or settings.is_testing:
        return MockLLMProvider()

    try:
        if name == "openai":
            if not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY missing — using mock LLM")
                return MockLLMProvider()
            return OpenAIProvider()
        if name == "gemini":
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY missing — using mock LLM")
                return MockLLMProvider()
            return GeminiProvider()
        if name == "ollama":
            # Do not silently fall back to mock — surface errors at call time
            return OllamaProvider()
        if name in {"azure_openai", "azure"}:
            return AzureOpenAIProvider()
        if name == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                logger.warning("ANTHROPIC_API_KEY missing — using mock LLM")
                return MockLLMProvider()
            return AnthropicProvider()
    except Exception:
        logger.exception("Failed to init LLM provider %s — using mock", name)
        return MockLLMProvider()

    logger.warning("Unknown LLM_PROVIDER=%s — using mock", name)
    return MockLLMProvider()


def get_active_llm_info() -> dict[str, Any]:
    """Runtime provider/model snapshot for UI badges (no remote calls)."""
    provider = get_llm_provider()
    return {
        "provider": provider.name,
        "model": provider.selected_model,
        "llm_provider_setting": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": (
            getattr(settings, "EMBEDDING_MODEL", None)
            or (
                settings.EMBEDDING_MODEL_FALLBACK
                if (settings.EMBEDDING_PROVIDER or "").lower() == "minilm"
                else settings.EMBEDDING_MODEL_PRIMARY
            )
        ),
    }


def clear_llm_provider_cache() -> None:
    """Allow runtime config changes to take effect."""
    get_llm_provider.cache_clear()
