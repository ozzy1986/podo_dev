#!/bin/bash
cd /var/www/html/dev.d.onl
. .env 2>/dev/null || true
export PGPASSWORD
psql -h "${PG_HOST:-localhost}" -p "${PG_PORT:-5432}" -U "$PG_USER" -d "$PG_DATABASE" -t -A -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('comments','votes');"
