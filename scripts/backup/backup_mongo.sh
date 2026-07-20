#!/usr/bin/env bash
# MongoDB dump
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_DIR:-./backups/mongo}/${STAMP}"
mkdir -p "$OUT_DIR"
echo "Backing up Mongo to $OUT_DIR"
mongodump \
  --uri="${MONGO_URL:-mongodb://admin:admin_password@localhost:27017}" \
  --out="$OUT_DIR"
echo "Done: $OUT_DIR"
