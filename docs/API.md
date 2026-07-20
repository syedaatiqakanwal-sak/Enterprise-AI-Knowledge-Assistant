# API Documentation

Interactive OpenAPI: **`/docs`** (Swagger) · **`/redoc`** · schema **`/api/v1/openapi.json`**

## Base URL

```
{origin}/api/v1
```

## Endpoint groups

| Tag | Prefix | Notes |
|-----|--------|-------|
| Authentication | `/auth` | login, register, refresh, password reset |
| Users | `/users` | profile & directory |
| Documents | `/documents` | DMS upload/list/versions |
| Chat / RAG | `/chat` | grounded Q&A |
| Semantic Search | `/search` | vector search |
| OCR / Vision | `/ocr`, `/vision` | extraction & analysis |
| Meetings | `/meetings` | intelligence pipeline |
| AI Agents | `/agent` | sessions, tools, workflows |
| Analytics | `/analytics` | usage & cost |
| Admin / Tenancy | `/admin` | orgs, teams, users, API keys, audit |
| Health | `/health`, `/live`, `/ready` | ops probes (also at root) |
| Observability | `/metrics` | Prometheus |

## Auth example

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"admin@example.com","password":"AdminPass123!"}
```

Response envelope:

```json
{
  "success": true,
  "message": "…",
  "data": {
    "user": { "id": "…", "email": "…" },
    "tokens": {
      "access_token": "…",
      "refresh_token": "…",
      "token_type": "bearer",
      "expires_in": 900
    }
  },
  "errors": null
}
```

JWT access claims include `sub`, `roles`, `tenant_id`, `organization_id`, `team_id`.

## Correlation

Send `X-Request-ID` / `X-Correlation-ID`; responses echo them for log correlation.
