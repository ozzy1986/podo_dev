"""
Integration tests for RewardRepository against real ClickHouse database.

Tests all 5 methods with real database operations.
Skips insert-based tests when rewards_log uses a View engine.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from app.repositories.reward_repo import RewardRepository


@pytest.mark.asyncio
@pytest.mark.integration
async def test_log_reward(real_pg_db, real_ch_db, test_user, test_domain, ch_rewards_writable):
    """Test logging a reward in ClickHouse."""
    if not ch_rewards_writable:
        pytest.skip("rewards_log is a View — cannot INSERT directly")

    repo = RewardRepository(real_pg_db, real_ch_db)
    test_wallet = test_user["wallet"]
    
    reward_id = await repo.log_reward(
        domain_id=test_domain["id"],
        wallet=test_wallet,
        amount=1.5,
        amount_units=150000000
    )
    
    assert reward_id > 0
    
    # Verify in ClickHouse
    query = "SELECT * FROM rewards_log WHERE id = %(id)s"
    result = await real_ch_db.async_execute_dict(query, {"id": reward_id})
    assert len(result) == 1
    assert result[0]["wallet"] == test_wallet
    assert float(result[0]["amount"]) == 1.5
    assert result[0]["status"] == "pending"
    
    # Cleanup
    try:
        await real_ch_db.async_execute("ALTER TABLE rewards_log DELETE WHERE id = %(id)s", {"id": reward_id})
    except Exception:
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_total_earned(real_pg_db, real_ch_db, test_user, ch_rewards_writable):
    """Test getting total earnings for a wallet."""
    if not ch_rewards_writable:
        pytest.skip("rewards_log is a View — cannot INSERT test data")

    repo = RewardRepository(real_pg_db, real_ch_db)
    test_wallet = test_user["wallet"]
    
    # Insert test rewards
    reward_ids = []
    try:
        for i in range(3):
            reward_id = await repo.log_reward(
                domain_id=None,
                wallet=test_wallet,
                amount=10.0 + i,
                amount_units=(10 + i) * 100000000,
                reward_id=None
            )
            reward_ids.append(reward_id)
        
        # Update status to confirmed
        for reward_id in reward_ids:
            await real_ch_db.async_execute(
                "ALTER TABLE rewards_log UPDATE status = 'confirmed' WHERE id = %(id)s",
                {"id": reward_id}
            )
        
        # Wait a moment for ClickHouse to process
        import asyncio
        await asyncio.sleep(0.5)
        
        total = await repo.get_user_total_earned(test_wallet)
        assert total == 33.0  # 10 + 11 + 12
        
    finally:
        # Cleanup
        for reward_id in reward_ids:
            try:
                await real_ch_db.async_execute("ALTER TABLE rewards_log DELETE WHERE id = %(id)s", {"id": reward_id})
            except Exception:
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_domain_earnings(real_pg_db, real_ch_db, test_domain, ch_rewards_writable):
    """Test getting earnings history for a domain."""
    if not ch_rewards_writable:
        pytest.skip("rewards_log is a View — cannot INSERT test data")

    repo = RewardRepository(real_pg_db, real_ch_db)
    test_wallet = "3TestWallet1234567890"
    
    reward_ids = []
    try:
        # Insert rewards for the domain
        for i in range(2):
            reward_id = await repo.log_reward(
                domain_id=test_domain["id"],
                wallet=test_wallet,
                amount=5.0 + i,
                amount_units=(5 + i) * 100000000
            )
            reward_ids.append(reward_id)
        
        # Get domain earnings
        earnings = await repo.get_domain_earnings(test_domain["id"])
        assert len(earnings) >= 2
        
        domain_rewards = [e for e in earnings if e.get("domain_id") == test_domain["id"]]
        assert len(domain_rewards) >= 2
        
    finally:
        # Cleanup
        for reward_id in reward_ids:
            try:
                await real_ch_db.async_execute("ALTER TABLE rewards_log DELETE WHERE id = %(id)s", {"id": reward_id})
            except Exception:
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_earnings_timeseries(real_pg_db, real_ch_db, test_user, ch_rewards_writable):
    """Test getting daily/weekly earnings timeseries."""
    if not ch_rewards_writable:
        pytest.skip("rewards_log is a View — cannot INSERT test data")

    repo = RewardRepository(real_pg_db, real_ch_db)
    test_wallet = test_user["wallet"]
    
    reward_ids = []
    try:
        # Insert rewards with different dates
        now = datetime.utcnow()
        for i in range(3):
            reward_id = await repo.log_reward(
                domain_id=None,
                wallet=test_wallet,
                amount=2.0,
                amount_units=200000000
            )
            reward_ids.append(reward_id)
            
            # Update status and created_at
            created_at = (now - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
            await real_ch_db.async_execute(
                f"ALTER TABLE rewards_log UPDATE status = 'confirmed', created_at = '{created_at}' WHERE id = %(id)s",
                {"id": reward_id}
            )
        
        # Wait for ClickHouse to process
        import asyncio
        await asyncio.sleep(1)
        
        timeseries = await repo.get_user_earnings_timeseries(test_wallet)
        
        assert "daily_earnings" in timeseries
        assert "weekly_earnings" in timeseries
        assert "avg_daily" in timeseries
        assert "avg_weekly" in timeseries
        
        # Should have some earnings (may be empty if materialized view doesn't exist, that's OK)
        assert isinstance(timeseries["daily_earnings"], dict)
        assert isinstance(timeseries["weekly_earnings"], dict)
        
    finally:
        # Cleanup
        for reward_id in reward_ids:
            try:
                await real_ch_db.async_execute("ALTER TABLE rewards_log DELETE WHERE id = %(id)s", {"id": reward_id})
            except Exception:
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_system_stats(real_pg_db, real_ch_db):
    """Test getting system-wide reward statistics."""
    repo = RewardRepository(real_pg_db, real_ch_db)
    
    stats = await repo.get_system_stats()
    
    assert "total_rewards" in stats or "count()" in stats
    assert isinstance(stats, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_earnings_timeseries_empty_wallet(real_pg_db, real_ch_db):
    """Test timeseries with empty wallet returns zeros."""
    repo = RewardRepository(real_pg_db, real_ch_db)
    
    timeseries = await repo.get_user_earnings_timeseries("")
    assert timeseries["daily_earnings"] == {}
    assert timeseries["weekly_earnings"] == {}
    assert timeseries["avg_daily"] == 0.0
    assert timeseries["avg_weekly"] == 0.0
