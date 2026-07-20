"""Quick Module 3 smoke test against a live server."""

from __future__ import annotations

import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def main() -> None:
    c = httpx.Client(timeout=30)
    email = f"m3-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post(
        f"{BASE}/auth/register",
        json={
            "email": email,
            "password": "StrongPass1!",
            "full_name": "M3 User",
            "phone": "+15551111",
        },
    )
    print("register", r.status_code, r.json().get("success"), r.json().get("message"))
    assert r.status_code == 201
    token = r.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = c.put(
        f"{BASE}/users/profile",
        headers=headers,
        json={"full_name": "M3 Updated", "phone": "+15552222"},
    )
    print("profile", r.status_code, r.json()["data"]["full_name"])
    assert r.status_code == 200

    r = c.post(
        f"{BASE}/auth/change-password",
        headers=headers,
        json={
            "current_password": "StrongPass1!",
            "new_password": "NewerPass1!",
        },
    )
    print("change-pw", r.status_code, r.json().get("success"))
    assert r.status_code == 200

    r = c.post(
        f"{BASE}/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    print("admin login", r.status_code, r.json().get("success"))
    assert r.status_code == 200
    admin_headers = {
        "Authorization": f"Bearer {r.json()['data']['tokens']['access_token']}"
    }
    r = c.get(f"{BASE}/users", headers=admin_headers)
    print("list users", r.status_code, "total", r.json()["data"]["total"])
    assert r.status_code == 200
    print("OK")


if __name__ == "__main__":
    main()
