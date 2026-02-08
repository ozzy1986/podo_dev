"""
Promotion renewal worker.
Runs every 15 minutes to process subscription renewals.
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_promotion_renewals_job():
    """
    Process promotion subscription renewals.
    
    This is called by the scheduler every 15 minutes.
    """
    settings = get_settings()
    
    logger.info("Starting promotion renewal job...")
    
    try:
        # Import the actual renewal processor
        from scripts.run_promotion_renewal import main as run_renewal
        
        # Run renewal processing
        run_renewal()
        
        logger.info("Promotion renewal job completed successfully")
    
    except Exception as e:
        logger.error(f"Promotion renewal job failed: {e}", exc_info=True)
