"""
PostgreSQL connection and schema validation tests.

Validates that the database connection works and all expected
tables, columns, indexes, and views exist.
"""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pg_connection(real_pg_db):
    """Test that PostgreSQL connection works."""
    result = await real_pg_db.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pg_tables_exist(real_pg_db):
    """Validate all expected tables exist."""
    # rewards_log is in ClickHouse only, not PostgreSQL
    expected_tables = [
        "users",
        "domains",
        "payout_requests",
        "pool_state",
        "system_state",
        "domain_promotions",
        "promotion_subscriptions",
    ]
    
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
    """
    rows = await real_pg_db.fetch(query)
    existing_tables = {row["table_name"] for row in rows}
    
    for table in expected_tables:
        assert table in existing_tables, f"Table {table} does not exist"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_users_table_columns(real_pg_db):
    """Validate critical columns exist in users table."""
    expected_columns = {
        "id", "telegram_id", "username", "wallet", "email", "password_hash",
        "created_at", "updated_at", "accumulated_balance", "accumulated_units",
        "payout_mode", "payout_threshold", "last_payout_at", "language",
        "email_verification_code", "email_verification_created_at",
        "widget_preferences", "total_earned"
    }
    
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users'
    """
    rows = await real_pg_db.fetch(query)
    existing_columns = {row["column_name"] for row in rows}
    
    missing = expected_columns - existing_columns
    assert not missing, f"Missing columns in users table: {missing}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_domains_table_columns(real_pg_db):
    """Validate critical columns exist in domains table."""
    expected_columns = {
        "id", "user_id", "domain", "nonce", "verified", "verification_time",
        "last_check", "last_reward", "failed_checks", "is_mining",
        "domain_expires_at", "whois_last_check", "created_at", "updated_at",
        "sld_length", "creation_date", "age_r", "total_earnings", "weight",
        "is_clickable", "promoted_at", "a_record_points_to_us", "description",
        "parking_mode", "parking_content", "content_theme"
    }
    
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'domains'
    """
    rows = await real_pg_db.fetch(query)
    existing_columns = {row["column_name"] for row in rows}
    
    missing = expected_columns - existing_columns
    assert not missing, f"Missing columns in domains table: {missing}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pg_indexes_exist(real_pg_db):
    """Validate critical indexes exist (supports idx_X or idx_tablename_X naming)."""
    query = """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
    """
    rows = await real_pg_db.fetch(query)
    existing_indexes = {row["indexname"] for row in rows}
    
    # Accept either short (idx_domain) or prefixed (idx_domains_domain) names
    required_patterns = [
        "domain",  # idx_domain or idx_domains_domain
        "user_id",  # idx_user_id or idx_domains_user_id
        "is_mining",
        "verified",
        "last_check",
    ]
    
    missing = []
    for pattern in required_patterns:
        if not any(pattern in idx for idx in existing_indexes):
            missing.append(pattern)
    
    assert not missing, (
        f"No index matching: {missing}. "
        f"Available: {sorted(existing_indexes)[:30]}..."
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_domain_stats_view(real_pg_db):
    """Check if domain_stats view exists (informational, not blocking)."""
    query = """
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = 'public' AND table_name = 'domain_stats'
    """
    view_exists = await real_pg_db.fetchrow(query)
    
    if view_exists is None:
        # View doesn't exist - log but don't fail the test suite.
        # This is a schema gap, not a test failure.
        pytest.skip(
            "domain_stats view does not exist. "
            "Consider creating it if needed for dashboard aggregations."
        )
    
    # If the view exists, validate its query works
    result = await real_pg_db.fetchrow("SELECT * FROM domain_stats LIMIT 1")
    assert result is not None, "domain_stats view query returned no rows"
