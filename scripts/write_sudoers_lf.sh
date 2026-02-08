#!/bin/bash
# Writes sudoers_dev_donl_full with Unix (LF) line endings. Run on server.
# Then: sudo cp /var/www/html/dev.d.onl/scripts/sudoers_dev_donl_full /etc/sudoers.d/dev-donl
#       sudo chmod 440 /etc/sudoers.d/dev-donl && sudo visudo -c
set -e
OUT="/var/www/html/dev.d.onl/scripts/sudoers_dev_donl_full"
printf '%s\n' \
  '# Sudoers for dev.d.onl agent (no password).' \
  '' \
  'Cmnd_Alias DEV_JOURNAL = /usr/bin/journalctl -u dev-donl-api *' \
  'Cmnd_Alias DEV_SYSTEMCTL = /usr/bin/systemctl restart dev-donl-api, /usr/bin/systemctl reload nginx, /usr/bin/systemctl is-active dev-donl-api' \
  'Cmnd_Alias DEV_NGINX = /usr/sbin/nginx -t' \
  'Cmnd_Alias DEV_NGINX_CP = /usr/bin/cp /var/www/html/dev.d.onl/nginx-dev.conf /etc/nginx/sites-available/dev.d.onl' \
  'Cmnd_Alias DEV_NGINX_LN = /usr/bin/ln -sf ../sites-available/dev.d.onl /etc/nginx/sites-enabled/dev.d.onl' \
  'Cmnd_Alias DEV_PSQL = /usr/bin/psql *' \
  '' \
  'ubuntu ALL=(ALL) NOPASSWD: DEV_JOURNAL, DEV_SYSTEMCTL, DEV_NGINX, DEV_NGINX_CP, DEV_NGINX_LN' \
  'ubuntu ALL=(postgres) NOPASSWD: DEV_PSQL' \
  > "$OUT"
echo "Written to $OUT (LF only). Run: sudo cp $OUT /etc/sudoers.d/dev-donl && sudo chmod 440 /etc/sudoers.d/dev-donl && sudo visudo -c"
