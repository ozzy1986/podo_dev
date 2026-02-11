#!/bin/bash
# Run migration 022 as postgres (required: only postgres can ALTER TABLE users).
# You will be prompted for sudo password and, if configured, postgres DB password.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."
sudo -u postgres psql -d domain_mining_dev -f database/migrations/022_wallet_comment_domain_karma.sql
echo "Migration 022 (wallet comment/domain karma) done."
