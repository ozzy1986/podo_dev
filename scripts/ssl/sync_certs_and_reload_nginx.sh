#!/bin/bash
# Sync certs from /tmp/certbot-* and ~/.certbot to /etc/letsencrypt, update nginx map, reload nginx.
# Run as root (e.g. from cron). Usage: sudo bash scripts/ssl/sync_certs_and_reload_nginx.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${LOG_FILE:-/var/log/d.onl-ssl-sync.log}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

log "SSL sync start"

# 1. Copy certs to /etc/letsencrypt/live
if ! bash "$SCRIPT_DIR/copy_certificates_to_standard_location.sh" >> "$LOG_FILE" 2>&1; then
    log "WARN: copy_certificates_to_standard_location.sh had errors (check if any cert dirs exist)"
fi

# 2. Update nginx config: run as ubuntu with venv (so dotenv and DB work)
PROJECT_USER="${SUDO_USER:-ubuntu}"
UPDATE_CMD="cd '$PROJECT_ROOT' && [ -f venv/bin/activate ] && . venv/bin/activate; export PYTHONPATH='$PROJECT_ROOT'; python3 scripts/ssl/update_nginx_cert_map.py"
if [ -n "$PROJECT_USER" ] && [ "$PROJECT_USER" != "root" ]; then
    if command -v sudo >/dev/null 2>&1; then
        sudo -u "$PROJECT_USER" bash -c "$UPDATE_CMD" >> "$LOG_FILE" 2>&1 || true
    else
        su "$PROJECT_USER" -s /bin/bash -c "$UPDATE_CMD" >> "$LOG_FILE" 2>&1 || true
    fi
    log "update_nginx_cert_map.py done"
fi

# 3. Deploy config and reload nginx
if [ -f "$PROJECT_ROOT/d.onl" ]; then
    cp "$PROJECT_ROOT/d.onl" /etc/nginx/sites-available/d.onl 2>/dev/null || true
fi
if nginx -t >> "$LOG_FILE" 2>&1; then
    systemctl reload nginx 2>/dev/null && log "nginx reloaded" || log "WARN: nginx reload failed"
else
    log "WARN: nginx -t failed, not reloading"
fi

log "SSL sync end"
