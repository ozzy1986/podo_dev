"""
SSL certificate renewal worker.
Runs daily at 3 AM to renew expiring certificates.
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


async def renew_ssl_certificates_job():
    """
    Renew SSL certificates that are expiring soon.
    
    This is called by the scheduler daily at 3:00 AM.
    Skipped on development servers.
    """
    settings = get_settings()
    
    if settings.is_development:
        logger.info("DEV: Skipping SSL renewal (development mode)")
        return
    
    logger.info("Starting SSL renewal job...")
    
    try:
        # Import the SSL renewal module
        from scripts.ssl.renew_certificates import SSLCertificateRenewer
        
        # Run SSL renewal
        renewer = SSLCertificateRenewer(use_staging=False, days_before_expiry=30)
        renewer.run()
        
        logger.info("SSL renewal job completed successfully")
    
    except Exception as e:
        logger.error(f"SSL renewal job failed: {e}", exc_info=True)
