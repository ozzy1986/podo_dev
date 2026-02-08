"""
d.onl Oracle Main Entry Point
Runs domain verification and reward processor every 12 hours.
"""

import logging
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Do not run oracle scheduler on development server (dev.d.onl)
from config.config import is_development
if is_development():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _log = logging.getLogger(__name__)
    _log.info("APP_ENV=development: oracle scheduler disabled. Exiting.")
    sys.exit(0)

from oracle.domain_processor import process_domains
from oracle.payout_scheduler import run_scheduler

# SSL certificate management (optional - only import if available)
# Note: Certificate issuance happens automatically when user verifies A-record
# Only renewal scheduler is needed here
try:
    from scripts.ssl.renew_certificates import SSLCertificateRenewer
    SSL_AVAILABLE = True
except ImportError:
    SSL_AVAILABLE = False
    logger.warning("SSL certificate management not available (scripts/ssl not found)")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Main oracle scheduler.
    
    Runs:
    - Domain verification and reward processing every 12 hours (at 00:00 and 12:00)
    - Payout scheduler every 10 minutes (for processing pending payouts)
    """
    scheduler = BlockingScheduler()

    # Run domain processor every 12 hours (at 00:00 and 12:00)
    scheduler.add_job(
        process_domains,
        'cron',
        hour='0,12',  # Run at midnight and noon
        minute=0,
        id='domain_processor',
        max_instances=1,  # Prevent overlap
        misfire_grace_time=3600  # 1 hour grace period
    )

    # Run payout scheduler every 10 minutes (for processing pending payouts).
    # Do not also add scripts/run_payout_scheduler.sh to crontab when this service runs (duplicate = extra CPU).
    scheduler.add_job(
        run_scheduler,
        'interval',
        minutes=10,
        id='payout_scheduler',
        max_instances=1
    )

    # SSL certificate management (if available)
    # Note: Certificate issuance happens automatically when user verifies A-record via API
    # Only renewal is scheduled here
    if SSL_AVAILABLE:
        # Renew SSL certificates daily at 3 AM
        def renew_ssl_certificates():
            renewer = SSLCertificateRenewer(use_staging=False, days_before_expiry=30)
            renewer.run()
        
        scheduler.add_job(
            renew_ssl_certificates,
            'cron',
            hour=3,
            minute=0,
            id='ssl_cert_renewal',
            max_instances=1,
            misfire_grace_time=3600
        )

    logger.info("=" * 60)
    logger.info("d.onl Oracle Started")
    logger.info("  Domain Processor: Every 12 hours (00:00, 12:00)")
    logger.info("  Payout Scheduler: Every 10 minutes")
    if SSL_AVAILABLE:
        logger.info("  SSL Certificate Renewal: Daily at 3:00 AM")
        logger.info("  SSL Certificate Issuance: Automatic (when A-record verified)")
    logger.info("=" * 60)
    logger.info("Press Ctrl+C to exit.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
