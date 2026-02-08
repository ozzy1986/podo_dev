sudo -u postgres psql -d domain_mining_dev -c "GRANT CREATE ON SCHEMA public TO domain_user_dev;"
cd /var/www/html/dev.d.onl && sed -i 's/\r$//' scripts/run_migration_019.sh && bash scripts/run_migration_019.sh
