# Module 3 — Authentication API & User Management

## Architecture

```
Routers (app/api/v1/auth.py, users.py)
    → Services (auth, user, token, email)
        → Repositories (user, role, refresh, verification/reset)
            → PostgreSQL (async SQLAlchemy 2.0)
```

Unified envelope on every response:

```json
{ "success": true, "message": "...", "data": {}, "errors": null }
```

```json
{ "success": false, "message": "...", "errors": { "code": "..." } }
```

## Endpoints

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/api/v1/auth/register` | Public | Employee role, verification email |
| POST | `/api/v1/auth/login` | Public | |
| POST | `/api/v1/auth/logout` | Public | Revokes refresh token |
| POST | `/api/v1/auth/refresh` | Public | Rotation |
| POST | `/api/v1/auth/forgot-password` | Public | Reset token 30 min |
| POST | `/api/v1/auth/reset-password` | Public | One-time |
| POST | `/api/v1/auth/verify-email` | Public | 24 h token |
| POST | `/api/v1/auth/change-password` | Bearer | Revokes all sessions |
| GET | `/api/v1/users/me` | Bearer | |
| PUT | `/api/v1/users/profile` | Bearer | full_name, phone |
| GET | `/api/v1/users` | Manager/Admin | Paginated |
| GET | `/api/v1/users/{id}` | Bearer | Self or elevated |
| DELETE | `/api/v1/users/{id}` | Admin | Soft delete |

## RBAC helpers

- `require_admin`
- `require_manager` (admin or manager)
- `require_permission("users:read")`
- `require_roles("admin", "manager")`

## Tests

```bash
cd backend
pytest -q
```

## Migration

```bash
alembic upgrade head   # includes 0003_user_phone
```
