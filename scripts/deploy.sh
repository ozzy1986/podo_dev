#!/bin/bash
# =============================================================================
# d.onl Production Deployment Script
# =============================================================================
# Usage:
#   ./scripts/deploy.sh              # Full deployment
#   ./scripts/deploy.sh --skip-db    # Skip database migrations
#   ./scripts/deploy.sh --rollback   # Rollback to previous version
#
# Prerequisites:
#   - SSH access to production server
#   - PostgreSQL and ClickHouse running
#   - Nginx installed
#   - Python 3.11+ with venv
# =============================================================================

set -euo pipefail

# Configuration
DEPLOY_DIR="/var/www/html/d.onl"
BACKUP_DIR="/var/www/html/d.onl.backup.$(date +%Y%m%d_%H%M%S)"
SERVICE_NAME="donl-api"
NGINX_CONF="nginx-prod.conf"
SYSTEMD_SERVICE="donl-api.service"
VENV_DIR="${DEPLOY_DIR}/venv"
LOG_DIR="${DEPLOY_DIR}/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
SKIP_DB=false
ROLLBACK=false
for arg in "$@"; do
    case $arg in
        --skip-db)   SKIP_DB=true ;;
        --rollback)  ROLLBACK=true ;;
    esac
done

# =============================================================================
# Rollback
# =============================================================================
if [ "$ROLLBACK" = true ]; then
    log_info "Rolling back to previous version..."
    LATEST_BACKUP=$(ls -td /var/www/html/d.onl.backup.* 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "No backup found to rollback to"
        exit 1
    fi
    log_info "Found backup: $LATEST_BACKUP"
    sudo systemctl stop $SERVICE_NAME
    rm -rf "$DEPLOY_DIR"
    mv "$LATEST_BACKUP" "$DEPLOY_DIR"
    sudo systemctl start $SERVICE_NAME
    log_info "Rollback complete"
    exit 0
fi

# =============================================================================
# Pre-flight checks
# =============================================================================
log_info "Running pre-flight checks..."

# Check .env exists
if [ ! -f "${DEPLOY_DIR}/.env" ]; then
    log_error ".env file not found at ${DEPLOY_DIR}/.env"
    log_info "Copy .env.example to .env and configure it first"
    exit 1
fi

# Check PostgreSQL is running
if ! pg_isready -q 2>/dev/null; then
    log_error "PostgreSQL is not running"
    exit 1
fi
log_info "PostgreSQL: OK"

# Check ClickHouse is running
if ! clickhouse-client --query "SELECT 1" >/dev/null 2>&1; then
    log_warn "ClickHouse is not responding (optional for initial deploy)"
fi

# =============================================================================
# Step 1: Backup current deployment
# =============================================================================
if [ -d "$DEPLOY_DIR" ]; then
    log_info "Backing up current deployment to $BACKUP_DIR..."
    cp -a "$DEPLOY_DIR" "$BACKUP_DIR"
fi

# =============================================================================
# Step 2: Update code
# =============================================================================
log_info "Syncing code to deployment directory..."
rsync -av --delete \
    --exclude='.env' \
    --exclude='venv/' \
    --exclude='logs/' \
    --exclude='__pycache__/' \
    --exclude='.git/' \
    --exclude='*.pyc' \
    ./ "$DEPLOY_DIR/"

# =============================================================================
# Step 3: Setup virtual environment and install dependencies
# =============================================================================
log_info "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip wheel
pip install -r "${DEPLOY_DIR}/requirements.txt"

# =============================================================================
# Step 4: Run database migrations
# =============================================================================
if [ "$SKIP_DB" = false ]; then
    log_info "Running database migrations..."
    MIGRATIONS_DIR="${DEPLOY_DIR}/database/migrations"

    # Run PostgreSQL migrations in order
    for sql_file in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | grep -v clickhouse | sort); do
        log_info "  Applying: $(basename $sql_file)"
        psql -U domain_user -d domain_mining -f "$sql_file" 2>&1 || {
            log_warn "  Migration $(basename $sql_file) had errors (may already be applied)"
        }
    done

    # Run ClickHouse migration
    CH_MIGRATION="${MIGRATIONS_DIR}/018_clickhouse_optimized_schema.sql"
    if [ -f "$CH_MIGRATION" ]; then
        log_info "  Applying ClickHouse schema..."
        clickhouse-client --multiquery < "$CH_MIGRATION" 2>&1 || {
            log_warn "  ClickHouse migration had errors (tables may already exist)"
        }
    fi
else
    log_info "Skipping database migrations (--skip-db)"
fi

# =============================================================================
# Step 5: Create log directory
# =============================================================================
mkdir -p "$LOG_DIR"
chown -R ubuntu:www-data "$LOG_DIR"

# =============================================================================
# Step 6: Install and enable systemd service
# =============================================================================
log_info "Installing systemd service..."
sudo cp "${DEPLOY_DIR}/${SYSTEMD_SERVICE}" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# =============================================================================
# Step 7: Install nginx config
# =============================================================================
log_info "Installing nginx configuration..."
sudo cp "${DEPLOY_DIR}/${NGINX_CONF}" "/etc/nginx/sites-available/d.onl"
sudo ln -sf "/etc/nginx/sites-available/d.onl" "/etc/nginx/sites-enabled/d.onl"
sudo nginx -t || {
    log_error "Nginx config test failed!"
    exit 1
}
sudo systemctl reload nginx

# =============================================================================
# Step 8: Restart application
# =============================================================================
log_info "Restarting application..."
sudo systemctl restart "$SERVICE_NAME"
sleep 3

# =============================================================================
# Step 9: Health check
# =============================================================================
log_info "Running health checks..."

MAX_RETRIES=10
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        log_info "Health check: PASSED (HTTP 200)"
        break
    fi
    RETRY=$((RETRY + 1))
    log_warn "Health check attempt $RETRY/$MAX_RETRIES (HTTP $HTTP_CODE)..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    log_error "Health check FAILED after $MAX_RETRIES attempts!"
    log_error "Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
    log_error "Rolling back..."
    sudo systemctl stop "$SERVICE_NAME"
    if [ -d "$BACKUP_DIR" ]; then
        rm -rf "$DEPLOY_DIR"
        mv "$BACKUP_DIR" "$DEPLOY_DIR"
        sudo systemctl start "$SERVICE_NAME"
        log_info "Rollback complete"
    fi
    exit 1
fi

# Verify API docs endpoint
API_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/docs 2>/dev/null || echo "000")
if [ "$API_CODE" = "200" ]; then
    log_info "API docs: ACCESSIBLE (HTTP 200)"
else
    log_warn "API docs returned HTTP $API_CODE"
fi

# =============================================================================
# Step 10: Cleanup old backups (keep last 3)
# =============================================================================
log_info "Cleaning up old backups..."
ls -td /var/www/html/d.onl.backup.* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null || true

# =============================================================================
# Done
# =============================================================================
echo ""
log_info "========================================="
log_info "  Deployment complete!"
log_info "========================================="
log_info "Service status: $(sudo systemctl is-active $SERVICE_NAME)"
log_info "Site URL: https://d.onl"
log_info "API docs: https://d.onl/api/docs"
log_info "Logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
