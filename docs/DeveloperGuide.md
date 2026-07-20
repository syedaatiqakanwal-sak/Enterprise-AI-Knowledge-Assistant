# Developer Guide

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy async, Alembic  
- Frontend: React + Vite + TypeScript + Tailwind  
- Data: PostgreSQL, MongoDB, Redis, Qdrant  

## Local setup (without Docker for API)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

Ensure Postgres/Redis/Mongo/Qdrant are reachable (Compose data services are enough).

## Conventions

- Modules are additive — do not break prior APIs  
- Response envelope: `{ success, message, data, errors }`  
- Permissions via RBAC codes (`documents:read`, `admin:all`, …)  
- Tenant isolation on admin and resource queries  

## Tests

```bash
cd backend
pytest -q
```

```bash
cd frontend
npm run build
```

## Load tests

```bash
# k6
k6 run loadtests/k6/smoke.js

# Locust
locust -f loadtests/locust/locustfile.py --host http://localhost:8000
```

## Useful probes

```bash
curl localhost:8000/live
curl localhost:8000/ready
curl localhost:8000/metrics
```
