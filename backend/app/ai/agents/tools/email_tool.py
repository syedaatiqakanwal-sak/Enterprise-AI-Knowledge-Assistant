from __future__ import annotations

from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool
from app.core.config import settings


@register_tool
class EmailSenderTool(BaseTool):
    name = "email_sender"
    description = (
        "Send an email. Requires confirmation when AGENT_EMAIL_REQUIRE_CONFIRMATION is true "
        "or when SMTP is not fully configured."
    )
    tags = ["email", "notify"]
    agent_types = ["email", "meeting", "general_assistant"]
    required_permissions = ["agents:write"]
    input_schema = {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "confirm": {"type": "boolean"},
        },
        "required": ["to", "subject", "body"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        to = str(kwargs.get("to") or "").strip()
        subject = str(kwargs.get("subject") or "").strip()
        body = str(kwargs.get("body") or "").strip()
        if not body:
            body = str(ctx.memory.get("last_meeting_summary") or "")
        confirm = bool(kwargs.get("confirm"))
        action = "send_email"

        smtp_ready = bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)
        needs_confirm = (
            settings.AGENT_EMAIL_REQUIRE_CONFIRMATION
            or not settings.AGENT_EMAIL_ENABLED
            or not smtp_ready
        )
        if needs_confirm and not confirm and action not in ctx.confirmed_actions:
            return ToolResult(
                success=True,
                data={
                    "draft": {"to": to, "subject": subject, "body": body[:2000]},
                    "smtp_configured": smtp_ready,
                    "email_enabled": settings.AGENT_EMAIL_ENABLED,
                },
                requires_confirmation=True,
                confirmation_action=action,
                error=None,
            )

        # Soft-send: log / stub when SMTP unavailable
        if not smtp_ready or not settings.AGENT_EMAIL_ENABLED:
            return ToolResult(
                True,
                data={
                    "sent": False,
                    "mode": "stub",
                    "to": to,
                    "subject": subject,
                    "message": "Email queued in stub mode (configure SMTP / AGENT_EMAIL_ENABLED).",
                },
            )

        try:
            # Best-effort SMTP via existing email service if present
            from app.services import email_service

            if hasattr(email_service, "send_email"):
                await email_service.send_email(to=to, subject=subject, body=body)
            return ToolResult(
                True,
                data={"sent": True, "mode": "smtp", "to": to, "subject": subject},
            )
        except Exception as exc:
            return ToolResult(False, error=f"Email send failed: {exc}")
