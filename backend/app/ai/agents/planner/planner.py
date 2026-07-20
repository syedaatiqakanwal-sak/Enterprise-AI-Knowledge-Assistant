"""Task planner — goal, tools, order, dependencies (heuristic + optional LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.agents.registry.base_tool import BaseTool
from app.core.config import settings


@dataclass
class PlanStep:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "args": self.args,
            "depends_on": self.depends_on,
            "rationale": self.rationale,
        }


@dataclass
class AgentPlan:
    goal: str
    agent_type: str
    steps: list[PlanStep]
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "agent_type": self.agent_type,
            "steps": [s.to_dict() for s in self.steps],
            "reasoning": self.reasoning,
            "required_tools": [s.tool for s in self.steps],
        }


class TaskPlanner:
    """Determines goal, required tools, execution order, and dependencies."""

    def plan(
        self,
        goal: str,
        *,
        agent_type: str,
        available_tools: list[BaseTool],
        memory: dict[str, Any] | None = None,
    ) -> AgentPlan:
        memory = memory or {}
        names = {t.name for t in available_tools}
        text = goal.lower().strip()
        steps: list[PlanStep] = []
        reasoning: list[str] = [f"Interpreted goal: {goal}", f"Agent type: {agent_type}"]

        def add(tool: str, args: dict[str, Any] | None = None, rationale: str = "") -> None:
            if tool not in names:
                reasoning.append(f"Skipped unavailable tool: {tool}")
                return
            idx = len(steps)
            depends = [idx - 1] if idx > 0 else []
            steps.append(
                PlanStep(
                    tool=tool,
                    args=args or {},
                    depends_on=depends,
                    rationale=rationale or f"Use {tool}",
                )
            )
            reasoning.append(f"Step {idx + 1}: {tool} — {rationale or tool}")

        if ("meeting" in text or "standup" in text) and (
            "summar" in text or "summary" in text or "minute" in text
        ):
            add("meeting_search", {"query": self._meeting_query(text)}, "Locate the meeting")
            add("meeting_summarizer", {}, "Summarize transcript / minutes")
            if "email" in text or "send" in text or "manager" in text:
                to = self._extract_email(goal) or "manager@example.com"
                add(
                    "email_sender",
                    {"to": to, "subject": "Meeting summary", "body": ""},
                    "Email the summary (may require confirmation)",
                )
        elif "email" in text and "meeting" in text:
            add("meeting_search", {"query": self._meeting_query(text)}, "Find meeting")
            add("meeting_summarizer", {}, "Build summary for email body")
            add(
                "email_sender",
                {
                    "to": self._extract_email(goal) or "manager@example.com",
                    "subject": "Meeting summary",
                    "body": "",
                },
                "Send email",
            )
        elif any(k in text for k in ("ocr", "invoice", "scanned")):
            add("ocr_search", {"query": goal}, "Search OCR results")
        elif any(k in text for k in ("vision", "image", "photo", "yolo")):
            add("vision_analysis", {}, "Inspect vision analyses")
        elif "weather" in text:
            city = self._extract_city(goal) or "London"
            add("weather", {"city": city}, "Fetch weather")
        elif any(k in text for k in ("calculate", "math")) or re.search(
            r"\d+\s*[\+\-\*/]\s*\d+", text
        ):
            expr = self._extract_expression(goal) or "1+1"
            add("calculator", {"expression": expr}, "Compute expression")
        elif "time" in text or "what day" in text or "current date" in text:
            add("current_time", {}, "Get current time")
        elif any(k in text for k in ("sql", "count documents", "how many")):
            add("sql_query", {"query": goal}, "Run readonly analytics query")
        elif "web" in text or "search online" in text:
            add("web_search", {"query": goal}, "Public web search")
        elif any(k in text for k in ("document", "file", "pdf")) and "summar" in text:
            add("document_search", {"query": goal}, "Find document")
            add("rag_search", {"query": goal}, "Summarize via RAG")
        elif "meeting" in text:
            add("meeting_search", {"query": self._meeting_query(text)}, "Search meetings")
        else:
            add("knowledge_search", {"query": goal}, "Retrieve knowledge snippets")
            add("rag_search", {"query": goal}, "Generate grounded answer")

        if not steps:
            add("current_time", {}, "Fallback heartbeat")

        if memory.get("last_meeting_id"):
            for s in steps:
                if s.tool == "meeting_summarizer" and "meeting_id" not in s.args:
                    s.args["meeting_id"] = memory["last_meeting_id"]

        if settings.AGENT_PROVIDER == "llm":
            reasoning.append("AGENT_PROVIDER=llm — heuristic plan retained.")

        return AgentPlan(goal=goal, agent_type=agent_type, steps=steps, reasoning=reasoning)

    @staticmethod
    def _meeting_query(text: str) -> str:
        if "yesterday" in text:
            return "yesterday"
        if "today" in text:
            return "today"
        return text[:120]

    @staticmethod
    def _extract_email(text: str) -> str | None:
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        return m.group(0) if m else None

    @staticmethod
    def _extract_city(text: str) -> str | None:
        m = re.search(r"in ([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)", text)
        if m:
            return m.group(1)
        m2 = re.search(r"weather (?:for |in )?([A-Za-z\s]+)$", text, re.I)
        return m2.group(1).strip() if m2 else None

    @staticmethod
    def _extract_expression(text: str) -> str | None:
        m = re.search(r"([\d\.\s\+\-\*\/\(\)]+)", text)
        if not m:
            return None
        expr = m.group(1).strip()
        return expr if any(c.isdigit() for c in expr) else None
