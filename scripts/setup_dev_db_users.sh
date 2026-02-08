#!/bin/bash
# Create separate PostgreSQL and ClickHouse users for development environment.
# Run on the VPS.
#
# Usage:
#   bash scripts/setup_dev_db_users.sh
#
# After running, update .env with:
#   PG_USER=domain_user_dev
#   PG_PASSWORD=<your_dev_password>
#   CH_USER=domain_user_dev
#   CH_PASSWORD=<your_dev_password>

set -e

echo "Enter a secure password for domain_user_dev (will be used for both PostgreSQL and ClickHouse):"
read -s DEV_DB_PASSWORD
echo
if [ -z "$DEV_DB_PASSWORD" ]; then
    echo "Error: Password cannot be empty"
    exit 1
fi

# Escape single quotes for use in SQL
DEV_PASS_ESC=$(echo "$DEV_DB_PASSWORD" | sed "s/'/''/g")

echo "Creating PostgreSQL user domain_user_dev..."

# Create user if not exists, then set password
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='domain_user_dev'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE USER domain_user_dev WITH PASSWORD '$DEV_PASS_ESC';"
else
    sudo -u postgres psql -c "ALTER USER domain_user_dev WITH PASSWORD '$DEV_PASS_ESC';"
fi

# Create database if not exists
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='domain_mining_dev'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE domain_mining_dev OWNER domain_user_dev;"

# Grant privileges
sudo -u postgres psql -d domain_mining_dev -c "
GRANT CONNECT ON DATABASE domain_mining_dev TO domain_user_dev;
GRANT USAGE ON SCHEMA public TO domain_user_dev;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO domain_user_dev;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO domain_user_dev;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO domain_user_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO domain_user_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO domain_user_dev;
"

echo "PostgreSQL: domain_user_dev ready (database domain_mining_dev)"

echo ""
echo "Creating ClickHouse user domain_user_dev..."
if command -v clickhouse-client >/dev/null 2>&1; then
    clickhouse-client --multiquery << EOF
CREATE USER IF NOT EXISTS domain_user_dev IDENTIFIED BY '$DEV_PASS_ESC';
CREATE DATABASE IF NOT EXISTS domain_mining_dev;
GRANT ALL ON domain_mining_dev.* TO domain_user_dev;
GRANT ALL ON domain_mining_dev TO domain_user_dev;
EOF
    echo "ClickHouse: domain_user_dev ready (database domain_mining_dev)"
else
    echo "ClickHouse not found. Create user manually if needed:"
    echo "  clickhouse-client -q \"CREATE USER IF NOT EXISTS domain_user_dev IDENTIFIED BY 'YOUR_PASSWORD';\""
    echo "  clickhouse-client -q \"CREATE DATABASE IF NOT EXISTS domain_mining_dev;\""
    echo "  clickhouse-client -q \"GRANT ALL ON domain_mining_dev.* TO domain_user_dev;\""
fi

echo ""
echo "Done. Update your .env with:"
echo "  PG_USER=domain_user_dev"
echo "  PG_PASSWORD=<the password you set>"
echo "  PG_DATABASE=domain_mining_dev"
echo "  CH_USER=domain_user_dev"
echo "  CH_PASSWORD=<the password you set>"
echo "  CH_DATABASE=domain_mining_dev"
echo ""
