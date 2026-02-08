"""
Consolidated scheduler for all background tasks.
In dev mode: runs domain checks and SSL renewal only.
In production: runs all jobs including rewards and payouts.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler():
    """
    Start the background task scheduler.

    Dev mode: domain verification + SSL renewal only (no money operations).
    Production: all jobs.
    """
    settings = get_settings()
    scheduler = get_scheduler()

    from app.workers.domain_processor import process_domains_job
    from app.workers.ssl_renewal import renew_ssl_certificates_job

    # Domain verification (runs in both dev and prod)
    scheduler.add_job(
        process_domains_job,
        trigger=CronTrigger(hour='0,12', minute=0),
        id='domain_processor',
        name='Domain Verification & Processing',
        max_instances=1,
        misfire_grace_time=3600,
        replace_existing=True
    )
    logger.info("Scheduled: Domain processor (every 12h at 00:00, 12:00)")

    # SSL certificate renewal (runs in both dev and prod)
    scheduler.add_job(
        renew_ssl_certificates_job,
        trigger=CronTrigger(hour=3, minute=0),
        id='ssl_renewal',
        name='SSL Certificate Renewal',
        max_instances=1,
        misfire_grace_time=3600,
        replace_existing=True
    )
    logger.info("Scheduled: SSL renewal (daily at 03:00)")

    # Production-only jobs (money operations)
    if not settings.is_development:
        from app.workers.hourly_rewards import process_hourly_rewards_job
        from app.workers.payout_scheduler import process_payouts_job
        from app.workers.promotion_renewal import process_promotion_renewals_job

        scheduler.add_job(
            process_hourly_rewards_job,
            trigger=CronTrigger(hour='*', minute=0),
            id='hourly_rewards',
            name='Hourly Rewards Distribution',
            max_instances=1,
            misfire_grace_time=600,
            replace_existing=True
        )
        logger.info("Scheduled: Hourly rewards (every hour)")

        scheduler.add_job(
            process_payouts_job,
            trigger=IntervalTrigger(minutes=10),
            id='payout_scheduler',
            name='Payout Processing',
            max_instances=1,
            replace_existing=True
        )
        logger.info("Scheduled: Payout processor (every 10 minutes)")

        scheduler.add_job(
            process_promotion_renewals_job,
            trigger=IntervalTrigger(minutes=15),
            id='promotion_renewal',
            name='Promotion Renewals',
            max_instances=1,
            replace_existing=True
        )
        logger.info("Scheduled: Promotion renewals (every 15 minutes)")

    scheduler.start()

    logger.info("=" * 60)
    logger.info("Background scheduler started")
    logger.info(f"  Environment: {settings.app_env}")
    if settings.is_development:
        logger.info("  DEV MODE: Only domain checks and SSL renewal active")
        logger.info("  Rewards, payouts, and promotions are DISABLED")
    else:
        logger.info("  PRODUCTION: All jobs active")
    logger.info("=" * 60)


async def stop_scheduler():
    """Stop the background task scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
