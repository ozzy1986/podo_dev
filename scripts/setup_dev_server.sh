#!/bin/bash
# Setup dev.d.onl on the same VPS: copy files, clone DB, create dev .env.
# Run on VPS from project root: bash /var/www/html/d.onl/scripts/setup_dev_server.sh
# If you see $'\r': command not found, run this one-liner first (no script needed):
#   find /var/www/html/d.onl/scripts -name "*.sh" -exec sed -i 's/\r$//' {} \; && find /var/www/html/d.onl/scripts -name "*.sh" -exec chmod +x {} \;
# Then: bash scripts/setup_dev_server.sh
# Prerequisites: dev.d.onl DNS A record points to this server.
# SSL: run once before or after: sudo certbot certonly -d dev.d.onl --webroot -w /var/www/html/certbot-webroot
# Nginx: after script: sudo cp /var/www/html/d.onl/d.onl.dev /etc/nginx/sites-available/dev.d.onl && sudo ln -sf ../sites-available/dev.d.onl /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
# On dev: no cron jobs and no oracle service (crontab points to d.onl; oracle systemd uses d.onl; scripts exit when APP_ENV=development).

set -e

PROD_ROOT="${PROD_ROOT:-/var/www/html/d.onl}"
DEV_ROOT="/var/www/html/dev.d.onl"
PG_PROD_DB="${PG_DATABASE:-domain_mining}"
PG_DEV_DB="domain_mining_dev"
PG_USER="${PG_USER:-domain_user}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"

if [ ! -d "$PROD_ROOT" ]; then
    echo "Error: PROD_ROOT not found: $PROD_ROOT. Set PROD_ROOT or run from VPS."
    exit 1
fi

# Load prod .env for DB credentials
if [ -f "$PROD_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source <(grep -v '^#' "$PROD_ROOT/.env" | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | sed 's/^/export /')
    set +a
    [ -n "$PG_DATABASE" ] && PG_PROD_DB="$PG_DATABASE"
    [ -n "$PG_USER" ] && PG_USER="$PG_USER"
    [ -n "$PG_HOST" ] && PG_HOST="$PG_HOST"
    [ -n "$PG_PORT" ] && PG_PORT="$PG_PORT"
fi

echo "=== Creating dev directory and copying files ==="
sudo mkdir -p "$DEV_ROOT"
sudo chown "$(whoami):www-data" "$DEV_ROOT" 2>/dev/null || sudo chown "$(whoami):$(whoami)" "$DEV_ROOT"

rsync -a --delete \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='logs' \
    --exclude='.env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.cursor' \
    --exclude='migrations/data_export' \
    "$PROD_ROOT/" "$DEV_ROOT/"

echo "=== Creating PostgreSQL dev database ==="
if sudo -u postgres psql -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$PG_DEV_DB"; then
    echo "Database $PG_DEV_DB already exists. Skipping create. To refresh: drop and re-run this script."
else
    sudo -u postgres psql -c "CREATE DATABASE $PG_DEV_DB OWNER $PG_USER;" 2>/dev/null || {
        echo "Trying with postgres user..."
        sudo -u postgres createuser -s "$PG_USER" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE $PG_DEV_DB OWNER $PG_USER;"
    }
fi

echo "=== Dumping prod DB and restoring into dev ==="
if [ -f "$PROD_ROOT/.env" ]; then
    PG_PASSWORD=$(grep '^PG_PASSWORD=' "$PROD_ROOT/.env" | cut -d= -f2- | tr -d '"' | tr -d "'" | head -1)
    export PGPASSWORD="$PG_PASSWORD"
fi
DUMP_FILE="/tmp/domain_mining_dump_$$.sql"
pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_PROD_DB" --no-owner --no-acl -f "$DUMP_FILE" 2>/dev/null || {
    echo "pg_dump failed. Ensure PG credentials in $PROD_ROOT/.env and that DB is running."
    exit 1
}
echo "Restoring into $PG_DEV_DB (errors may appear for extensions/ownership; data should load)..."
if ! psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DEV_DB" -f "$DUMP_FILE" 2>&1; then
    echo "WARN: psql restore had non-zero exit. Check errors above."
fi
rm -f "$DUMP_FILE"
unset PGPASSWORD
# Verify dev DB has data
DOMAIN_COUNT=$(psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DEV_DB" -t -A -c "SELECT COUNT(*) FROM domains;" 2>/dev/null || echo "0")
echo "Dev DB domains count after restore: $DOMAIN_COUNT"

echo "=== Creating dev .env ==="
DEV_ENV="$DEV_ROOT/.env"
cp "$PROD_ROOT/.env" "$DEV_ENV"
if command -v sed >/dev/null 2>&1; then
    sed -i.bak -e 's/^APP_ENV=.*/APP_ENV=development/' -e 's|^SITE_URL=.*|SITE_URL=https://dev.d.onl|' -e "s/^PG_DATABASE=.*/PG_DATABASE=$PG_DEV_DB/" "$DEV_ENV" 2>/dev/null || \
    sed -i '' -e 's/^APP_ENV=.*/APP_ENV=development/' -e 's|^SITE_URL=.*|SITE_URL=https://dev.d.onl|' -e "s/^PG_DATABASE=.*/PG_DATABASE=$PG_DEV_DB/" "$DEV_ENV" 2>/dev/null || true
fi
grep -q '^APP_ENV=' "$DEV_ENV" || echo "APP_ENV=development" >> "$DEV_ENV"
grep -q '^SITE_URL=' "$DEV_ENV" || echo "SITE_URL=https://dev.d.onl" >> "$DEV_ENV"
grep -q '^PG_DATABASE=' "$DEV_ENV" || echo "PG_DATABASE=$PG_DEV_DB" >> "$DEV_ENV"
rm -f "$DEV_ENV.bak"
# Web server (www-data) must read .env for API/PostgreSQL; allow group read
chmod 640 "$DEV_ENV" 2>/dev/null || true
sudo chown "$(whoami):www-data" "$DEV_ENV" 2>/dev/null || true

echo "=== Dev venv (optional) ==="
if [ ! -d "$DEV_ROOT/venv" ]; then
    python3 -m venv "$DEV_ROOT/venv"
    "$DEV_ROOT/venv/bin/pip" install -q -r "$DEV_ROOT/requirements.txt"
    echo "Dev venv created and dependencies installed."
else
    echo "Dev venv already exists. Skip."
fi

echo ""
echo "=== Done. Next steps ==="
echo "0. After deploy from Windows, fix line endings and permissions: cd $PROD_ROOT && bash scripts/fix_scripts_on_server.sh"
echo "1. SSL (if not yet): sudo certbot certonly -d dev.d.onl --webroot -w /var/www/html/certbot-webroot"
echo "2. Nginx: sudo cp $PROD_ROOT/d.onl.dev /etc/nginx/sites-available/dev.d.onl && sudo ln -sf ../sites-available/dev.d.onl /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx"
echo "3. Do NOT add dev.d.onl to crontab and do NOT start oracle service for dev (only d.onl)."
echo "4. Dev site: https://dev.d.onl (after DNS and nginx)."
echo ""
echo "If dev has no domains: check dev DB and re-copy data from prod:"
echo "  psql -h localhost -U domain_user -d domain_mining_dev -t -A -c \"SELECT COUNT(*) FROM domains;\""
echo "  cd $PROD_ROOT && PGPASSWORD=\$(grep '^PG_PASSWORD=' .env | cut -d= -f2-) pg_dump -h localhost -U domain_user -d domain_mining --no-owner --no-acl | psql -h localhost -U domain_user -d domain_mining_dev"
