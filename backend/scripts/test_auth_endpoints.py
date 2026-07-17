"""
End-to-end Module 2B authentication API test script.

Run against a live server:
    python scripts/test_auth_endpoints.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "app.log"


def _extract_latest_token(pattern: str) -> str | None:
    if not LOG_PATH.exists():
        return None
    text = LOG_PATH.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(pattern, text)
    return matches[-1] if matches else None


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=30.0)
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))

    import uuid as _uuid

    email = f"employee.{_uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass123!"
    new_password = "NewPass123!"

    # Register
    r = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test Employee"},
    )
    if r.status_code == 409:
        # Clean path: login instead
        r = client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            # try new password from prior run
            r = client.post("/auth/login", json={"email": email, "password": new_password})
            if r.status_code == 200:
                password = new_password
    check("POST /auth/register|login", r.status_code in (200, 201), f"{r.status_code}")
    if r.status_code not in (200, 201):
        print(r.text)
        return 1

    data = r.json()
    access = data["tokens"]["access_token"]
    refresh = data["tokens"]["refresh_token"]
    check("tokens issued", bool(access and refresh))
    check("employee role assigned", any(x["name"] == "employee" for x in data["user"]["roles"]))

    # Current user
    r = client.get("/users/me", headers={"Authorization": f"Bearer {access}"})
    check("GET /users/me", r.status_code == 200, f"{r.status_code}")

    # Refresh
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    check("POST /auth/refresh", r.status_code == 200, f"{r.status_code}")
    if r.status_code == 200:
        access = r.json()["access_token"]
        new_refresh = r.json()["refresh_token"]
        # Old refresh must be invalid
        r_old = client.post("/auth/refresh", json={"refresh_token": refresh})
        check("refresh rotation invalidates old", r_old.status_code == 401, f"{r_old.status_code}")
        refresh = new_refresh

    # Logout
    r = client.post("/auth/logout", json={"refresh_token": refresh})
    check("POST /auth/logout", r.status_code == 200, f"{r.status_code}")
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    check("logout revokes refresh", r.status_code == 401, f"{r.status_code}")

    # Re-login for remaining flows
    r = client.post("/auth/login", json={"email": email, "password": password})
    check("POST /auth/login", r.status_code == 200, f"{r.status_code}")
    access = r.json()["tokens"]["access_token"]
    refresh = r.json()["tokens"]["refresh_token"]

    # Forgot + reset password
    r = client.post("/auth/forgot-password", json={"email": email})
    check("POST /auth/forgot-password", r.status_code == 200, f"{r.status_code}")

    reset_token = _extract_latest_token(r"Or use this token: ([A-Za-z0-9_-]+)")
    # Password reset emails contain "Or use this token:" — may also match verify emails.
    # Prefer AUTH_TOKEN= structured log lines
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            m = re.search(r"AUTH_TOKEN=([A-Za-z0-9_-]+)", line)
            if m and m.group(1):
                # Heuristic: password-reset emails mention Reset
                if "reset" in line.lower() or "Reset" in line:
                    reset_token = m.group(1)
                    break
        if not reset_token:
            for line in reversed(lines):
                if "Password reset" in line or "reset-password" in line:
                    m = re.search(r"AUTH_TOKEN=([A-Za-z0-9_-]+)", line) or re.search(
                        r"Or use this token: ([A-Za-z0-9_-]+)", line
                    )
                    if m:
                        reset_token = m.group(1)
                        break
                    m = re.search(r"token=([A-Za-z0-9_-]+)", line)
                    if m:
                        reset_token = m.group(1)
                        break

    if reset_token:
        r = client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": new_password},
        )
        check("POST /auth/reset-password", r.status_code == 200, f"{r.status_code}")
        r = client.post("/auth/login", json={"email": email, "password": new_password})
        check("login with new password", r.status_code == 200, f"{r.status_code}")
        password = new_password
        access = r.json()["tokens"]["access_token"]
        refresh = r.json()["tokens"]["refresh_token"]
    else:
        check("POST /auth/reset-password", False, "could not extract reset token from logs")

    # Email verification — register a fresh user to capture verify token
    verify_email = f"verify.{_uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/auth/register",
        json={
            "email": verify_email,
            "password": "VerifyPass123!",
            "full_name": "Verify User",
        },
    )
    check("register for verify-email", r.status_code in (200, 201), f"{r.status_code}")
    verify_token = None
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in reversed(lines):
            if "verify" in line.lower() and "AUTH_TOKEN=" in line:
                m = re.search(r"AUTH_TOKEN=([A-Za-z0-9_-]+)", line)
                if m and m.group(1):
                    verify_token = m.group(1)
                    break
        if not verify_token:
            for line in reversed(lines):
                if "verify-email" in line or "Verify your" in line:
                    m = re.search(r"AUTH_TOKEN=([A-Za-z0-9_-]+)", line) or re.search(
                        r"Or use this token: ([A-Za-z0-9_-]+)", line
                    )
                    if m:
                        verify_token = m.group(1)
                        break
                    m = re.search(r"token=([A-Za-z0-9_-]+)", line)
                    if m:
                        verify_token = m.group(1)
                        break
    if verify_token:
        r = client.post("/auth/verify-email", json={"token": verify_token})
        check("POST /auth/verify-email", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        r = client.post(
            "/auth/login",
            json={"email": verify_email, "password": "VerifyPass123!"},
        )
        if r.status_code == 200:
            check(
                "user is_verified after confirm",
                r.json()["user"]["is_verified"] is True,
            )
    else:
        check("POST /auth/verify-email", False, "token not found in logs")

    # Unauthorized me
    r = client.get("/users/me")
    check("GET /users/me without token -> 401", r.status_code == 401, f"{r.status_code}")

    # Validation
    r = client.post(
        "/auth/register",
        json={"email": "bad", "password": "weak", "full_name": "x"},
    )
    check("validation rejects weak register", r.status_code == 422, f"{r.status_code}")

    # Admin seed login
    r = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    check("seeded admin login", r.status_code == 200, f"{r.status_code}")
    if r.status_code == 200:
        roles = [x["name"] for x in r.json()["user"]["roles"]]
        check("admin role present", "admin" in roles, str(roles))

    failed = [name for name, ok, _ in results if not ok]
    print("\n=== SUMMARY ===")
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
