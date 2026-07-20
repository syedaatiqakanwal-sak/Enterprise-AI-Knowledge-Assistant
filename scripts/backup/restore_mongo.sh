#!/usr/bin/env bash
# Restore MongoDB from mongodump directory
set -euo pipefail
DIR="${1:?Usage: $0 <mongodump-dir>}"
mongorestore --uri="${MONGO_URL:-mongodb://admin:admin_password@localhost:27017}" --drop "$DIR"
echo "Mongo restore complete"
