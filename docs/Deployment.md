# Deployment Guide

Cloud-agnostic deployment for AWS, Azure, GCP, or any Kubernetes cluster.

## Prerequisites

- Docker 24+ / Compose v2
- kubectl + optional kustomize
- Container registry (GHCR, ECR, ACR, GCR)
- Secrets manager or sealed secrets for production

## Environment files

| File | Use |
|------|-----|
| `.env.example` | Local / development template |
| `.env.production.example` | Production template → copy to `.env.production` |

## Docker Compose

### Development

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

### Production

```bash
cp .env.production.example .env.production
# edit secrets
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Services: Nginx, backend, frontend, worker, Postgres, MongoDB, Redis, Qdrant, Prometheus, Grafana.

## Kubernetes

```bash
# Review and replace secrets in k8s/base/namespace-config.yaml
kubectl apply -k k8s/overlays/staging
kubectl apply -k k8s/overlays/production
```

Includes: Namespace, ConfigMap, Secret, Deployments, Services, Ingress, PVCs, PV example, HPA, NetworkPolicy.

### TLS / Let's Encrypt

1. Install cert-manager on the cluster  
2. Create a ClusterIssuer (`letsencrypt-prod`)  
3. Uncomment `cert-manager.io/cluster-issuer` on the Ingress  
4. Point DNS `app.example.com` at the load balancer  

Compose TLS: place `fullchain.pem` / `privkey.pem` under `nginx/certs/` and enable the HTTPS server block in `nginx/nginx.conf`.

## Images

| Image | Dockerfile |
|-------|------------|
| Backend | `backend/Dockerfile` (multi-stage) |
| Worker | `backend/Dockerfile.worker` |
| Frontend | `frontend/Dockerfile` (Vite → Nginx) |

CI builds and pushes to GHCR on `main` (see `.github/workflows/ci.yml`). Deploy step is a **placeholder** — wire your cluster credentials via GitHub Environments.

## Health probes

| Path | Purpose |
|------|---------|
| `/live` | Liveness (process up) |
| `/ready` | Readiness (Postgres + Redis + Mongo; Qdrant optional) |
| `/health` | Full dependency status |
| `/metrics` | Prometheus scrape |

## Secrets

- Environment variables  
- Docker secrets / K8s Secrets mounted at `/run/secrets`  
- Abstraction: `app.core.secrets.SecretProvider`

## Rollback

1. Redeploy previous image tag  
2. Restore Postgres/Mongo from `scripts/backup/` if a migration failed  
3. Keep Qdrant snapshots via the placeholder script wired to the snapshots API  
