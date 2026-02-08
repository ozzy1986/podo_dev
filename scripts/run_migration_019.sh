#!/bin/bash
# Run migration 019 on dev. Load .env and strip CR from values (Windows-edited .env).
# If you get "permission denied for schema public", run once as postgres:
#   sudo -u postgres psql -d domain_mining_dev -c "GRANT CREATE ON SCHEMA public TO domain_user_dev;"
#   sudo -u postgres psql -d domain_mining_dev -f database/migrations/019_comments_and_votes.sql
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."
if [ ! -f .env ]; then
  echo "No .env found"
  exit 1
fi
export PG_HOST=$(grep '^PG_HOST=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_PORT=$(grep '^PG_PORT=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_DATABASE=$(grep '^PG_DATABASE=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_USER=$(grep '^PG_USER=' .env | cut -d= -f2- | sed 's/\r$//')
export PGPASSWORD=$(grep '^PG_PASSWORD=' .env | cut -d= -f2- | sed 's/\r$//')
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f database/migrations/019_comments_and_votes.sql
echo "Migration 019 done."
