"""Workflow graph runner — sequential, conditional, retries, error recovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.ai.agents.registry import ToolContext, ensure_tools_loaded
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WorkflowNode:
    node_id: str
    node_type: str  # llm | tool | condition | loop | output
    label: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    next_on_success: str | None = None
    next_on_failure: str | None = None


@dataclass
class WorkflowRunResult:
    success: bool
    outputs: list[dict[str, Any]] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "outputs": self.outputs,
            "path": self.path,
            "error": self.error,
        }


class WorkflowEngine:
    """
    Executes a workflow graph (future-ready for visual builder).

    Graph format::
        {
          "entry": "n1",
          "nodes": [
            {"id": "n1", "type": "tool", "label": "...", "config": {"tool": "rag_search", "args": {...}},
             "next_on_success": "n2", "next_on_failure": "end"}
          ]
        }
    """

    async def run(
        self,
        graph: dict[str, Any],
        ctx: ToolContext,
        *,
        max_steps: int | None = None,
    ) -> WorkflowRunResult:
        registry = ensure_tools_loaded()
        nodes = {
            n["id"]: WorkflowNode(
                node_id=n["id"],
                node_type=n.get("type") or n.get("node_type") or "tool",
                label=n.get("label") or "",
                config=n.get("config") or {},
                next_on_success=n.get("next_on_success"),
                next_on_failure=n.get("next_on_failure"),
            )
            for n in (graph.get("nodes") or [])
        }
        current = graph.get("entry") or (next(iter(nodes)) if nodes else None)
        max_steps = max_steps or settings.AGENT_MAX_TOOL_CALLS
        outputs: list[dict[str, Any]] = []
        path: list[str] = []
        steps = 0

        while current and current != "end" and steps < max_steps:
            node = nodes.get(current)
            if node is None:
                return WorkflowRunResult(False, outputs, path, error=f"Unknown node {current}")
            path.append(current)
            steps += 1
            ok = True
            payload: dict[str, Any] = {"node_id": current, "type": node.node_type}

            try:
                if node.node_type == "tool":
                    tool_name = node.config.get("tool")
                    args = dict(node.config.get("args") or {})
                    tool = registry.get(tool_name)
                    result = await self._with_retries(tool.execute, ctx, args)
                    payload["tool"] = tool_name
                    payload["result"] = result.to_dict()
                    ok = result.success and not result.requires_confirmation
                    if result.requires_confirmation:
                        outputs.append(payload)
                        return WorkflowRunResult(
                            False,
                            outputs,
                            path,
                            error="Workflow paused for confirmation",
                        )
                elif node.node_type == "condition":
                    expr = str(node.config.get("expression") or "true").lower()
                    ok = expr in ("true", "1", "yes") or bool(ctx.memory.get(expr))
                    payload["condition"] = expr
                    payload["passed"] = ok
                elif node.node_type == "loop":
                    # Single-pass loop stub (future: iterate list)
                    payload["loop"] = "pass"
                    ok = True
                elif node.node_type == "llm":
                    from app.ai.llm import get_llm_provider

                    prompt = str(node.config.get("prompt") or ctx.memory.get("goal") or "")
                    answer = await get_llm_provider().generate(
                        system="You are an enterprise AI agent assistant.",
                        context=str(ctx.memory),
                        question=prompt,
                    )
                    payload["answer"] = answer
                    ctx.memory["last_llm"] = answer
                elif node.node_type == "output":
                    payload["output"] = node.config.get("message") or ctx.memory
                    outputs.append(payload)
                    return WorkflowRunResult(True, outputs, path)
                else:
                    payload["skipped"] = True
            except Exception as exc:
                logger.exception("Workflow node %s failed", current)
                ok = False
                payload["error"] = str(exc)

            outputs.append(payload)
            current = node.next_on_success if ok else (node.next_on_failure or "end")

        return WorkflowRunResult(True, outputs, path)

    async def _with_retries(self, fn, ctx: ToolContext, args: dict[str, Any]):
        last_exc: Exception | None = None
        for attempt in range(settings.AGENT_MAX_RETRIES + 1):
            try:
                return await fn(ctx, **args)
            except Exception as exc:
                last_exc = exc
                logger.warning("Tool retry %s: %s", attempt, exc)
        from app.ai.agents.registry import ToolResult

        return ToolResult(False, error=str(last_exc))
