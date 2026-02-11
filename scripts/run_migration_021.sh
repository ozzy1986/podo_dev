#!/bin/bash
# Run migration 021 on dev: paid votes (amount, free_like_used, free_dislike_used), karma = SUM(value*amount).
# Requires migration 019 (votes table) to be applied. Safe to run multiple times (idempotent).
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
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f database/migrations/021_paid_votes.sql
echo "Migration 021 (paid votes) done."
