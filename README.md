# Enterprise AI Knowledge Assistant

Production-ready, multi-tenant enterprise platform for chatting with company knowledge — documents, RAG, OCR/vision, meeting intelligence, AI agents, analytics, and SaaS administration.

**Version:** 0.12.0 · **Stack:** FastAPI · React/Vite · PostgreSQL · MongoDB · Redis · Qdrant

## Quick start (development)

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

- API: http://localhost:8000/docs  
- Frontend: http://localhost:3000  
- Probes: `/live` · `/ready` · `/health` · `/metrics`

### Local Ollama + MiniLM (optional, no cloud keys)

For fully local RAG on Windows without Docker AI images:

1. Install [Ollama](https://ollama.com) and run `ollama pull llama3.2`
2. In `.env` set:
   - `LLM_PROVIDER=ollama`
   - `OLLAMA_MODEL=llama3.2`
   - `EMBEDDING_PROVIDER=minilm`
   - `EMBEDDING_MODEL=all-MiniLM-L6-v2`
3. Backend: `pip install -r backend/requirements-ai.txt` then start uvicorn
4. Admin → **Settings → AI / Ollama** to ping Ollama and view embedding status

See [DeveloperGuide.md](docs/DeveloperGuide.md) for details.

## Environments

| Env | Compose / Kustomize |
|-----|---------------------|
| Development | `docker-compose.dev.yml` |
| Production | `docker-compose.prod.yml` |
| Staging K8s | `k8s/overlays/staging` |
| Production K8s | `k8s/overlays/production` |

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture.md](docs/Architecture.md) | System design + Mermaid diagrams |
| [Deployment.md](docs/Deployment.md) | Docker, Kubernetes, SSL, cloud-agnostic deploy |
| [API.md](docs/API.md) | API overview & OpenAPI |
| [DeveloperGuide.md](docs/DeveloperGuide.md) | Local setup, conventions |
| [OperationsGuide.md](docs/OperationsGuide.md) | Monitoring, backups, incidents |

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): lint → pytest → frontend build → Docker build → Trivy scan → push images → deploy placeholder.

## Security highlights

- JWT + RBAC + tenant isolation  
- Rate limiting, CORS lockdown in staging/production  
- Security headers + Nginx reverse proxy  
- Secrets via env / Docker secrets / Kubernetes Secrets (`app.core.secrets`)  
- Non-root containers, NetworkPolicy, HPA  

## License

Proprietary — see contact in OpenAPI `/docs`.
