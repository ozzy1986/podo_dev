"""
Domain verification and processing worker.
Runs every 12 hours to verify domains and update mining status.
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_domains_job():
    """
    Process domains: verify DNS, update mining status.
    
    This is called by the scheduler every 12 hours.
    """
    settings = get_settings()
    
    logger.info("Starting domain processing job...")
    
    try:
        # Import the actual domain processor from oracle
        from oracle.domain_processor import process_domains
        
        # Run domain processing
        process_domains()
        
        logger.info("Domain processing job completed successfully")
    
    except Exception as e:
        logger.error(f"Domain processing job failed: {e}", exc_info=True)
