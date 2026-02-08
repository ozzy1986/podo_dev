"""
Stats and config API routes.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_reward_repo, get_app_settings
from app.repositories.reward_repo import RewardRepository
from app.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Stats"])


def _serialize(obj: Any) -> Any:
    """Convert Decimal/datetime to JSON-safe types."""
    from decimal import Decimal
    from datetime import datetime
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def _map_system_stats(raw: dict) -> dict:
    """Map backend system stats to frontend-expected fields."""
    domains_rewarded = raw.get("domains_rewarded", 0) or 0
    return {
        "total_domains": domains_rewarded,
        "active_domains": domains_rewarded,
        "verified_domains": domains_rewarded,
        "total_users": raw.get("unique_wallets", 0) or 0,
        "total_rewards_distributed": float(raw.get("total_distributed", 0) or 0),
        "successful_transactions": raw.get("total_rewards", 0) or 0,
        "failed_transactions": raw.get("failed_transactions", 0) or 0,
        "total_rewards": raw.get("total_rewards", 0),
        "total_distributed": raw.get("total_distributed", 0),
        "unique_wallets": raw.get("unique_wallets", 0),
        "domains_rewarded": domains_rewarded,
    }


@router.get("/stats")
async def get_stats(
    reward_repo: RewardRepository = Depends(get_reward_repo),
):
    """Get system-wide stats. Frontend expects total_domains, active_domains, total_users, total_rewards_distributed, successful_transactions, failed_transactions."""
    try:
        stats = await reward_repo.get_system_stats()
        return _serialize(_map_system_stats(stats))
    except Exception as e:
        logger.warning(f"get_stats failed: {e}")
        return _serialize(_map_system_stats({
            "total_rewards": 0,
            "total_distributed": 0,
            "unique_wallets": 0,
            "domains_rewarded": 0,
            "failed_transactions": 0,
        }))


@router.get("/config")
async def get_config(
    settings: Settings = Depends(get_app_settings),
):
    """Get public app config (token name, etc.)."""
    return {
        "token_name": settings.blockchain.token_name,
        "token_decimals": settings.blockchain.token_decimals,
        "site_url": settings.site_url,
        "debug": settings.debug,
    }


@router.get("/subscription/frequencies")
async def get_subscription_frequencies():
    """Get available promotion subscription frequencies."""
    return {
        "frequencies": [
            {"id": "5min", "label": "5 minutes", "minutes": 5},
            {"id": "10min", "label": "10 minutes", "minutes": 10},
            {"id": "15min", "label": "15 minutes", "minutes": 15},
            {"id": "1hour", "label": "1 hour", "minutes": 60},
            {"id": "2hours", "label": "2 hours", "minutes": 120},
            {"id": "3hours", "label": "3 hours", "minutes": 180},
            {"id": "5hours", "label": "5 hours", "minutes": 300},
            {"id": "7hours", "label": "7 hours", "minutes": 420},
            {"id": "10hours", "label": "10 hours", "minutes": 600},
            {"id": "24hours", "label": "24 hours", "minutes": 1440},
            {"id": "48hours", "label": "48 hours", "minutes": 2880},
            {"id": "72hours", "label": "72 hours", "minutes": 4320},
            {"id": "1week", "label": "1 week", "minutes": 10080},
        ]
    }
