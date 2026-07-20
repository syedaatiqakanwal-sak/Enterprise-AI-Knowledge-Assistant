"""
Email delivery service.

In development without SMTP, verification and reset tokens are written to the
application log so flows remain testable without an external mail provider.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _extract_token_hint(body: str) -> str:
    """Pull a token from email body for structured logging (dev aid)."""
    import re

    match = re.search(r"Or use this token: ([A-Za-z0-9_-]+)", body)
    if match:
        return match.group(1)
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else ""


class EmailService:
    """Send transactional auth emails (verification, password reset)."""

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> None:
        """Send an email via SMTP or log it when SMTP is not configured."""
        if not settings.SMTP_HOST:
            logger.info(
                "EMAIL (dev/no-SMTP) | to=%s | subject=%s | AUTH_TOKEN=%s | body=%s",
                to_email,
                subject,
                _extract_token_hint(text_body or html_body),
                text_body or html_body,
            )
            return

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body or html_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_TLS:
                smtp.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("Email sent | to=%s | subject=%s", to_email, subject)

    def send_verification_email(self, *, to_email: str, token: str) -> None:
        """Email a one-time email-verification token / link."""
        link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        subject = f"Verify your {settings.PROJECT_NAME} account"
        text = (
            f"Welcome!\n\nVerify your email by opening:\n{link}\n\n"
            f"Or use this token: {token}\n\n"
            f"This link expires in {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} hour(s)."
        )
        html = (
            f"<p>Welcome!</p>"
            f"<p><a href=\"{link}\">Verify your email</a></p>"
            f"<p>Or use this token: <code>{token}</code></p>"
        )
        self.send_email(to_email=to_email, subject=subject, html_body=html, text_body=text)

    def send_password_reset_email(self, *, to_email: str, token: str) -> None:
        """Email a one-time password-reset token / link."""
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = f"Reset your {settings.PROJECT_NAME} password"
        text = (
            f"We received a password reset request.\n\n"
            f"Open: {link}\n\nOr use this token: {token}\n\n"
            f"Expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minute(s). "
            "If you did not request this, ignore this email."
        )
        html = (
            f"<p>Password reset requested.</p>"
            f"<p><a href=\"{link}\">Reset password</a></p>"
            f"<p>Or use this token: <code>{token}</code></p>"
        )
        self.send_email(to_email=to_email, subject=subject, html_body=html, text_body=text)


email_service = EmailService()
