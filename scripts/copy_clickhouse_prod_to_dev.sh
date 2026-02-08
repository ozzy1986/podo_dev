#!/bin/bash
#
# Copy ClickHouse rewards_log table from production to development.
# Keeps dev database name (domain_mining_dev) and uses dev credentials.
#
# Prerequisites:
#   - clickhouse-client installed (run from WSL, Linux, or Git Bash on Windows)
#   - Network access to prod ClickHouse from the machine running this
#
# Run from project root. Loads CH_* from .env for dev destination.
#
# Usage:
#   PROD_CH_HOST=prod.example.com PROD_CH_DATABASE=domain_mining PROD_CH_USER=default PROD_CH_PASSWORD=secret \
#   ./scripts/copy_clickhouse_prod_to_dev.sh
#
# Or set variables in .env.prod.clickhouse (gitignored) and source it.

set -e

# Load PROD_CH_* and CH_* from .env if present (strip CRLF from .env)
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -E '^(PROD_CH_|CH_)' .env | grep -v '^#' | sed 's/\r$//' | xargs)
fi

# Trim whitespace and carriage returns from vars
trim() { echo "$1" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }

# === PRODUCTION (source) - from .env or environment ===
PROD_CH_HOST=$(trim "${PROD_CH_HOST:-}")
PROD_CH_PORT=$(trim "${PROD_CH_PORT:-9000}")
PROD_CH_DATABASE=$(trim "${PROD_CH_DATABASE:-domain_mining}")
PROD_CH_USER=$(trim "${PROD_CH_USER:-default}")
PROD_CH_PASSWORD=$(trim "${PROD_CH_PASSWORD:-}")

# === DEVELOPMENT (destination) - from .env or defaults ===
DEV_CH_HOST=$(trim "${CH_HOST:-localhost}")
DEV_CH_PORT=$(trim "${CH_PORT:-9000}")
DEV_CH_DATABASE=$(trim "${CH_DATABASE:-domain_mining_dev}")
DEV_CH_USER=$(trim "${CH_USER:-domain_user_dev}")
DEV_CH_PASSWORD=$(trim "${CH_PASSWORD:-}")

# Ensure port is numeric (reset if contains invalid chars)
[[ ! "$PROD_CH_PORT" =~ ^[0-9]+$ ]] && PROD_CH_PORT=9000
[[ ! "$DEV_CH_PORT" =~ ^[0-9]+$ ]] && DEV_CH_PORT=9000

TMP_DIR="/tmp/clickhouse_copy_$$"
mkdir -p "$TMP_DIR"
trap "rm -rf $TMP_DIR" EXIT

# Build connection strings for clickhouse-client
build_prod_opts() {
  local opts="--host ${PROD_CH_HOST} --port ${PROD_CH_PORT} --database ${PROD_CH_DATABASE}"
  [ -n "$PROD_CH_USER" ] && opts="$opts -u $PROD_CH_USER"
  [ -n "$PROD_CH_PASSWORD" ] && opts="$opts --password $PROD_CH_PASSWORD"
  echo "$opts"
}

build_dev_opts() {
  local opts="--host ${DEV_CH_HOST} --port ${DEV_CH_PORT}"
  [ -n "$DEV_CH_USER" ] && opts="$opts -u $DEV_CH_USER"
  [ -n "$DEV_CH_PASSWORD" ] && opts="$opts --password $DEV_CH_PASSWORD"
  echo "$opts"
}

PROD_OPTS=$(build_prod_opts)
DEV_OPTS=$(build_dev_opts)

if [ -z "$PROD_CH_HOST" ]; then
  echo "Error: PROD_CH_HOST is required."
  echo "Example: PROD_CH_HOST=prod.example.com PROD_CH_DATABASE=domain_mining PROD_CH_PASSWORD=xxx $0"
  exit 1
fi

echo "=== Copying ClickHouse rewards_log from prod to dev ==="
echo "Source: $PROD_CH_HOST:$PROD_CH_PORT / $PROD_CH_DATABASE"
echo "Target: $DEV_CH_HOST:$DEV_CH_PORT / $DEV_CH_DATABASE"
echo ""

# Step 1: Get CREATE TABLE from prod (TabSeparated = single line, no Pretty formatting)
echo "1. Fetching table schema from production..."
clickhouse-client $PROD_OPTS -q "SHOW CREATE TABLE rewards_log FORMAT TabSeparated" > "$TMP_DIR/create.sql"

# Step 2: Rewrite DDL to use dev database and fix line endings
# SHOW CREATE may output "CREATE TABLE db.rewards_log" or "CREATE TABLE rewards_log"
sed -i.bak -E "s|CREATE TABLE [a-zA-Z0-9_]*\.?rewards_log|CREATE TABLE ${DEV_CH_DATABASE}.rewards_log|g" "$TMP_DIR/create.sql"
sed -i 's/\r$//' "$TMP_DIR/create.sql"

# Step 3: Ensure dev database exists and create table
echo "2. Creating database and table on dev..."
clickhouse-client $DEV_OPTS -q "CREATE DATABASE IF NOT EXISTS ${DEV_CH_DATABASE}"
clickhouse-client $DEV_OPTS -q "DROP TABLE IF EXISTS ${DEV_CH_DATABASE}.rewards_log"
# TabSeparated escapes newlines as literal \n - convert to real newlines for clickhouse-client
tr -d '\r' < "$TMP_DIR/create.sql" | sed 's/\\n/\n/g' > "$TMP_DIR/create_clean.sql"
clickhouse-client $DEV_OPTS < "$TMP_DIR/create_clean.sql"

# Step 4 & 5: Export from prod and import to dev in batches by ID (avoids memory limit)
# SELECT * on full table spikes memory; batching by id keeps each query small
BATCH_SIZE=50000
echo "3. Exporting and importing data in batches of $BATCH_SIZE..."
RANGE=$(clickhouse-client $PROD_OPTS -q "SELECT min(id), max(id) FROM rewards_log" 2>/dev/null || echo "")
if [ -n "$RANGE" ] && [ "$RANGE" != "0\t0" ]; then
  MIN_ID=$(echo "$RANGE" | cut -f1)
  MAX_ID=$(echo "$RANGE" | cut -f2)
  CURRENT=$MIN_ID
  IMPORTED=0
  while [ "$CURRENT" -le "$MAX_ID" ]; do
    NEXT=$((CURRENT + BATCH_SIZE))
    clickhouse-client $PROD_OPTS -q "SELECT * FROM rewards_log WHERE id >= $CURRENT AND id < $NEXT ORDER BY id FORMAT TabSeparated" 2>/dev/null | \
      clickhouse-client $DEV_OPTS -q "INSERT INTO ${DEV_CH_DATABASE}.rewards_log FORMAT TabSeparated" 2>/dev/null
    IMPORTED=$((IMPORTED + BATCH_SIZE))
    echo "   Progress: id up to $((NEXT-1))..."
    CURRENT=$NEXT
  done
  FINAL_COUNT=$(clickhouse-client $DEV_OPTS -q "SELECT count() FROM ${DEV_CH_DATABASE}.rewards_log" 2>/dev/null || echo "?")
  echo "   Done. Total rows in table: $FINAL_COUNT"
else
  echo "   No data to import (empty table on prod)."
fi

echo ""
echo "Done. rewards_log is now in ${DEV_CH_DATABASE} on ${DEV_CH_HOST}."
