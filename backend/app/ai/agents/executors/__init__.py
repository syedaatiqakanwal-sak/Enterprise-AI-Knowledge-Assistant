"""Plan executor — multi-step tool runs with retries, confirmation, observability."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.agents.memory import AgentMemory
from app.ai.agents.planner import AgentPlan
from app.ai.agents.registry import ToolContext, ToolResult, ensure_tools_loaded
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExecutionEvent:
    step_index: int
    tool_name: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    retries: int = 0
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "tool_name": self.tool_name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "retries": self.retries,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class ExecutionResult:
    success: bool
    final_response: str
    events: list[ExecutionEvent] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    waiting_confirmation: bool = False
    confirmation_action: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "final_response": self.final_response,
            "events": [e.to_dict() for e in self.events],
            "reasoning": self.reasoning,
            "waiting_confirmation": self.waiting_confirmation,
            "confirmation_action": self.confirmation_action,
            "metrics": self.metrics,
        }


class AgentExecutor:
    async def run_plan(
        self,
        plan: AgentPlan,
        ctx: ToolContext,
        memory: AgentMemory,
        *,
        confirm: bool = False,
    ) -> ExecutionResult:
        registry = ensure_tools_loaded()
        events: list[ExecutionEvent] = []
        reasoning = list(plan.reasoning)
        started = time.perf_counter()
        last_outputs: list[dict[str, Any]] = []

        if confirm:
            ctx.confirmed_actions.add("send_email")

        for idx, step in enumerate(plan.steps):
            if idx >= settings.AGENT_MAX_TOOL_CALLS:
                reasoning.append("Stopped: max tool calls reached")
                break

            args = dict(step.args)
            # Inject memory into email body if empty
            if step.tool == "email_sender" and not args.get("body"):
                args["body"] = str(
                    ctx.memory.get("last_meeting_summary")
                    or last_outputs[-1].get("executive_summary")
                    or last_outputs[-1].get("summary")
                    or "Please see the meeting summary."
                )
            if confirm and step.tool == "email_sender":
                args["confirm"] = True

            event = ExecutionEvent(
                step_index=idx,
                tool_name=step.tool,
                status="running",
                input=args,
            )
            retries = 0
            result: ToolResult | None = None
            t0 = time.perf_counter()
            while True:
                try:
                    tool = registry.get(step.tool)
                    result = await tool.execute(ctx, **args)
                    break
                except Exception as exc:
                    retries += 1
                    logger.warning("Tool %s failed attempt %s: %s", step.tool, retries, exc)
                    if retries > settings.AGENT_MAX_RETRIES:
                        result = ToolResult(False, error=str(exc))
                        break
            latency = (time.perf_counter() - t0) * 1000
            assert result is not None
            event.latency_ms = round(latency, 2)
            event.retries = retries
            event.output = result.to_dict()
            event.requires_confirmation = result.requires_confirmation

            if result.requires_confirmation:
                event.status = "waiting_confirmation"
                events.append(event)
                await memory.append_tool_history(event.to_dict())
                return ExecutionResult(
                    success=False,
                    final_response=(
                        "I prepared the action but need your confirmation before sending email. "
                        "Re-run with confirm=true to proceed."
                    ),
                    events=events,
                    reasoning=reasoning
                    + ["Waiting for user confirmation before email_sender"],
                    waiting_confirmation=True,
                    confirmation_action=result.confirmation_action,
                    metrics={"total_ms": round((time.perf_counter() - started) * 1000, 2)},
                )

            if not result.success:
                event.status = "failed"
                event.error = result.error
                events.append(event)
                await memory.append_tool_history(event.to_dict())
                # Error recovery: continue if non-critical, else stop
                if step.tool in ("web_search", "weather"):
                    reasoning.append(f"Recovered from {step.tool} failure — continuing")
                    continue
                return ExecutionResult(
                    success=False,
                    final_response=f"Tool `{step.tool}` failed: {result.error}",
                    events=events,
                    reasoning=reasoning,
                    metrics={"total_ms": round((time.perf_counter() - started) * 1000, 2)},
                )

            event.status = "success"
            events.append(event)
            await memory.append_tool_history(event.to_dict())
            data = result.data or {}
            last_outputs.append(data)
            ctx.memory.update(
                {k: v for k, v in data.items() if isinstance(k, str) and k.startswith("last_")}
            )
            if "executive_summary" in data:
                ctx.memory["last_meeting_summary"] = data["executive_summary"]
            if data.get("items") and step.tool == "meeting_search":
                items = data["items"]
                if items:
                    ctx.memory["last_meeting_id"] = items[0].get("id")

        await memory.merge_short_term(dict(ctx.memory))
        final = self._compose_response(plan, last_outputs, events)
        return ExecutionResult(
            success=True,
            final_response=final,
            events=events,
            reasoning=reasoning,
            metrics={
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
                "tool_calls": len(events),
                "failures": sum(1 for e in events if e.status == "failed"),
            },
        )

    def _compose_response(
        self,
        plan: AgentPlan,
        outputs: list[dict[str, Any]],
        events: list[ExecutionEvent],
    ) -> str:
        if not outputs:
            return "I completed planning but no tool produced output."
        last = outputs[-1]
        if "answer" in last:
            return str(last["answer"])
        if "executive_summary" in last:
            actions = last.get("action_items") or []
            return (
                f"Meeting summary: {last['executive_summary']}\n"
                f"Action items: {len(actions)}. Decisions: {len(last.get('decisions') or [])}."
            )
        if "summary" in last and isinstance(last["summary"], dict):
            return str(last["summary"].get("executive_summary") or last["summary"])
        if "result" in last and "expression" in last:
            return f"{last['expression']} = {last['result']}"
        if "utc" in last:
            return f"Current UTC time: {last['utc']} ({last.get('day_of_week')})"
        if "temperature_c" in last:
            return f"Weather in {last.get('city')}: {last.get('temperature_c')}°C, {last.get('conditions')}"
        if "sent" in last:
            return f"Email status: {'sent' if last.get('sent') else last.get('message') or 'stubbed'}."
        tools = ", ".join(e.tool_name for e in events)
        return f"Completed tools [{tools}] for goal: {plan.goal}"
