"""Locust load test — auth, chat, RAG, OCR, meetings, agents."""

from __future__ import annotations

import os

from locust import HttpUser, between, task


class EnterpriseAIUser(HttpUser):
    wait_time = between(1, 3)
    token: str | None = None

    def on_start(self) -> None:
        email = os.getenv("TEST_EMAIL", "admin@example.com")
        password = os.getenv("TEST_PASSWORD", "AdminPass123!")
        with self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            catch_response=True,
            name="auth.login",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json().get("data") or {}
                tokens = data.get("tokens") or {}
                self.token = tokens.get("access_token")
                resp.success()
            else:
                resp.failure(f"login failed: {resp.status_code}")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def health(self) -> None:
        self.client.get("/live", name="probe.live")
        self.client.get("/ready", name="probe.ready")

    @task(5)
    def chat_sessions(self) -> None:
        self.client.get("/api/v1/chat/sessions", headers=self._headers(), name="chat.sessions")

    @task(4)
    def search(self) -> None:
        self.client.get(
            "/api/v1/search",
            params={"q": "policy", "limit": 5},
            headers=self._headers(),
            name="rag.search",
        )

    @task(2)
    def ocr(self) -> None:
        self.client.get("/api/v1/ocr/jobs", headers=self._headers(), name="ocr.jobs")

    @task(2)
    def meetings(self) -> None:
        self.client.get("/api/v1/meetings", headers=self._headers(), name="meetings.list")

    @task(2)
    def agents(self) -> None:
        self.client.get(
            "/api/v1/agent/sessions", headers=self._headers(), name="agents.sessions"
        )
