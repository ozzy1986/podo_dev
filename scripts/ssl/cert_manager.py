"""
SSL Certificate Manager for Let's Encrypt
Handles certificate issuance, renewal, and status tracking
"""

import os
import sys
import logging
import socket
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

# Add project root to path
# Script is in scripts/ssl/, need to go up 2 levels: .. -> .. -> project_root
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _project_root)

from dotenv import load_dotenv
env_file = os.path.join(_project_root, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)

logger = logging.getLogger(__name__)

# Import cryptography for certificate parsing (doesn't require acme)
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Cryptography library not available: {e}")
    CRYPTO_AVAILABLE = False
    x509 = None
    default_backend = None

# Try to import certbot as fallback
try:
    from certbot import main as certbot_main
    from certbot import errors as certbot_errors
    CERTBOT_AVAILABLE = True
except ImportError:
    CERTBOT_AVAILABLE = False
    certbot_main = None
    certbot_errors = None

# DNS resolver for checking domain IP
try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    logger.warning("dnspython not available, DNS checks will be limited")


class CertificateManager:
    """Manages SSL certificates via Let's Encrypt ACME API"""
    
    # Let's Encrypt ACME directory URLs
    PRODUCTION_DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"
    STAGING_DIRECTORY = "https://acme-staging-v02.api.letsencrypt.org/directory"
    
    # Rate limits (conservative values)
    MAX_CERTIFICATES_PER_HOUR = 250  # Leave 50 buffer from 300 limit
    MAX_CERTIFICATES_PER_DAY = 5000
    
    # Certificate paths
    CERT_BASE_DIR = Path("/etc/letsencrypt/live")
    CERT_CONFIG_DIR = Path("/etc/letsencrypt")
    
    def __init__(self, use_staging: bool = False, server_ip: Optional[str] = None):
        """
        Initialize certificate manager.
        
        Args:
            use_staging: Use Let's Encrypt staging environment (for testing)
            server_ip: Server IP address to check domain DNS against
        """
        self.use_staging = use_staging
        self.acme_directory = self.STAGING_DIRECTORY if use_staging else self.PRODUCTION_DIRECTORY
        self.server_ip = server_ip or os.getenv('OUR_SERVER_IP', '193.33.170.175')
        
        # Rate limiting tracking
        self._request_times = []
        self._lock = None  # Would use threading.Lock in production
        
        # Certificate storage
        self.cert_base_dir = Path(self.CERT_BASE_DIR)
        self.cert_config_dir = Path(self.CERT_CONFIG_DIR)
        
        # Track custom certbot config dir for user-writable certificates
        self._custom_config_dir = None
        
        logger.info(f"CertificateManager initialized (staging={use_staging}, server_ip={self.server_ip})")
    
    def check_domain_points_to_server(self, domain: str) -> Tuple[bool, Optional[str]]:
        """
        Check if domain DNS A record points to our server IP.
        
        Returns:
            (is_valid, error_message)
        """
        if not DNS_AVAILABLE:
            # Fallback: try socket.gethostbyname
            try:
                resolved_ip = socket.gethostbyname(domain)
                if resolved_ip == self.server_ip:
                    return True, None
                else:
                    return False, f"Domain {domain} points to {resolved_ip}, expected {self.server_ip}"
            except socket.gaierror as e:
                return False, f"DNS resolution failed: {e}"
        
        try:
            # Query A record
            answers = dns.resolver.resolve(domain, 'A')
            for answer in answers:
                if str(answer) == self.server_ip:
                    return True, None
            
            # Check all resolved IPs
            resolved_ips = [str(answer) for answer in answers]
            return False, f"Domain {domain} points to {', '.join(resolved_ips)}, expected {self.server_ip}"
            
        except dns.resolver.NXDOMAIN:
            return False, f"Domain {domain} does not exist"
        except dns.resolver.NoAnswer:
            return False, f"Domain {domain} has no A record"
        except Exception as e:
            return False, f"DNS check failed: {str(e)}"
    
    def _check_domain_points_to_server_for_issue(self, domain: str) -> Tuple[bool, Optional[str]]:
        """
        Check A-record using same consensus resolvers as verifier, so that
        when verification already passed we do not fail due to server's stale resolver.
        Falls back to single-resolver check if verifier is unavailable.
        Returns:
            (is_valid, error_message)
        """
        try:
            from oracle.verifier import get_verifier
            verifier = get_verifier()
            points_to_us, resolved_ip = verifier.dns_verifier.verify_a_record_with_consensus(domain)
            if points_to_us:
                logger.debug(f"CertificateManager: A-record check via verifier consensus for {domain}: OK ({resolved_ip})")
                return True, None
            return False, (
                f"Domain {domain} points to {resolved_ip or 'unknown'}, expected {self.server_ip}"
            )
        except ImportError as e:
            logger.debug(f"Verifier not available for cert DNS check, using built-in: {e}")
        except Exception as e:
            logger.warning(f"Verifier A-record check failed for {domain}, falling back to built-in: {e}")
        return self.check_domain_points_to_server(domain)
    
    def get_certificate_paths(self, domain: str) -> Dict[str, Path]:
        """Get paths for certificate files for a domain."""
        domain_dir = self.cert_base_dir / domain
        return {
            'directory': domain_dir,
            'fullchain': domain_dir / 'fullchain.pem',
            'privkey': domain_dir / 'privkey.pem',
            'cert': domain_dir / 'cert.pem',
            'chain': domain_dir / 'chain.pem',
        }
    
    def certificate_exists(self, domain: str) -> bool:
        """Check if certificate files exist for domain."""
        paths = self.get_certificate_paths(domain)
        try:
            return paths['fullchain'].exists() and paths['privkey'].exists()
        except PermissionError:
            # If we don't have permission to check /etc/letsencrypt/, assume cert doesn't exist
            # This can happen when running as non-root user
            logger.debug(f"Permission denied checking certificate for {domain}, assuming it doesn't exist")
            return False
    
    def get_certificate_expiry(self, domain: str) -> Optional[datetime]:
        """Get certificate expiration date."""
        paths = self.get_certificate_paths(domain)
        if not paths['cert'].exists():
            return None
        
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography library not available, cannot read certificate expiry")
            return None
        
        try:
            with open(paths['cert'], 'rb') as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                return cert.not_valid_after_utc.replace(tzinfo=None)
        except PermissionError:
            logger.debug(f"Permission denied reading certificate for {domain}")
            return None
        except Exception as e:
            logger.error(f"Error reading certificate expiry for {domain}: {e}")
            return None
    
    def is_certificate_valid(self, domain: str, min_days_remaining: int = 30) -> bool:
        """
        Check if certificate exists and is valid (not expiring soon).
        
        Args:
            domain: Domain name
            min_days_remaining: Minimum days before expiry to consider valid
        """
        if not self.certificate_exists(domain):
            return False
        
        expiry = self.get_certificate_expiry(domain)
        if not expiry:
            return False
        
        days_remaining = (expiry - datetime.now()).days
        return days_remaining >= min_days_remaining
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we can make another certificate request (rate limiting).
        Returns True if allowed, False if should wait.
        """
        now = time.time()
        hour_ago = now - 3600
        
        # Remove requests older than 1 hour
        self._request_times = [t for t in self._request_times if t > hour_ago]
        
        if len(self._request_times) >= self.MAX_CERTIFICATES_PER_HOUR:
            return False
        
        return True
    
    def _record_request(self):
        """Record a certificate request for rate limiting."""
        self._request_times.append(time.time())
    
    def _parse_certbot_saved_path(self, stdout: str) -> Optional[Dict[str, Path]]:
        """Parse 'Certificate is saved at: .../fullchain.pem' from certbot stdout (certbot may use e.g. domain-0004)."""
        import re
        m = re.search(r'Certificate is saved at:\s*(\S+/fullchain\.pem)', stdout)
        if not m:
            return None
        fullchain = Path(m.group(1).strip())
        if not fullchain.exists():
            return None
        directory = fullchain.parent
        privkey = directory / 'privkey.pem'
        if not privkey.exists():
            return None
        return {
            'directory': directory,
            'fullchain': fullchain,
            'privkey': privkey,
            'cert': directory / 'cert.pem',
            'chain': directory / 'chain.pem',
        }

    def _find_certbot_cert_after_issue(self, cert_domain: str, domain: str,
                                       fallback_paths: Dict[str, Path]) -> Dict[str, Path]:
        """
        After certbot succeeded, cert may be in a different dir (e.g. snap uses its own paths).
        Search common locations and return cert_paths if found.
        """
        if fallback_paths['fullchain'].exists() and fallback_paths['privkey'].exists():
            return fallback_paths
        search_bases = [
            Path('/etc/letsencrypt'),
            Path('/var/lib/letsencrypt'),
            Path('/var/snap/certbot/common/letsencrypt'),
            Path('/var/snap/certbot/current/letsencrypt'),
            Path('/var/snap/certbot/common'),
            Path('/var/snap/certbot/current'),
        ]
        for base in search_bases:
            if not base.exists():
                continue
            # live/cert_domain/
            for name in (cert_domain, domain):
                live_dir = base / 'live' / name
                fc = live_dir / 'fullchain.pem'
                pk = live_dir / 'privkey.pem'
                if fc.exists() and pk.exists():
                    logger.info(f"Found certificate at {live_dir} (config base: {base})")
                    return {
                        'directory': live_dir,
                        'fullchain': fc,
                        'privkey': pk,
                        'cert': live_dir / 'cert.pem',
                        'chain': live_dir / 'chain.pem',
                    }
            # archive/cert_domain/ fullchainN.pem, privkeyN.pem (take latest N)
            for name in (cert_domain, domain):
                archive_dir = base / 'archive' / name
                if not archive_dir.is_dir():
                    continue
                try:
                    fullchains = sorted(archive_dir.glob('fullchain*.pem'), key=lambda p: p.stat().st_mtime, reverse=True)
                    privkeys = sorted(archive_dir.glob('privkey*.pem'), key=lambda p: p.stat().st_mtime, reverse=True)
                    if fullchains and privkeys and fullchains[0].exists() and privkeys[0].exists():
                        logger.info(f"Found certificate in archive at {archive_dir} (config base: {base})")
                        return {
                            'directory': archive_dir,
                            'fullchain': fullchains[0],
                            'privkey': privkeys[0],
                            'cert': archive_dir / 'cert1.pem' if (archive_dir / 'cert1.pem').exists() else fullchains[0],
                            'chain': archive_dir / 'chain1.pem' if (archive_dir / 'chain1.pem').exists() else fullchains[0],
                        }
                except OSError:
                    continue
        return fallback_paths
    
    def issue_certificate(self, domain: str, webroot_path: str = None,
                          force_reissue: bool = False) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Issue a new SSL certificate for domain using HTTP-01 challenge.
        
        Args:
            domain: Domain name to issue certificate for
            webroot_path: Web root path for HTTP-01 challenge. Default must match nginx
                         (d.onl uses /var/www/html/certbot-webroot for acme-challenge).
            force_reissue: If True, remove existing live+archive for this domain before running
                          certbot so a fresh cert (e.g. with www) is issued instead of reusing old one.
        
        Returns:
            (success, error_message, certificate_info)
        """
        if webroot_path is None:
            webroot_path = os.getenv('CERTBOT_WEBROOT', '/var/www/html/certbot-webroot')
        if not CERTBOT_AVAILABLE:
            return False, "Certbot not available", None
        
        # Check rate limit
        if not self._check_rate_limit():
            wait_time = 3600 - (time.time() - self._request_times[0])
            return False, f"Rate limit exceeded. Wait {int(wait_time)} seconds", None
        
        # Check DNS: use same consensus resolvers as verifier to avoid mismatch
        # (server's default resolver may be stale; verifier uses public DNS)
        dns_valid, dns_error = self._check_domain_points_to_server_for_issue(domain)
        if not dns_valid:
            return False, dns_error, None
        
        # Check if certificate already exists and is valid (skip when force_reissue: we want a fresh cert e.g. with www)
        if not force_reissue and self.is_certificate_valid(domain):
            expiry = self.get_certificate_expiry(domain)
            return True, None, {
                'domain': domain,
                'status': 'exists',
                'expires_at': expiry,
                'cert_path': str(self.get_certificate_paths(domain)['fullchain']),
                'key_path': str(self.get_certificate_paths(domain)['privkey'])
            }
        
        # Use certbot as it's more reliable than raw ACME client
        if CERTBOT_AVAILABLE:
            return self._issue_with_certbot(domain, webroot_path, force_reissue=force_reissue)
        else:
            return False, "Certbot not available", None
    
    def _issue_with_certbot(self, domain: str, webroot_path: str,
                            force_reissue: bool = False) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Issue certificate using certbot command-line tool."""
        import subprocess
        
        try:
            # Convert IDN domain to Punycode for certbot (certbot requires ASCII)
            try:
                import idna
                # Check if domain contains non-ASCII characters
                domain_ascii = domain.encode('ascii', errors='ignore').decode('ascii')
                if domain_ascii != domain:
                    # Contains non-ASCII, convert to Punycode
                    punycode_domain = idna.encode(domain).decode('ascii')
                    logger.info(f"Converting IDN domain {domain} to Punycode: {punycode_domain}")
                    cert_domain = punycode_domain
                else:
                    cert_domain = domain
            except ImportError:
                logger.warning("idna library not available, cannot convert IDN domains")
                cert_domain = domain
            except Exception as e:
                logger.warning(f"Failed to convert IDN domain {domain}: {e}, using as-is")
                cert_domain = domain
            
            # Ensure .well-known directory exists and is writable
            well_known_path = os.path.join(webroot_path, '.well-known')
            acme_challenge_path = os.path.join(well_known_path, 'acme-challenge')
            try:
                os.makedirs(acme_challenge_path, mode=0o755, exist_ok=True)
                # Try to set permissions if possible
                try:
                    os.chmod(well_known_path, 0o755)
                    os.chmod(acme_challenge_path, 0o755)
                except (OSError, PermissionError):
                    pass  # Ignore if we can't change permissions
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot create .well-known directory at {acme_challenge_path}: {e}")
                # Try alternative paths. Prefer /tmp first when running as non-root (e.g. www-data)
                # since /var/www/html/certbot-webroot is often not writable by CGI user.
                alternative_paths = [
                    '/tmp/certbot-webroot',  # Writable by any user, nginx can read (see d.onl)
                    '/var/www/html/certbot-webroot',  # Standard location if writable
                ]
                
                webroot_path = None
                for alt_path in alternative_paths:
                    acme_challenge_path = os.path.join(alt_path, '.well-known', 'acme-challenge')
                    try:
                        os.makedirs(acme_challenge_path, mode=0o755, exist_ok=True)
                        # Test if we can write a file
                        test_file = os.path.join(acme_challenge_path, '.test_write')
                        try:
                            with open(test_file, 'w') as f:
                                f.write('test')
                            os.remove(test_file)
                            webroot_path = alt_path
                            logger.info(f"Using alternative webroot path: {webroot_path}")
                            break
                        except (OSError, PermissionError):
                            continue
                    except (OSError, PermissionError):
                        continue
                
                if not webroot_path:
                    # Last resort: use user home (but nginx won't be able to read it without proper permissions)
                    user_home = os.path.expanduser('~')
                    webroot_path = os.path.join(user_home, 'certbot-webroot')
                    acme_challenge_path = os.path.join(webroot_path, '.well-known', 'acme-challenge')
                    os.makedirs(acme_challenge_path, mode=0o755, exist_ok=True)
                    logger.warning(f"Using user home webroot path: {webroot_path}")
                    logger.warning("WARNING: nginx may not be able to read files from this path!")
                    logger.warning("Please run: sudo chmod -R 755 {0} && sudo chown -R ubuntu:www-data {0}".format(webroot_path))
            
            # Get writable directories for certbot (if not running as root)
            config_dir = os.getenv('CERTBOT_CONFIG_DIR', '/etc/letsencrypt')
            work_dir = os.getenv('CERTBOT_WORK_DIR', '/var/lib/letsencrypt')
            logs_dir = os.getenv('CERTBOT_LOGS_DIR', '/var/log/letsencrypt')
            
            # Check if we can write to default directories
            can_write_config = os.access(config_dir, os.W_OK) if os.path.exists(config_dir) else False
            can_write_work = os.access(work_dir, os.W_OK) if os.path.exists(work_dir) else False
            can_write_logs = os.access(logs_dir, os.W_OK) if os.path.exists(logs_dir) else False
            
            # If we can't write to default dirs, use writable alternatives.
            # Prefer /tmp/certbot-{uid} because ~ (e.g. /var/www for www-data) is often not writable when running as CGI.
            if not (can_write_config and can_write_work and can_write_logs):
                uid = getattr(os, 'getuid', lambda: 0)()
                tmp_certbot_base = os.path.join('/tmp', f'certbot-{uid}')
                try:
                    os.makedirs(tmp_certbot_base, mode=0o700, exist_ok=True)
                    user_certbot_dir = tmp_certbot_base
                except (OSError, PermissionError):
                    user_home = os.path.expanduser('~')
                    user_certbot_dir = os.path.join(user_home, '.certbot')
                config_dir = os.path.join(user_certbot_dir, 'config')
                work_dir = os.path.join(user_certbot_dir, 'work')
                logs_dir = os.path.join(user_certbot_dir, 'logs')
                os.makedirs(config_dir, mode=0o755, exist_ok=True)
                os.makedirs(work_dir, mode=0o755, exist_ok=True)
                os.makedirs(logs_dir, mode=0o755, exist_ok=True)
                logger.info(f"Using writable certbot directories: {user_certbot_dir}")
            
            # Request both apex and www for apex domains so one cert covers both
            domains_for_cert = [cert_domain]
            if not cert_domain.startswith('www.'):
                www_domain = 'www.' + cert_domain
                domains_for_cert.append(www_domain)
            # Force fresh issuance when re-issuing (e.g. to add www): remove existing live+archive
            # in both default config_dir and snap paths (snap certbot may ignore --config-dir)
            if force_reissue and len(domains_for_cert) >= 2:
                dirs_to_remove = [Path(config_dir) / subdir / cert_domain for subdir in ('live', 'archive')]
                for snap_base in (Path('/var/snap/certbot/common'), Path('/var/snap/certbot/current')):
                    if snap_base.exists():
                        for subdir in ('live', 'archive'):
                            p = (snap_base / 'letsencrypt' / subdir / cert_domain) if (snap_base / 'letsencrypt').exists() else (snap_base / subdir / cert_domain)
                            if p not in dirs_to_remove:
                                dirs_to_remove.append(p)
                for old_dir in dirs_to_remove:
                    if old_dir.exists():
                        try:
                            import shutil
                            shutil.rmtree(old_dir)
                            logger.info(f"Removed existing {old_dir} for fresh issuance with www")
                        except (OSError, PermissionError):
                            try:
                                subprocess.run(['sudo', 'rm', '-rf', str(old_dir)], check=False, capture_output=True)
                                logger.info(f"Removed existing {old_dir} for fresh issuance with www")
                            except Exception:
                                pass
            certbot_d_args = []
            for d in domains_for_cert:
                certbot_d_args.extend(['-d', d])
            
            # Prepare certbot command
            cmd = [
                'certbot',
                'certonly',
                '--non-interactive',
                '--agree-tos',
                '--webroot',
                '--webroot-path', webroot_path,
                '--email', os.getenv('LETSENCRYPT_EMAIL', 'admin@d.onl'),
                '--cert-name', cert_domain,
                '--config-dir', config_dir,
                '--work-dir', work_dir,
                '--logs-dir', logs_dir,
            ] + certbot_d_args
            
            if self.use_staging:
                cmd.append('--staging')
            
            # Run certbot (requesting both apex and www in one cert)
            domains_str = ' and '.join(domains_for_cert) if len(domains_for_cert) > 1 else domains_for_cert[0]
            logger.info(f"Issuing certificate for {domains_str}...")
            certbot_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            if certbot_result.returncode != 0:
                logger.warning(f"Certbot stderr: {certbot_result.stderr[:500] if certbot_result.stderr else 'none'}")
                logger.warning(f"Certbot stdout: {certbot_result.stdout[:500] if certbot_result.stdout else 'none'}")
            elif certbot_result.stdout and 'Certificate is saved at' in certbot_result.stdout:
                logger.debug(f"Certbot wrote: {certbot_result.stdout.strip()[:300]}")
            if certbot_result.returncode == 0:
                self._record_request()
                
                # Certbot stores certificates in {config_dir}/live/{domain}/
                # When using user directories, config_dir is different from /etc/letsencrypt
                cert_base = Path(config_dir) / 'live'
                
                # Try to get certificate paths from the actual config_dir used
                cert_domain_dir = cert_base / cert_domain
                cert_paths = {
                    'directory': cert_domain_dir,
                    'fullchain': cert_domain_dir / 'fullchain.pem',
                    'privkey': cert_domain_dir / 'privkey.pem',
                    'cert': cert_domain_dir / 'cert.pem',
                    'chain': cert_domain_dir / 'chain.pem',
                }
                
                # If cert doesn't exist at expected path, try original domain path
                if not cert_paths['fullchain'].exists():
                    domain_dir = cert_base / domain
                    cert_paths = {
                        'directory': domain_dir,
                        'fullchain': domain_dir / 'fullchain.pem',
                        'privkey': domain_dir / 'privkey.pem',
                        'cert': domain_dir / 'cert.pem',
                        'chain': domain_dir / 'chain.pem',
                    }
                # Certbot may use a different cert name (e.g. netfox.ru-0004) when re-issuing — parse stdout
                if (not cert_paths['fullchain'].exists() or not cert_paths['privkey'].exists()) and certbot_result.stdout:
                    parsed = self._parse_certbot_saved_path(certbot_result.stdout)
                    if parsed and parsed['fullchain'].exists() and parsed['privkey'].exists():
                        logger.info(f"Using cert path from certbot output: {parsed['directory']}")
                        cert_paths = parsed
                # If still missing (e.g. snap certbot wrote elsewhere), search common certbot locations
                if not cert_paths['fullchain'].exists() or not cert_paths['privkey'].exists():
                    cert_paths = self._find_certbot_cert_after_issue(cert_domain, domain, cert_paths)
                
                # Get expiry date
                expiry = None
                if cert_paths['cert'].exists():
                    try:
                        if CRYPTO_AVAILABLE:
                            with open(cert_paths['cert'], 'rb') as f:
                                cert_data = f.read()
                                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
                                expiry = cert.not_valid_after_utc.replace(tzinfo=None)
                    except Exception as e:
                        logger.warning(f"Could not read certificate expiry: {e}")
                
                # Try to copy certificates to standard location /etc/letsencrypt/live/ for nginx
                # This allows nginx to find certificates without Lua or dynamic loading
                standard_cert_dir = Path('/etc/letsencrypt/live') / cert_domain
                try:
                    import shutil
                    import subprocess
                    # When running as root, certbot may write to /etc/letsencrypt — skip copy only if files exist there
                    # (snap certbot can write elsewhere and ignore --config-dir, so we must verify)
                    try:
                        src_resolved = cert_paths['fullchain'].resolve()
                        dst_fullchain = (standard_cert_dir / 'fullchain.pem').resolve()
                        paths_same = src_resolved == dst_fullchain or str(src_resolved).startswith(str(standard_cert_dir.resolve()))
                        dest_exists = (standard_cert_dir / 'fullchain.pem').exists() and (standard_cert_dir / 'privkey.pem').exists()
                        already_in_place = paths_same and dest_exists
                    except (OSError, RuntimeError):
                        already_in_place = False
                    if already_in_place:
                        logger.info(f"Certificate already in standard location: {standard_cert_dir}")
                        cert_paths = {
                            'directory': standard_cert_dir,
                            'fullchain': standard_cert_dir / 'fullchain.pem',
                            'privkey': standard_cert_dir / 'privkey.pem',
                            'cert': standard_cert_dir / 'cert.pem',
                            'chain': standard_cert_dir / 'chain.pem',
                        }
                    else:
                        # Try to create directory and copy files using sudo if needed
                        if not standard_cert_dir.exists():
                            try:
                                standard_cert_dir.mkdir(parents=True, exist_ok=True)
                            except (PermissionError, OSError):
                                subprocess.run(['sudo', 'mkdir', '-p', str(standard_cert_dir)], check=False)
                        if cert_paths['fullchain'].exists() and cert_paths['privkey'].exists():
                            try:
                                shutil.copy2(cert_paths['fullchain'], standard_cert_dir / 'fullchain.pem')
                                shutil.copy2(cert_paths['privkey'], standard_cert_dir / 'privkey.pem')
                                if cert_paths['cert'].exists():
                                    shutil.copy2(cert_paths['cert'], standard_cert_dir / 'cert.pem')
                                if cert_paths['chain'].exists():
                                    shutil.copy2(cert_paths['chain'], standard_cert_dir / 'chain.pem')
                                logger.info(f"Copied certificate to standard location: {standard_cert_dir}")
                                cert_paths = {
                                    'directory': standard_cert_dir,
                                    'fullchain': standard_cert_dir / 'fullchain.pem',
                                    'privkey': standard_cert_dir / 'privkey.pem',
                                    'cert': standard_cert_dir / 'cert.pem',
                                    'chain': standard_cert_dir / 'chain.pem',
                                }
                            except (PermissionError, OSError):
                                try:
                                    subprocess.run(['sudo', 'cp', str(cert_paths['fullchain']), str(standard_cert_dir / 'fullchain.pem')], check=True)
                                    subprocess.run(['sudo', 'cp', str(cert_paths['privkey']), str(standard_cert_dir / 'privkey.pem')], check=True)
                                    if cert_paths['cert'].exists():
                                        subprocess.run(['sudo', 'cp', str(cert_paths['cert']), str(standard_cert_dir / 'cert.pem')], check=True)
                                    if cert_paths['chain'].exists():
                                        subprocess.run(['sudo', 'cp', str(cert_paths['chain']), str(standard_cert_dir / 'chain.pem')], check=True)
                                    subprocess.run(['sudo', 'chmod', '644', str(standard_cert_dir / 'fullchain.pem')], check=False)
                                    subprocess.run(['sudo', 'chmod', '600', str(standard_cert_dir / 'privkey.pem')], check=False)
                                    logger.info(f"Copied certificate to standard location using sudo: {standard_cert_dir}")
                                    cert_paths = {
                                        'directory': standard_cert_dir,
                                        'fullchain': standard_cert_dir / 'fullchain.pem',
                                        'privkey': standard_cert_dir / 'privkey.pem',
                                        'cert': standard_cert_dir / 'cert.pem',
                                        'chain': standard_cert_dir / 'chain.pem',
                                    }
                                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                                    logger.warning(f"Could not copy certificate to /etc/letsencrypt/live/ using sudo: {e}")
                                    logger.warning("Certificate saved in user directory. Run as root: sudo bash scripts/ssl/copy_certificates_to_standard_location.sh && sudo systemctl reload nginx")
                except Exception as e:
                    logger.warning(f"Could not copy certificate to /etc/letsencrypt/live/: {e}")
                    logger.warning("Run as root to sync certs for nginx: sudo bash scripts/ssl/copy_certificates_to_standard_location.sh")
                    # Continue with user directory paths
                
                # Try to update nginx configuration with new certificate
                try:
                    update_script = os.path.join(_project_root, 'scripts', 'ssl', 'update_nginx_cert_map.py')
                    if os.path.exists(update_script):
                        import subprocess
                        result = subprocess.run(
                            [sys.executable, update_script],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            logger.info("Nginx configuration updated with new certificate")
                        else:
                            logger.warning(f"Failed to update nginx config: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Could not update nginx config: {e}")

                # Nginx requires cert in /etc/letsencrypt/live/
                if not (standard_cert_dir / 'fullchain.pem').exists() or not (standard_cert_dir / 'privkey.pem').exists():
                    msg = (
                        "Certificate was issued but not found in /etc/letsencrypt/live/. "
                        "Certbot may have written to another path (e.g. snap). "
                        "Install certbot from apt (not snap) so --config-dir is honored, or run: "
                        "sudo bash scripts/ssl/copy_certificates_to_standard_location.sh"
                    )
                    logger.error(msg)
                    if certbot_result.stdout:
                        logger.info(f"Certbot stdout (cert location): {certbot_result.stdout[:600]}")
                    return False, msg, None
                return True, None, {
                    'domain': domain,  # Store original domain name
                    'status': 'issued',
                    'expires_at': expiry,
                    'cert_path': str(cert_paths['fullchain']),
                    'key_path': str(cert_paths['privkey']),
                    'issued_at': datetime.now()
                }
            else:
                error_msg = certbot_result.stderr or certbot_result.stdout or "Unknown error"
                logger.error(f"Certbot failed for {domain}: {error_msg}")
                return False, f"Certbot error: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "Certificate issuance timed out", None
        except Exception as e:
            logger.error(f"Error issuing certificate for {domain}: {e}")
            return False, f"Exception: {str(e)}", None
    
    def renew_certificate(self, domain: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Renew an existing certificate.
        
        Returns:
            (success, error_message, certificate_info)
        """
        if not CERTBOT_AVAILABLE:
            return False, "Certbot not available", None
        
        if not self.certificate_exists(domain):
            return False, "Certificate does not exist", None
        
        import subprocess
        
        try:
            cmd = [
                'certbot',
                'renew',
                '--cert-name', domain,
                '--non-interactive',
                '--quiet'
            ]
            
            if self.use_staging:
                cmd.append('--staging')
            
            logger.info(f"Renewing certificate for {domain}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                expiry = self.get_certificate_expiry(domain)
                paths = self.get_certificate_paths(domain)
                return True, None, {
                    'domain': domain,
                    'status': 'renewed',
                    'expires_at': expiry,
                    'cert_path': str(paths['fullchain']),
                    'key_path': str(paths['privkey']),
                    'renewed_at': datetime.now()
                }
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return False, f"Renewal failed: {error_msg}", None
                
        except Exception as e:
            logger.error(f"Error renewing certificate for {domain}: {e}")
            return False, f"Exception: {str(e)}", None
    
    def get_certificate_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get information about existing certificate."""
        if not self.certificate_exists(domain):
            return None
        
        expiry = self.get_certificate_expiry(domain)
        paths = self.get_certificate_paths(domain)
        
        days_remaining = None
        if expiry:
            days_remaining = (expiry - datetime.now()).days
        
        return {
            'domain': domain,
            'exists': True,
            'expires_at': expiry,
            'days_remaining': days_remaining,
            'cert_path': str(paths['fullchain']),
            'key_path': str(paths['privkey']),
            'is_valid': self.is_certificate_valid(domain)
        }


def get_cert_manager(use_staging: bool = False) -> CertificateManager:
    """Get certificate manager instance."""
    return CertificateManager(use_staging=use_staging)
