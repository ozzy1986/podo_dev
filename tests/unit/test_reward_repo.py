"""
Unit tests for app.repositories.reward_repo – RewardRepository with mocked ClickHouse.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.reward_repo import RewardRepository


@pytest.fixture
def mock_pg():
    """Mock PostgreSQL connection."""
    return MagicMock()


@pytest.fixture
def mock_ch():
    """Mock ClickHouse client with async methods."""
    ch = MagicMock()
    ch.async_fetchval = AsyncMock(return_value=100)
    ch.async_insert = AsyncMock(return_value=1)
    ch.async_execute_dict = AsyncMock(return_value=[])
    return ch


@pytest.fixture
def reward_repo(mock_pg, mock_ch):
    """RewardRepository with mocked databases."""
    return RewardRepository(mock_pg, mock_ch)


class TestLogReward:
    """Tests for log_reward."""

    @pytest.mark.asyncio
    async def test_log_reward_with_explicit_id(self, reward_repo, mock_ch):
        """Uses provided reward_id when given."""
        mock_ch.async_insert = AsyncMock(return_value=1)
        rid = await reward_repo.log_reward(
            domain_id=1, wallet="3Nxxx", amount=1.0, amount_units=100000000, reward_id=999
        )
        assert rid == 999
        call_args = mock_ch.async_insert.call_args
        assert call_args[0][1][0]["id"] == 999

    @pytest.mark.asyncio
    async def test_log_reward_without_id_uses_counter(self, reward_repo, mock_ch):
        """Uses in-memory counter when reward_id is None."""
        mock_ch.async_fetchval = AsyncMock(return_value=50)
        with patch("app.repositories.reward_repo._reward_id_counter", 0):
            rid = await reward_repo.log_reward(
                domain_id=1, wallet="3Nyyy", amount=0.5, amount_units=50000000
            )
        assert rid == 51
        mock_ch.async_fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_reward_second_call_increments_counter(self, reward_repo, mock_ch):
        """Second log_reward without id uses in-memory increment (else branch)."""
        mock_ch.async_fetchval = AsyncMock(return_value=50)
        with patch("app.repositories.reward_repo._reward_id_counter", 0):
            rid1 = await reward_repo.log_reward(
                domain_id=1, wallet="3Na", amount=0.5, amount_units=50000000
            )
            rid2 = await reward_repo.log_reward(
                domain_id=2, wallet="3Nb", amount=0.5, amount_units=50000000
            )
        assert rid1 == 51
        assert rid2 == 52
        mock_ch.async_fetchval.assert_called_once()


class TestGetUserTotalEarned:
    """Tests for get_user_total_earned."""

    @pytest.mark.asyncio
    async def test_returns_total_when_result_exists(self, reward_repo, mock_ch):
        """Returns sum when ClickHouse returns rows."""
        mock_ch.async_execute_dict = AsyncMock(return_value=[{"total": 42.5}])
        total = await reward_repo.get_user_total_earned("3Nwallet")
        assert total == 42.5

    @pytest.mark.asyncio
    async def test_returns_zero_when_empty(self, reward_repo, mock_ch):
        """Returns 0.0 when no result or total is None."""
        mock_ch.async_execute_dict = AsyncMock(return_value=[])
        total = await reward_repo.get_user_total_earned("3Nempty")
        assert total == 0.0

        mock_ch.async_execute_dict = AsyncMock(return_value=[{"total": None}])
        total = await reward_repo.get_user_total_earned("3Nempty")
        assert total == 0.0


class TestGetDomainEarnings:
    """Tests for get_domain_earnings."""

    @pytest.mark.asyncio
    async def test_get_domain_earnings_with_filters(self, reward_repo, mock_ch):
        """Passes start_date and end_date to query."""
        mock_ch.async_execute_dict = AsyncMock(return_value=[
            {"id": 1, "amount": 1.0, "created_at": "2025-01-01"}
        ])
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        result = await reward_repo.get_domain_earnings(10, start_date=start, end_date=end)
        assert len(result) == 1
        call_args = mock_ch.async_execute_dict.call_args
        assert "start_date" in str(call_args)
        assert "end_date" in str(call_args)


class TestGetUserEarningsTimeseries:
    """Tests for get_user_earnings_timeseries."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_wallet(self, reward_repo):
        """Returns empty structure when wallet is empty."""
        result = await reward_repo.get_user_earnings_timeseries("")
        assert result["daily_earnings"] == {}
        assert result["weekly_earnings"] == {}
        assert result["avg_daily"] == 0.0
        assert result["avg_weekly"] == 0.0

    @pytest.mark.asyncio
    async def test_returns_timeseries_from_daily_stats(self, reward_repo, mock_ch):
        """Uses rewards_daily_stats when available."""
        mock_ch.async_execute_dict = AsyncMock(side_effect=[
            [{"day": "2025-01-15", "total": 10.0}, {"day": "2025-01-16", "total": 20.0}],
            [{"week_start": "2025-01-13", "total": 30.0}],
        ])
        result = await reward_repo.get_user_earnings_timeseries("3Nwallet")
        assert "2025-01-15" in result["daily_earnings"]
        assert result["daily_earnings"]["2025-01-15"] == 10.0
        assert result["avg_daily"] == 15.0
        assert result["avg_weekly"] == 30.0

    @pytest.mark.asyncio
    async def test_fallback_to_rewards_log_on_unknown_table(self, reward_repo, mock_ch):
        """Falls back to rewards_log when rewards_daily_stats does not exist."""
        mock_ch.async_execute_dict = AsyncMock(side_effect=[
            Exception("Unknown table rewards_daily_stats"),
            [{"day": "2025-01-15", "total": 5.0}],
            [{"week_start": "2025-01-13", "total": 5.0}],
        ])
        result = await reward_repo.get_user_earnings_timeseries("3Nwallet")
        assert "2025-01-15" in result["daily_earnings"]
        assert result["avg_daily"] == 5.0

    @pytest.mark.asyncio
    async def test_skips_non_dict_rows(self, reward_repo, mock_ch):
        """Skips rows that are not dicts (ClickHouse edge case)."""
        mock_ch.async_execute_dict = AsyncMock(side_effect=[
            [{"day": "2025-01-15", "total": 10.0}, "invalid_row", {"day": "2025-01-16", "total": 20.0}],
            [{"week_start": "2025-01-13", "total": 30.0}, 42, {"week_start": "2025-01-20", "total": 10.0}],
        ])
        result = await reward_repo.get_user_earnings_timeseries("3Nwallet")
        assert "2025-01-15" in result["daily_earnings"]
        assert "2025-01-16" in result["daily_earnings"]
        assert "2025-01-13" in result["weekly_earnings"]
        assert "2025-01-20" in result["weekly_earnings"]
        assert len(result["daily_earnings"]) == 2

    @pytest.mark.asyncio
    async def test_fallback_also_raises_returns_empty(self, reward_repo, mock_ch):
        """When fallback query also fails, returns empty structure."""
        mock_ch.async_execute_dict = AsyncMock(side_effect=[
            Exception("rewards_daily_stats missing"),
            Exception("fallback failed"),
        ])
        result = await reward_repo.get_user_earnings_timeseries("3Nwallet")
        assert result["daily_earnings"] == {}
        assert result["weekly_earnings"] == {}
        assert result["avg_daily"] == 0.0
        assert result["avg_weekly"] == 0.0

    @pytest.mark.asyncio
    async def test_other_exception_returns_empty(self, reward_repo, mock_ch):
        """When first query raises non-table-error, returns empty (else branch)."""
        mock_ch.async_execute_dict = AsyncMock(side_effect=Exception("connection refused"))
        result = await reward_repo.get_user_earnings_timeseries("3Nwallet")
        assert result["daily_earnings"] == {}
        assert result["avg_daily"] == 0.0


class TestGetSystemStats:
    """Tests for get_system_stats."""

    @pytest.mark.asyncio
    async def test_returns_stats_dict(self, reward_repo, mock_ch):
        """Returns first row as stats dict."""
        mock_ch.async_execute_dict = AsyncMock(return_value=[{
            "total_rewards": 100,
            "total_distributed": 500.0,
            "unique_wallets": 50,
            "domains_rewarded": 30,
        }])
        result = await reward_repo.get_system_stats()
        assert result["total_rewards"] == 100
        assert result["total_distributed"] == 500.0

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_result(self, reward_repo, mock_ch):
        """Returns empty dict when no rows."""
        mock_ch.async_execute_dict = AsyncMock(return_value=[])
        result = await reward_repo.get_system_stats()
        assert result == {}
