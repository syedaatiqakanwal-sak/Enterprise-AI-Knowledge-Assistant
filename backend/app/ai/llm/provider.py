"""LLM provider abstraction — switch models via LLM_PROVIDER env."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Optional

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
    """Unified chat completion interface."""

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
        """Default stream: yield the full response once."""
        text = await self.generate(
            system=system, context=context, question=question, history=history
        )
        # Chunk for typing animation
        step = 24
        for i in range(0, len(text), step):
            yield text[i : i + step]


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
        # Use first 400 chars of context as grounded answer
        snippet = context.strip()[:400].replace("\n", " ")
        return (
            f"Based on your uploaded documents: {snippet}…\n\n"
            f"(Generated via mock LLM for offline/dev mode.)"
        )


class OpenAIProvider(LLMProvider):
    name = "openai"

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
        model = settings.LLM_MODEL or "gpt-4o-mini"
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
        model_name = settings.LLM_MODEL or "gemini-1.5-flash"
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


class OllamaProvider(LLMProvider):
    name = "ollama"

    async def generate(
        self,
        *,
        system: str,
        context: str,
        question: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        model = settings.LLM_MODEL or settings.OLLAMA_MODEL
        messages = [{"role": "system", "content": system}]
        for h in history or []:
            messages.append(h)
        messages.append(
            {"role": "user", "content": _build_user_prompt(context, question)}
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message", {}) or {}).get("content", "").strip()


class AzureOpenAIProvider(LLMProvider):
    name = "azure_openai"

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
        deployment = settings.AZURE_OPENAI_DEPLOYMENT or settings.LLM_MODEL or "gpt-4o"
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
        model = settings.LLM_MODEL or "claude-3-5-sonnet-20240620"
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
