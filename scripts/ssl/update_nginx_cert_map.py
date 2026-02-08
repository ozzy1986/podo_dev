#!/usr/bin/env python3
"""
Update nginx configuration with server blocks for domains that have SSL certificates.
This script reads the ssl_certificates table and creates/updates server blocks in nginx config.
"""

import os
import sys
import re
from pathlib import Path

# Add project root to path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _project_root)

try:
    from dotenv import load_dotenv
    env_file = os.path.join(_project_root, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
except ImportError:
    pass  # .env optional if DB credentials come from environment

from database.db_pg import get_db_pg

NGINX_CONFIG = Path('/etc/nginx/sites-available/d.onl')
NGINX_CONFIG_LOCAL = Path(_project_root) / 'd.onl'

def get_domains_with_certificates():
    """Get all domains that have active SSL certificates."""
    db = get_db_pg()
    try:
        with db.get_cursor() as (cursor, conn):
            query = """
                SELECT DISTINCT domain
                FROM ssl_certificates
                WHERE status = 'active'
                ORDER BY domain
            """
            cursor.execute(query)
            return [row['domain'] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting domains: {e}")
        return []

def generate_server_block(domain, punycode_domain=None):
    """Generate nginx server block for a domain with SSL certificate. Includes www for apex domains."""
    server_name = punycode_domain if punycode_domain else domain
    cert_name = punycode_domain if punycode_domain else domain
    # One block for both apex and www (cert is issued for both)
    if not server_name.startswith('www.'):
        server_name_line = f"{server_name} www.{server_name}"
    else:
        server_name_line = server_name
    
    return f"""# {domain}
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {server_name_line};

    ssl_certificate /etc/letsencrypt/live/{cert_name}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{cert_name}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    root /var/www/html/d.onl;
    autoindex off;

    # Proxy to parking handler (super parking or redirect to d.onl)
    # Timeouts must match default server block in d.onl
    location / {{
        proxy_pass http://127.0.0.1:8999;
        proxy_set_header Host $host;
        proxy_set_header X-Original-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }}
}}"""

def update_nginx_config(config_path, domains):
    """Update nginx config with server blocks for domains."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return False
    
    # Find the section between "# HTTPS server - user domains" and "# Default HTTPS server"
    pattern = r'(# HTTPS server - user domains.*?)(# Default HTTPS server)'
    
    # Build server blocks for all domains
    server_blocks = []
    for domain in domains:
        # Convert IDN to Punycode if needed
        try:
            import idna
            if domain.encode('ascii', errors='ignore').decode('ascii') != domain:
                punycode_domain = idna.encode(domain).decode('ascii')
                server_blocks.append(generate_server_block(domain, punycode_domain))
            else:
                server_blocks.append(generate_server_block(domain))
        except ImportError:
            server_blocks.append(generate_server_block(domain))
    
    # Generate replacement text
    replacement = '# HTTPS server - user domains with SSL certificates\n'
    replacement += '# Each domain with certificate gets its own server block\n'
    replacement += '# This is automatically updated by scripts/ssl/update_nginx_cert_map.py\n\n'
    replacement += '\n\n'.join(server_blocks)
    replacement += '\n\n# Default HTTPS server'
    
    # Replace the section
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    else:
        print("Could not find HTTPS server section to update")
        return False
    
    # Write updated config
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated nginx config: {config_path}")
        print(f"Added {len(domains)} server blocks for domains with certificates")
        return True
    except PermissionError:
        print(f"Permission denied writing to {config_path}")
        print("You may need to run with sudo or update the local config file")
        return False

def main():
    """Main function."""
    domains = get_domains_with_certificates()
    print(f"Found {len(domains)} domains with SSL certificates")
    
    # Update local config file
    if update_nginx_config(NGINX_CONFIG_LOCAL, domains):
        print(f"\n✓ Updated local config: {NGINX_CONFIG_LOCAL}")
        print(f"To apply changes:")
        print(f"  sudo cp {NGINX_CONFIG_LOCAL} {NGINX_CONFIG}")
        print(f"  sudo nginx -t")
        print(f"  sudo systemctl reload nginx")
    
    # Try to update system config if we have permissions
    if os.access(NGINX_CONFIG, os.W_OK):
        if update_nginx_config(NGINX_CONFIG, domains):
            print(f"\n✓ Updated system config: {NGINX_CONFIG}")
            print("Run: sudo nginx -t && sudo systemctl reload nginx")

if __name__ == '__main__':
    main()
