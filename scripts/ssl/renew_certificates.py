#!/usr/bin/env python3
"""
Automatic SSL Certificate Renewal Script
Renews certificates that are expiring within 30 days.
Run via cron daily.
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
# Script is in scripts/ssl/, need to go up 2 levels: .. -> .. -> project_root
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _project_root)

from dotenv import load_dotenv
env_file = os.path.join(_project_root, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)

# Setup logging
# Try to use project logs directory, fallback to console only if fails
logs_dir = os.path.join(_project_root, 'logs')
log_file = os.path.join(logs_dir, 'ssl_certificates.log')

# Ensure logs directory exists
try:
    os.makedirs(logs_dir, exist_ok=True)
    # Try to set permissions if possible
    os.chmod(logs_dir, 0o775)
except (OSError, PermissionError):
    pass  # Ignore errors, will try to write anyway

# Try to create file handler, fallback to console only if fails
handlers = [logging.StreamHandler()]
try:
    file_handler = logging.FileHandler(log_file)
    handlers.append(file_handler)
except (PermissionError, OSError):
    pass  # Will log warning after logger is created

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

# Log warning if file handler failed
if len(handlers) == 1:
    logger.warning(f"Could not create log file {log_file}. Using console only.")

# Import database and certificate manager
try:
    from database.db_pg import get_db_pg
    from scripts.ssl.cert_manager import CertificateManager
    from oracle.verifier import get_verifier
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're running from project root and all dependencies are installed")
    sys.exit(1)


class SSLCertificateRenewer:
    """Handles automatic SSL certificate renewal"""
    
    def __init__(self, use_staging: bool = False, days_before_expiry: int = 30):
        """
        Initialize certificate renewer.
        
        Args:
            use_staging: Use Let's Encrypt staging environment
            days_before_expiry: Renew certificates this many days before expiry
        """
        self.db = get_db_pg()
        self.cert_manager = CertificateManager(use_staging=use_staging)
        self.days_before_expiry = days_before_expiry
        self.use_staging = use_staging
        self.verifier = get_verifier()
        
        logger.info(f"SSL Certificate Renewer initialized (staging={use_staging}, days_before_expiry={days_before_expiry})")
    
    def get_certificates_needing_renewal(self) -> List[Dict[str, Any]]:
        """
        Get certificates that need renewal.
        
        Returns certificates that:
        - Are active
        - Expire within days_before_expiry days
        - Haven't been renewed recently
        - Domain is verified (verified = TRUE)
        - Domain has A-record pointing to our server (a_record_points_to_us = TRUE)
        """
        try:
            with self.db.get_cursor() as (cursor, conn):
                expiry_threshold = datetime.now() + timedelta(days=self.days_before_expiry)
                
                query = """
                    SELECT sc.id, sc.domain_id, sc.domain, sc.cert_path, sc.expires_at,
                           d.verified, d.a_record_points_to_us
                    FROM ssl_certificates sc
                    JOIN domains d ON sc.domain_id = d.id
                    WHERE sc.status = 'active'
                      AND sc.expires_at <= %s
                      AND (sc.last_renewal IS NULL OR sc.last_renewal < NOW() - INTERVAL '1 day')
                      AND d.verified = TRUE
                      AND d.a_record_points_to_us = TRUE
                    ORDER BY sc.expires_at ASC
                """
                cursor.execute(query, (expiry_threshold,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting certificates needing renewal: {e}")
            return []
    
    def update_renewal_status(self, cert_id: int, domain: str, success: bool,
                              cert_info: Dict[str, Any] = None, error_message: str = None):
        """Update certificate renewal status in database."""
        try:
            with self.db.get_cursor() as (cursor, conn):
                if success and cert_info:
                    cursor.execute("""
                        UPDATE ssl_certificates
                        SET expires_at = %s,
                            last_renewal = CURRENT_TIMESTAMP,
                            status = 'active',
                            error_message = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        cert_info.get('expires_at'),
                        cert_id
                    ))
                else:
                    cursor.execute("""
                        UPDATE ssl_certificates
                        SET last_renewal = CURRENT_TIMESTAMP,
                            status = 'error',
                            error_message = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        error_message[:500] if error_message else None,
                        cert_id
                    ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating renewal status for {domain}: {e}")
    
    def process_renewals(self) -> Dict[str, int]:
        """
        Process certificate renewals.
        
        Returns:
            Statistics dict with counts
        """
        stats = {
            'processed': 0,
            'renewed': 0,
            'skipped': 0,
            'errors': 0
        }
        
        certificates = self.get_certificates_needing_renewal()
        logger.info(f"Found {len(certificates)} certificates needing renewal")
        
        for cert_row in certificates:
            cert_id = cert_row['id']
            domain = cert_row['domain']
            stats['processed'] += 1
            
            try:
                # Verify TXT record (domain verification)
                logger.info(f"Checking TXT record for {domain}...")
                txt_verified = self.verifier.dns_verifier.find_donl_record(domain)
                if not txt_verified:
                    logger.warning(f"Skipping {domain}: TXT record verification failed")
                    stats['skipped'] += 1
                    self.update_renewal_status(
                        cert_id, domain, False,
                        error_message="TXT record verification failed"
                    )
                    continue
                
                # Verify A-record points to our server
                logger.info(f"Checking A-record for {domain}...")
                a_record_valid, resolved_ip = self.verifier.dns_verifier.verify_a_record_with_consensus(domain)
                if not a_record_valid:
                    logger.warning(f"Skipping {domain}: A-record does not point to our server (resolved: {resolved_ip})")
                    stats['skipped'] += 1
                    self.update_renewal_status(
                        cert_id, domain, False,
                        error_message=f"A-record does not point to our server (resolved: {resolved_ip})"
                    )
                    continue
                
                # Both checks passed, proceed with renewal
                logger.info(f"Renewing certificate for {domain}...")
                success, error_msg, cert_info = self.cert_manager.renew_certificate(domain)
                
                if success:
                    logger.info(f"✓ Certificate renewed for {domain}")
                    stats['renewed'] += 1
                    self.update_renewal_status(cert_id, domain, True, cert_info)
                else:
                    logger.warning(f"✗ Failed to renew certificate for {domain}: {error_msg}")
                    stats['errors'] += 1
                    self.update_renewal_status(cert_id, domain, False, error_message=error_msg)
                
                # Small delay
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error renewing certificate for {domain}: {e}")
                stats['errors'] += 1
                self.update_renewal_status(
                    cert_id, domain, False,
                    error_message=f"Exception: {str(e)}"
                )
        
        return stats
    
    def run(self):
        """Main execution method."""
        logger.info("=" * 60)
        logger.info("Starting SSL certificate renewal process")
        logger.info(f"Staging mode: {self.use_staging}")
        logger.info(f"Renewing certificates expiring within {self.days_before_expiry} days")
        logger.info("Verifying TXT and A-records before renewal")
        logger.info("=" * 60)
        
        stats = self.process_renewals()
        
        logger.info("=" * 60)
        logger.info("Certificate renewal completed")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Renewed: {stats['renewed']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    if os.getenv('APP_ENV', 'production').strip().lower() == 'development':
        logger.info("APP_ENV=development: SSL renewal skipped. Exiting.")
        return
    use_staging = os.getenv('LETSENCRYPT_STAGING', '0').lower() in ('1', 'true', 'yes')
    days_before_expiry = int(os.getenv('SSL_RENEW_DAYS_BEFORE', '30'))
    
    renewer = SSLCertificateRenewer(use_staging=use_staging, days_before_expiry=days_before_expiry)
    renewer.run()


if __name__ == '__main__':
    main()
