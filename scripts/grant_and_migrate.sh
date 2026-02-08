#!/bin/bash
set -e
# One-time: grant CREATE to dev user, then run migration 019
sudo -u postgres psql -d domain_mining_dev -c "GRANT CREATE ON SCHEMA public TO domain_user_dev;"
cd /var/www/html/dev.d.onl
export PG_HOST=$(grep '^PG_HOST=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_PORT=$(grep '^PG_PORT=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_DATABASE=$(grep '^PG_DATABASE=' .env | cut -d= -f2- | sed 's/\r$//')
export PG_USER=$(grep '^PG_USER=' .env | cut -d= -f2- | sed 's/\r$//')
export PGPASSWORD=$(grep '^PG_PASSWORD=' .env | cut -d= -f2- | sed 's/\r$//')
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -f database/migrations/019_comments_and_votes.sql
echo "Grant and migration 019 done."
