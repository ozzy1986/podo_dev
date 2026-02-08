#!/bin/bash
# Cron wrapper for SSL certificate renewal - activates venv before running Python
# Usage: Add to crontab: 0 3 * * * /var/www/html/d.onl/scripts/run_ssl_renew.sh

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Ensure logs directory exists with correct permissions
LOGS_DIR="$PROJECT_ROOT/logs"
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    chmod 775 "$LOGS_DIR" 2>/dev/null || true
    # Try to set ownership to ubuntu:www-data if sudo is available (non-fatal)
    if command -v sudo >/dev/null 2>&1; then
        sudo chown "$(whoami):www-data" "$LOGS_DIR" 2>/dev/null || true
        sudo chmod g+s "$LOGS_DIR" 2>/dev/null || true
    fi
fi

# Activate venv if it exists
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT"

# Run the Python script
exec python3 "$PROJECT_ROOT/scripts/ssl/renew_certificates.py"
