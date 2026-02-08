"""
Payout processing worker.
Runs every 10 minutes to process pending withdrawal requests.
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_payouts_job():
    """
    Process pending payout requests.
    
    This is called by the scheduler every 10 minutes.
    Skipped on development servers (no real blockchain transactions).
    """
    settings = get_settings()
    
    if settings.is_development:
        logger.debug("DEV: Skipping payout processing (development mode)")
        return
    
    logger.info("Starting payout processing job...")
    
    try:
        # Import the actual payout scheduler from oracle
        from oracle.payout_scheduler import run_scheduler
        
        # Run payout processing
        run_scheduler()
        
        logger.info("Payout processing job completed successfully")
    
    except Exception as e:
        logger.error(f"Payout processing job failed: {e}", exc_info=True)
