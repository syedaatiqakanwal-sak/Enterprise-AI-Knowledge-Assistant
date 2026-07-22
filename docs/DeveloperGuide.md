# Developer Guide

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy async, Alembic  
- Frontend: React + Vite + TypeScript + Tailwind  
- Data: PostgreSQL, MongoDB, Redis, Qdrant  
- Local AI: Ollama (LLM) + sentence-transformers MiniLM (embeddings)

## Local setup (without Docker for API)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r requirements.txt
pip install -r requirements-ai.txt   # sentence-transformers, torch, qdrant-client
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

Ensure Postgres/Redis/Mongo/Qdrant are reachable (Compose data services are enough).

### Local RAG providers (dev)

In the project-root `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2

EMBEDDING_PROVIDER=minilm
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

Install and start Ollama separately, then:

```bash
ollama pull llama3.2
```

On API startup the MiniLM model is loaded **once** and reused for all embed/index/search calls.

**Windows note:** if `pip install torch` fails with a long-path error, install into a short directory and add a `.pth` file:

```powershell
pip install --target C:\pyai torch --index-url https://download.pytorch.org/whl/cpu
pip install --target C:\pyai sentence-transformers==3.0.1
# from backend\.venv\Lib\site-packages:
Set-Content aaa_pyai.pth "C:\pyai"
```

Or enable Windows long paths (admin): `LongPathsEnabled=1` under `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem`.

Admin probes:

- `GET /api/v1/system/embeddings/status`
- `GET /api/v1/system/ollama/status`
- `GET /api/v1/system/ollama/models`

After switching embedding providers, **reindex** documents so vectors match the new model:

```bash
POST /api/v1/documents/{id}/index?sync=true
# or
POST /api/v1/documents/reindex
```

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
