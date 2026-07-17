# Module 2B — Enterprise Authentication System

## Overview

JWT-based authentication with refresh-token rotation, email verification,
password reset, bcrypt password hashing, and RBAC (Admin / Manager / Employee).

Base URL: `http://127.0.0.1:8000/api/v1`

Swagger UI: `http://127.0.0.1:8000/docs`

---

## Roles

| Role | Description |
|------|-------------|
| `admin` | Full administrative access (`admin:all` + all permissions) |
| `manager` | Elevated document and user-read access |
| `employee` | Default role assigned on registration |

Permissions are seeded on startup (`users:*`, `documents:*`, `roles:*`, `admin:all`).

---

## Endpoints

### `POST /auth/register`

Create an employee account, send verification email, return tokens.

**Request**
```json
{
  "email": "user@example.com",
  "password": "StrongPass1!",
  "full_name": "Jane Doe"
}
```

Password rules: 8–128 chars, upper, lower, digit, special character.

**Response `201`**
```json
{
  "user": {
    "id": "...",
    "email": "user@example.com",
    "full_name": "Jane Doe",
    "is_active": true,
    "is_verified": false,
    "last_login": null,
    "created_at": "...",
    "roles": [{ "id": "...", "name": "employee", "description": "..." }]
  },
  "tokens": {
    "access_token": "<jwt>",
    "refresh_token": "<opaque>",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

---

### `POST /auth/login`

**Request**
```json
{ "email": "user@example.com", "password": "StrongPass1!" }
```

**Response `200`** — same shape as register (`AuthResponse`).

---

### `POST /auth/logout`

Revokes the provided refresh token (idempotent).

**Request**
```json
{ "refresh_token": "<opaque>" }
```

**Response `200`**
```json
{ "message": "Logged out successfully", "success": true }
```

---

### `POST /auth/refresh`

Rotates refresh token; previous token is invalidated.

**Request**
```json
{ "refresh_token": "<opaque>" }
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<new-opaque>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

### `POST /auth/forgot-password`

Always returns a generic success message (anti-enumeration).

**Request**
```json
{ "email": "user@example.com" }
```

In development (no SMTP), the reset token is written to `backend/logs/app.log`
as `AUTH_TOKEN=...`.

---

### `POST /auth/reset-password`

**Request**
```json
{
  "token": "<reset-token>",
  "new_password": "NewStrong1!"
}
```

Revokes all refresh tokens for the user.

---

### `POST /auth/verify-email`

**Request**
```json
{ "token": "<verification-token>" }
```

Sets `is_verified=true`. Token is emailed at registration (logged in development).

---

### `GET /users/me`

Requires `Authorization: Bearer <access_token>`.

**Response `200`** — `UserOut` profile with roles.

---

## Security features

- BCrypt password hashing (`passlib`)
- Access JWT (short-lived) + opaque refresh tokens (hashed at rest)
- Refresh rotation + logout revocation
- Soft delete (`deleted_at`) on users/roles/permissions
- Rate limiting on auth routes (Redis, in-memory fallback)
- Input sanitization on names/emails
- JWT middleware (soft parse) + `get_current_user` / `require_roles` / `require_permissions` dependencies

---

## Seed admin

Configured via `.env`:

```
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=AdminPass123!
```

Created automatically on startup if missing.

---

## Migrations

```bash
cd backend
alembic upgrade head
```

Revisions:
- `0001_initial_baseline` — Module 2A
- `0002_auth_rbac` — users, roles, permissions, user_roles, role_permissions, refresh_tokens, email_verification_tokens, password_reset_tokens

---

## Automated test results

Command:

```bash
python scripts/test_auth_endpoints.py
```

Latest run: **all endpoints passed** (register, login, me, refresh rotation, logout, forgot/reset password, verify-email, validation 422, seeded admin RBAC).

---

## Local notes

- `.env` currently points Postgres to `127.0.0.1` for Windows local testing.
- For Docker Compose, set `POSTGRES_HOST=postgres`, `MONGO_HOST=mongodb`, `REDIS_HOST=redis` (and matching URLs).
