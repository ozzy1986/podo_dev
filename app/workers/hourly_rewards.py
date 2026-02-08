"""
Hourly rewards distribution worker.
Runs every hour to calculate and distribute mining rewards.
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_hourly_rewards_job():
    """
    Process hourly rewards: calculate emissions and distribute to miners.
    
    This is called by the scheduler every hour.
    Skipped on development servers.
    """
    settings = get_settings()
    
    if settings.is_development:
        logger.info("DEV: Skipping hourly rewards (development mode)")
        return
    
    logger.info("Starting hourly rewards job...")
    
    try:
        # Import the actual hourly processor from oracle
        from oracle.hourly_processor import process_hour
        
        # Run hourly processing
        process_hour()
        
        logger.info("Hourly rewards job completed successfully")
    
    except Exception as e:
        logger.error(f"Hourly rewards job failed: {e}", exc_info=True)
