#!/bin/bash
# Run migration 022 on dev: users.comment_karma, domain_karma + triggers.
# Requires migrations 019 and 021. Safe to run multiple times (idempotent).
# If you get "must be owner of table users", run as postgres: bash scripts/run_migration_022_postgres.sh
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
if ! psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f database/migrations/022_wallet_comment_domain_karma.sql 2>&1; then
  echo "If the error was 'must be owner of table users', run: bash scripts/run_migration_022_postgres.sh"
  exit 1
fi
echo "Migration 022 (wallet comment/domain karma) done."
