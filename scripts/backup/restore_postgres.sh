#!/usr/bin/env bash
# Restore PostgreSQL from gzipped SQL dump
set -euo pipefail
FILE="${1:?Usage: $0 <backup.sql.gz>}"
echo "Restoring Postgres from $FILE"
gunzip -c "$FILE" | PGPASSWORD="${POSTGRES_PASSWORD}" psql \
  -h "${POSTGRES_HOST:-localhost}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "${POSTGRES_USER:-admin}" \
  -d "${POSTGRES_DB:-enterprise_ai}"
echo "Restore complete"
