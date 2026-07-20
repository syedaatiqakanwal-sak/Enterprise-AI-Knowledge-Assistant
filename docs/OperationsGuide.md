# Operations Guide

## Monitoring

- **Prometheus** scrapes backend `/metrics` (HTTP latency & counters)  
- Config: `monitoring/prometheus/prometheus.yml`  
- **Grafana** provisioned datasource + API overview dashboard  
- Compose: services `prometheus`, `grafana` in `docker-compose.prod.yml`  

Optional exporters: Redis exporter, Qdrant `/metrics`, node-exporter for host metrics.

## Logging

- Staging/production: **structured JSON** (`LOG_JSON=true`)  
- Fields: timestamp, level, message, request_id, correlation_id, environment, version  
- Rotation: `LOG_DIR` with `app.log` / `error.log` (size + backup count)  
- Ship to ELK / Loki / CloudWatch via sidecar or agent  

## Health & incidents

| Symptom | Check |
|---------|-------|
| Pod restart loop | `/live` failing → crash / OOM |
| 503 from ingress | `/ready` → Postgres/Redis/Mongo |
| Degraded RAG | Qdrant status in `/health` |
| Auth spikes | Rate limit + Redis |

## Backups

```bash
./scripts/backup/backup_postgres.sh
./scripts/backup/backup_mongo.sh
./scripts/backup/backup_qdrant.sh   # placeholder → wire snapshots API
```

Restore:

```bash
./scripts/backup/restore_postgres.sh backups/postgres/pg_….sql.gz
./scripts/backup/restore_mongo.sh backups/mongo/<stamp>
```

Schedule via CronJob in Kubernetes or host cron.

## Performance checklist

- Postgres indexes already on tenant/user/document foreign keys — review slow queries with `pg_stat_statements`  
- Redis for rate limits & cache — enable AOF in prod compose  
- Nginx gzip + asset cache headers  
- Backend HPA scales on CPU (70%)  
- Prefer `/ready` for load balancer; keep `/metrics` internal  

## Security ops

- Rotate `SECRET_KEY` and API keys via Admin console  
- Scan images in CI (Trivy)  
- Enforce NetworkPolicy + non-root UIDs  
- Short-lived access tokens (15m prod example)  
- Never wildcard CORS in staging/production  

## Capacity plans (subscription architecture)

Free / Starter / Professional / Enterprise usage limits are enforced at the tenancy layer (Module 11). Payment gateways are intentionally out of scope.
