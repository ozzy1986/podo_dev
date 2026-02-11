#!/bin/bash
# Run migration 020 on dev: backfill one like from owner for each existing domain.
# Requires migration 019 (votes table) to be applied. Safe to run multiple times (no-op for domains that already have owner vote).
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
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f database/migrations/020_backfill_domain_owner_likes.sql
echo "Migration 020 (backfill domain owner likes) done."
