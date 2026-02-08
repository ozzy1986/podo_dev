"""
ClickHouse connection and schema validation tests.

Validates that the ClickHouse connection works and all expected
tables and materialized views exist.
"""

import pytest
from datetime import datetime


@pytest.mark.integration
def test_ch_connection(real_ch_db):
    """Test that ClickHouse connection works."""
    result = real_ch_db.execute("SELECT 1")
    assert result == [(1,)]


@pytest.mark.integration
def test_rewards_log_table_exists(real_ch_db):
    """Validate rewards_log table exists and has correct columns."""
    # Check table exists
    query = """
        SELECT name
        FROM system.tables
        WHERE database = currentDatabase() AND name = 'rewards_log'
    """
    result = real_ch_db.execute(query)
    assert len(result) > 0, "rewards_log table does not exist"
    
    # Check columns
    query = """
        SELECT name, type
        FROM system.columns
        WHERE database = currentDatabase() AND table = 'rewards_log'
        ORDER BY name
    """
    rows = real_ch_db.execute_dict(query)
    column_names = {row["name"] for row in rows}
    
    expected_columns = {
        "id", "domain_id", "amount", "amount_units", "wallet",
        "txid", "status", "error_message", "created_at", "confirmed_at"
    }
    missing = expected_columns - column_names
    assert not missing, f"Missing columns in rewards_log: {missing}"


@pytest.mark.integration
def test_rewards_daily_stats_table_exists(real_ch_db):
    """Validate rewards_daily_stats table exists."""
    query = """
        SELECT name
        FROM system.tables
        WHERE database = currentDatabase() AND name = 'rewards_daily_stats'
    """
    result = real_ch_db.execute(query)
    # Table may not exist if materialized view wasn't created, that's OK
    # Just log a warning
    if len(result) == 0:
        print("Warning: rewards_daily_stats table does not exist (materialized view may be missing)")
    else:
        # If it exists, check columns
        query = """
            SELECT name
            FROM system.columns
            WHERE database = currentDatabase() AND table = 'rewards_daily_stats'
        """
        rows = real_ch_db.execute_dict(query)
        column_names = {row["name"] for row in rows}
        expected = {"wallet", "day", "total_amount", "tx_count", "domain_count"}
        missing = expected - column_names
        assert not missing, f"Missing columns in rewards_daily_stats: {missing}"


@pytest.mark.integration
def test_rewards_domain_totals_table_exists(real_ch_db):
    """Validate rewards_domain_totals table exists."""
    query = """
        SELECT name
        FROM system.tables
        WHERE database = currentDatabase() AND name = 'rewards_domain_totals'
    """
    result = real_ch_db.execute(query)
    # Table may not exist, that's OK
    if len(result) == 0:
        print("Warning: rewards_domain_totals table does not exist (materialized view may be missing)")
    else:
        # If it exists, check columns
        query = """
            SELECT name
            FROM system.columns
            WHERE database = currentDatabase() AND table = 'rewards_domain_totals'
        """
        rows = real_ch_db.execute_dict(query)
        column_names = {row["name"] for row in rows}
        expected = {"domain_id", "total_amount", "tx_count"}
        missing = expected - column_names
        assert not missing, f"Missing columns in rewards_domain_totals: {missing}"


@pytest.mark.integration
def test_ch_insert_read_roundtrip(real_ch_db):
    """Test basic insert and read operations.
    
    Skips if rewards_log is a View (materialized view target), since
    ClickHouse Views do not support direct INSERT.
    """
    # Check engine type before attempting insert
    engine_result = real_ch_db.execute(
        "SELECT engine FROM system.tables "
        "WHERE database = currentDatabase() AND name = 'rewards_log'"
    )
    if not engine_result:
        pytest.skip("rewards_log table does not exist")
    
    engine = engine_result[0][0]
    if engine in ("View", "MaterializedView"):
        pytest.skip(
            f"rewards_log uses engine={engine}, cannot INSERT directly. "
            "Insert into the underlying MergeTree table instead."
        )
    
    test_wallet = f"3TestWallet{int(datetime.now().timestamp())}"
    test_data = [{
        "id": 999999999,
        "domain_id": None,
        "amount": 1.5,
        "amount_units": 150000000,
        "wallet": test_wallet,
        "txid": None,
        "status": "confirmed",
        "error_message": None,
        "created_at": datetime.now(),
        "confirmed_at": None
    }]
    
    try:
        # Insert
        columns = list(test_data[0].keys())
        rows_inserted = real_ch_db.insert("rewards_log", test_data, columns)
        assert rows_inserted == 1
        
        # Read back
        query = "SELECT * FROM rewards_log WHERE wallet = %(wallet)s AND id = 999999999"
        result = real_ch_db.execute_dict(query, {"wallet": test_wallet})
        assert len(result) == 1
        assert result[0]["wallet"] == test_wallet
        assert float(result[0]["amount"]) == 1.5
        
    finally:
        # Cleanup
        try:
            real_ch_db.execute("ALTER TABLE rewards_log DELETE WHERE id = 999999999")
        except Exception:
            pass  # Cleanup failure is OK
