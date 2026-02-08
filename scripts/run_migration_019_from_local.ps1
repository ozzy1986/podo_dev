# Run migration 019 on dev server. You will be prompted for sudo password once.
# Usage: .\scripts\run_migration_019_from_local.ps1
# Or: ssh -t donl-dev "sudo -u postgres psql -d domain_mining_dev -c \"GRANT CREATE ON SCHEMA public TO domain_user_dev;\" && cd /var/www/html/dev.d.onl && sed -i 's/\r$//' scripts/run_migration_019.sh && bash scripts/run_migration_019.sh"
$remote = @'
sudo -u postgres psql -d domain_mining_dev -c "GRANT CREATE ON SCHEMA public TO domain_user_dev;" && cd /var/www/html/dev.d.onl && sed -i 's/\r$//' scripts/run_migration_019.sh && bash scripts/run_migration_019.sh
'@
ssh -t donl-dev $remote
