"""
Reward repository for database operations (PostgreSQL + ClickHouse).
All ClickHouse calls use async wrappers to avoid blocking the event loop.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.repositories.base import BaseRepository
from app.db.clickhouse import ClickHouseDatabase

logger = logging.getLogger(__name__)

# Monotonic in-memory counter used when no external ID is provided.
# Safe because only one uvicorn worker writes rewards at a time via the scheduler.
_reward_id_counter: int = 0


class RewardRepository(BaseRepository):
    """Repository for reward operations."""

    def __init__(self, db, ch_db: ClickHouseDatabase):
        super().__init__(db)
        self.ch_db = ch_db

    async def log_reward(
        self,
        domain_id: int,
        wallet: str,
        amount: float,
        amount_units: int,
        reward_id: Optional[int] = None,
    ) -> int:
        """
        Log a reward in ClickHouse.

        Uses a caller-supplied ``reward_id`` (preferred) or a monotonic
        in-memory counter instead of the expensive MAX(id) scan.

        Args:
            domain_id: Domain ID
            wallet: Recipient wallet
            amount: Reward amount (tokens)
            amount_units: Reward amount (smallest units)
            reward_id: Pre-allocated ID (e.g. from PG sequence). If *None*,
                an in-memory counter is used.

        Returns:
            Reward log ID that was inserted.
        """
        global _reward_id_counter

        if reward_id is None:
            # Lazy-init counter from ClickHouse once, then increment in-memory
            if _reward_id_counter == 0:
                max_id = await self.ch_db.async_fetchval(
                    "SELECT max(id) FROM rewards_log"
                )
                _reward_id_counter = (max_id or 0) + 1
            else:
                _reward_id_counter += 1
            reward_id = _reward_id_counter

        data = [{
            'id': reward_id,
            'domain_id': domain_id,
            'wallet': wallet,
            'amount': amount,
            'amount_units': amount_units,
            'status': 'pending',
            'created_at': datetime.utcnow(),
        }]

        await self.ch_db.async_insert('rewards_log', data)
        logger.debug("reward_logged id=%d domain=%d wallet=%s amount=%s", reward_id, domain_id, wallet, amount)
        return reward_id

    async def get_user_total_earned(self, wallet: str) -> float:
        """
        Get total earnings for a wallet from ClickHouse.

        Args:
            wallet: User wallet address

        Returns:
            Total earned amount
        """
        query = """
            SELECT SUM(amount) AS total
            FROM rewards_log
            WHERE wallet = %(wallet)s
              AND status IN ('confirmed', 'accumulated')
        """
        result = await self.ch_db.async_execute_dict(query, {'wallet': wallet})
        return float(result[0]['total']) if result and result[0].get('total') else 0.0

    async def get_domain_earnings(
        self,
        domain_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get earnings history for a domain.

        Args:
            domain_id: Domain ID
            start_date: Start date filter
            end_date: End date filter
            limit: Max rows returned

        Returns:
            List of reward records
        """
        query = "SELECT * FROM rewards_log WHERE domain_id = %(domain_id)s"
        params: Dict[str, Any] = {'domain_id': domain_id}

        if start_date:
            query += " AND created_at >= %(start_date)s"
            params['start_date'] = start_date
        if end_date:
            query += " AND created_at <= %(end_date)s"
            params['end_date'] = end_date

        query += " ORDER BY created_at DESC LIMIT %(limit)s"
        params['limit'] = limit

        return await self.ch_db.async_execute_dict(query, params)

    async def get_user_earnings_timeseries(self, wallet: str) -> Dict[str, Any]:
        """
        Get daily and weekly earnings for charts.
        Uses rewards_daily_stats materialized view for performance.

        Returns:
            dict with daily_earnings, weekly_earnings, avg_daily, avg_weekly
        """
        if not wallet:
            return {
                "daily_earnings": {},
                "weekly_earnings": {},
                "avg_daily": 0.0,
                "avg_weekly": 0.0,
            }

        daily_earnings: Dict[str, float] = {}
        weekly_earnings: Dict[str, float] = {}

        def _date_key(val) -> str:
            return val.isoformat() if hasattr(val, "isoformat") else str(val)

        params = {"wallet": wallet}

        try:
            # Try rewards_daily_stats first (materialized view, fast)
            daily_query = """
                SELECT day, sum(total_amount) AS total
                FROM rewards_daily_stats
                WHERE wallet = %(wallet)s AND day >= today() - 30
                GROUP BY wallet, day ORDER BY day
            """
            weekly_query = """
                SELECT toMonday(day) AS week_start, sum(total_amount) AS total
                FROM rewards_daily_stats
                WHERE wallet = %(wallet)s AND day >= today() - 84
                GROUP BY wallet, week_start ORDER BY week_start
            """
            daily_rows = await self.ch_db.async_execute_dict(daily_query, params)
            weekly_rows = await self.ch_db.async_execute_dict(weekly_query, params)
        except Exception as e:
            err_msg = str(e).lower()
            if "rewards_daily_stats" in err_msg or "unknown table" in err_msg:
                # Fallback: aggregate from rewards_log (table always exists)
                logger.debug("rewards_daily_stats not available, using rewards_log: %s", e)
                daily_query = """
                    SELECT toDate(created_at) AS day, sum(amount) AS total
                    FROM rewards_log
                    WHERE wallet = %(wallet)s AND status IN ('confirmed', 'accumulated')
                      AND created_at >= today() - 30
                    GROUP BY day ORDER BY day
                """
                weekly_query = """
                    SELECT toMonday(toDate(created_at)) AS week_start, sum(amount) AS total
                    FROM rewards_log
                    WHERE wallet = %(wallet)s AND status IN ('confirmed', 'accumulated')
                      AND created_at >= today() - 84
                    GROUP BY week_start ORDER BY week_start
                """
                try:
                    daily_rows = await self.ch_db.async_execute_dict(daily_query, params)
                    weekly_rows = await self.ch_db.async_execute_dict(weekly_query, params)
                except Exception as fallback_err:
                    logger.warning("get_user_earnings_timeseries fallback failed: %s", fallback_err)
                    return {
                        "daily_earnings": {},
                        "weekly_earnings": {},
                        "avg_daily": 0.0,
                        "avg_weekly": 0.0,
                    }
            else:
                logger.warning("get_user_earnings_timeseries failed: %s", e)
                return {
                    "daily_earnings": {},
                    "weekly_earnings": {},
                    "avg_daily": 0.0,
                    "avg_weekly": 0.0,
                }

        for row in daily_rows or []:
            if not isinstance(row, dict):
                continue
            if day := row.get("day"):
                daily_earnings[_date_key(day)] = float(row.get("total", 0) or 0)
        for row in weekly_rows or []:
            if not isinstance(row, dict):
                continue
            if week_start := row.get("week_start"):
                weekly_earnings[_date_key(week_start)] = float(row.get("total", 0) or 0)

        daily_vals = list(daily_earnings.values()) or [0]
        weekly_vals = list(weekly_earnings.values()) or [0]
        avg_daily = sum(daily_vals) / len(daily_vals) if daily_vals else 0.0
        avg_weekly = sum(weekly_vals) / len(weekly_vals) if weekly_vals else 0.0

        return {
            "daily_earnings": daily_earnings,
            "weekly_earnings": weekly_earnings,
            "avg_daily": round(avg_daily, 2),
            "avg_weekly": round(avg_weekly, 2),
        }

    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system-wide reward statistics.

        Returns:
            Statistics dictionary
        """
        query = """
            SELECT
                count()                    AS total_rewards,
                sum(amount)                AS total_distributed,
                uniq(wallet)               AS unique_wallets,
                uniq(domain_id)            AS domains_rewarded
            FROM rewards_log
        """
        result = await self.ch_db.async_execute_dict(query)
        return result[0] if result else {}
