#!/usr/bin/env python3
"""
Batch SSL certificate issuance for domains that should have a certificate but do not.
Issues certificates for domains that are verified, mining, have A-record pointing to our IP,
and have no certificate or status != 'active' (e.g. previous issuance failed).
Run: python3 scripts/ssl/issue_certificates_batch.py -y   (or use scripts/run_ssl_batch_issue.sh -y)
For nginx to use new certs, run as root or run copy_certificates_to_standard_location.sh + reload nginx after.
"""

import os
import sys
import logging
import time
from datetime import datetime
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
log_file = os.path.join(logs_dir, 'ssl_certificates_batch.log')

# Ensure logs directory exists
try:
    os.makedirs(logs_dir, exist_ok=True)
    # Try to set permissions if possible
    os.chmod(logs_dir, 0o775)
except (OSError, PermissionError) as e:
    pass  # Ignore errors, will try to write anyway

# Try to create file handler, fallback to console only if fails
handlers = [logging.StreamHandler()]
try:
    file_handler = logging.FileHandler(log_file)
    handlers.append(file_handler)
except (PermissionError, OSError) as e:
    # Will log warning after logger is created
    pass

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


class BatchCertificateIssuer:
    """One-time batch certificate issuer for all existing domains"""
    
    def __init__(self, use_staging: bool = False):
        """
        Initialize batch certificate issuer.
        
        Args:
            use_staging: Use Let's Encrypt staging environment
        """
        self.db = get_db_pg()
        self.cert_manager = CertificateManager(use_staging=use_staging)
        self.verifier = get_verifier()
        self.use_staging = use_staging
        
        logger.info(f"Batch Certificate Issuer initialized (staging={use_staging})")
    
    def get_all_eligible_domains(self) -> List[Dict[str, Any]]:
        """
        Get all domains that should have an SSL certificate but do not yet.
        
        Returns domains that:
        - Are verified (verified = TRUE)
        - Are mining (is_mining = TRUE)
        - Have A-record pointing to our server (a_record_points_to_us = TRUE)
        - Have no certificate record OR status is not 'active' (e.g. previous issuance failed)
        """
        try:
            with self.db.get_cursor() as (cursor, conn):
                query = """
                    SELECT d.id, d.domain, d.verified, d.a_record_points_to_us
                    FROM domains d
                    LEFT JOIN ssl_certificates sc ON d.id = sc.domain_id
                    WHERE d.verified = TRUE
                      AND d.is_mining = TRUE
                      AND d.a_record_points_to_us = TRUE
                      AND (sc.id IS NULL OR sc.status != 'active')
                    ORDER BY d.created_at ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting eligible domains: {e}")
            return []
    
    def verify_domain_checks(self, domain: str) -> tuple[bool, str]:
        """
        Verify both TXT and A-record for domain.
        
        Returns:
            (is_valid, error_message)
        """
        # Check TXT record (domain verification)
        try:
            txt_verified = self.verifier.dns_verifier.find_donl_record(domain)
            if not txt_verified:
                return False, "TXT record verification failed"
        except Exception as e:
            logger.warning(f"Error checking TXT record for {domain}: {e}")
            return False, f"TXT record check error: {str(e)}"
        
        # Check A-record points to our server
        try:
            a_record_valid, resolved_ip = self.verifier.dns_verifier.verify_a_record_with_consensus(domain)
            if not a_record_valid:
                return False, f"A-record does not point to our server (resolved: {resolved_ip})"
        except Exception as e:
            logger.warning(f"Error checking A-record for {domain}: {e}")
            return False, f"A-record check error: {str(e)}"
        
        return True, None
    
    def update_certificate_status(self, domain_id: int, domain: str, success: bool, 
                                 cert_info: Dict[str, Any] = None, error_message: str = None):
        """Update certificate status in database."""
        try:
            with self.db.get_cursor() as (cursor, conn):
                if success and cert_info:
                    # Insert or update certificate record
                    cursor.execute("""
                        INSERT INTO ssl_certificates 
                        (domain_id, domain, cert_path, key_path, issued_at, expires_at, status, error_message)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (domain_id) DO UPDATE SET
                            cert_path = EXCLUDED.cert_path,
                            key_path = EXCLUDED.key_path,
                            issued_at = EXCLUDED.issued_at,
                            expires_at = EXCLUDED.expires_at,
                            status = EXCLUDED.status,
                            error_message = NULL,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        domain_id,
                        domain,
                        cert_info.get('cert_path'),
                        cert_info.get('key_path'),
                        cert_info.get('issued_at', datetime.now()),
                        cert_info.get('expires_at'),
                        'active',
                        None
                    ))
                else:
                    # Update with error (cert_path and key_path can be NULL for errors)
                    cursor.execute("""
                        INSERT INTO ssl_certificates 
                        (domain_id, domain, cert_path, key_path, status, error_message, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (domain_id) DO UPDATE SET
                            cert_path = NULL,
                            key_path = NULL,
                            status = EXCLUDED.status,
                            error_message = EXCLUDED.error_message,
                            expires_at = NULL,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        domain_id,
                        domain,
                        None,  # cert_path
                        None,  # key_path
                        'error',
                        error_message[:500] if error_message else None,
                        None  # expires_at
                    ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating certificate status for {domain}: {e}")
    
    def process_all_domains(self) -> Dict[str, int]:
        """
        Process all eligible domains and issue certificates.
        
        Returns:
            Statistics dict with counts
        """
        stats = {
            'total': 0,
            'processed': 0,
            'issued': 0,
            'skipped_verification': 0,
            'skipped_already_exists': 0,
            'errors': 0
        }
        
        domains = self.get_all_eligible_domains()
        stats['total'] = len(domains)
        logger.info(f"Found {len(domains)} eligible domains for certificate issuance")
        
        for domain_row in domains:
            domain_id = domain_row['id']
            domain = domain_row['domain']
            stats['processed'] += 1
            
            try:
                # When force_reissue=True, cert_manager will not skip for "already exists" and will re-issue (e.g. to add www)
                # Verify TXT and A-record
                logger.info(f"Verifying {domain} (TXT and A-record)...")
                is_valid, error_msg = self.verify_domain_checks(domain)
                
                if not is_valid:
                    logger.warning(f"Skipping {domain}: {error_msg}")
                    stats['skipped_verification'] += 1
                    self.update_certificate_status(
                        domain_id, domain, False,
                        error_message=error_msg
                    )
                    continue
                
                # Issue certificate (force_reissue so certbot does fresh issuance with apex+www, not old apex-only)
                logger.info(f"Issuing certificate for {domain}...")
                success, error_msg, cert_info = self.cert_manager.issue_certificate(domain, force_reissue=True)
                
                if success:
                    logger.info(f"✓ Certificate issued for {domain}")
                    stats['issued'] += 1
                    self.update_certificate_status(domain_id, domain, True, cert_info)
                else:
                    logger.warning(f"✗ Failed to issue certificate for {domain}: {error_msg}")
                    stats['errors'] += 1
                    self.update_certificate_status(domain_id, domain, False, error_message=error_msg)
                    
                    # If rate limited, stop processing
                    if 'rate limit' in error_msg.lower():
                        logger.warning("Rate limit reached, stopping processing")
                        logger.info("Run this script again later to continue with remaining domains")
                        break
                
                # Small delay to avoid overwhelming the system and respect rate limits
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing {domain}: {e}", exc_info=True)
                stats['errors'] += 1
                self.update_certificate_status(
                    domain_id, domain, False,
                    error_message=f"Exception: {str(e)}"
                )
        
        return stats
    
    def run(self, non_interactive: bool = False):
        """Main execution method."""
        logger.info("=" * 80)
        logger.info("BATCH SSL CERTIFICATE ISSUANCE")
        logger.info("=" * 80)
        logger.info(f"Staging mode: {self.use_staging}")
        logger.info("Issues certificates for domains that should have one but do not (no cert or status != active).")
        logger.info("Eligible: verified=TRUE, is_mining=TRUE, a_record_points_to_us=TRUE, (no ssl_certificates row OR status != 'active')")
        logger.info("=" * 80)
        
        if not non_interactive:
            response = input("Continue with batch certificate issuance? (yes/no): ")
            if response.lower() not in ('yes', 'y'):
                logger.info("Aborted by user")
                return
        
        stats = self.process_all_domains()
        
        logger.info("=" * 80)
        logger.info("BATCH CERTIFICATE ISSUANCE COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Total eligible domains: {stats['total']}")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Issued: {stats['issued']}")
        logger.info(f"Skipped (verification failed): {stats['skipped_verification']}")
        logger.info(f"Skipped (already exists): {stats['skipped_already_exists']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 80)
        
        if stats['errors'] > 0 or stats['skipped_verification'] > 0:
            logger.info("")
            logger.info("Note: Some domains were skipped due to:")
            logger.info("  - Failed TXT or A-record verification")
            logger.info("  - Rate limits (run script again later)")
            logger.info("  - Other errors (check logs for details)")


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Issue SSL certificates for eligible domains (verified + A-record).')
    parser.add_argument('-y', '--yes', action='store_true', help='Non-interactive: do not ask for confirmation')
    parser.add_argument('--staging', action='store_true', help='Use Let\'s Encrypt staging (overrides LETSENCRYPT_STAGING)')
    args = parser.parse_args()
    use_staging = args.staging or os.getenv('LETSENCRYPT_STAGING', '0').lower() in ('1', 'true', 'yes')
    issuer = BatchCertificateIssuer(use_staging=use_staging)
    issuer.run(non_interactive=args.yes)


if __name__ == '__main__':
    main()
