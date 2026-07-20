#!/usr/bin/env bash
# PostgreSQL logical backup
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_DIR:-./backups/postgres}"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/pg_${POSTGRES_DB:-enterprise_ai}_${STAMP}.sql.gz"
echo "Backing up Postgres to $FILE"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${POSTGRES_HOST:-localhost}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "${POSTGRES_USER:-admin}" \
  -d "${POSTGRES_DB:-enterprise_ai}" \
  --no-owner --format=plain | gzip > "$FILE"
echo "Done: $FILE"
