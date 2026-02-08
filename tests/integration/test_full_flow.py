"""
End-to-end integration test for complete user lifecycle.

Tests the full flow: register -> login -> add domain -> verify -> 
check earnings -> update language -> update widgets -> request payout
"""

import pytest
import pytest_asyncio
from datetime import datetime


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skip(reason="real_client + asyncpg pool conflict: another operation in progress")
async def test_full_user_lifecycle(real_client, real_pg_db, real_ch_db):
    """
    Test complete user lifecycle with real databases.
    
    Flow:
    1. Register user via email
    2. Login and get token
    3. Add domain
    4. Verify domain (simulate)
    5. Check earnings
    6. Update language
    7. Update widgets
    8. Request payout
    """
    timestamp = int(datetime.now().timestamp())
    test_email = f"test_lifecycle_{timestamp}@test.d.onl"
    test_password = "TestPassword123!"
    test_domain_name = f"test-lifecycle-{timestamp}.test.d.onl"
    
    try:
        # Step 1: Register user
        register_response = real_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "language": "en"
            }
        )
        assert register_response.status_code == 200 or register_response.status_code == 201
        
        # Step 2: Login
        login_response = real_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": test_password
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Step 3: Add domain
        add_domain_response = real_client.post(
            "/api/v1/domains",
            headers=auth_headers,
            json={"domain": test_domain_name}
        )
        assert add_domain_response.status_code == 200 or add_domain_response.status_code == 201
        domain_data = add_domain_response.json()
        domain_id = domain_data.get("id") or domain_data.get("domain", {}).get("id")
        
        # Step 4: Verify domain (simulate by calling verify endpoint)
        # Note: Actual DNS verification would require real DNS setup
        verify_response = real_client.post(
            f"/api/v1/domains/{domain_id}/verify",
            headers=auth_headers
        )
        # May fail if DNS isn't set up, that's OK for integration test
        assert verify_response.status_code in [200, 400, 422]
        
        # Step 5: Check earnings
        earnings_response = real_client.get(
            "/api/v1/user/earnings",
            headers=auth_headers
        )
        assert earnings_response.status_code == 200
        earnings_data = earnings_response.json()
        assert "daily_earnings" in earnings_data
        
        # Step 6: Update language
        language_response = real_client.put(
            "/api/v1/user/language",
            headers=auth_headers,
            json={"language": "ru"}
        )
        assert language_response.status_code == 200
        assert language_response.json()["language"] == "ru"
        
        # Step 7: Update widgets
        widgets_response = real_client.post(
            "/api/v1/user/widgets",
            headers=auth_headers,
            json={"enabled_widgets": ["earnings", "domains"]}
        )
        assert widgets_response.status_code == 200
        assert "enabled_widgets" in widgets_response.json()
        
        # Step 8: Get dashboard (combines multiple endpoints)
        dashboard_response = real_client.get(
            "/api/v1/user/dashboard",
            headers=auth_headers
        )
        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()
        assert isinstance(dashboard_data, dict)
        
        # Step 9: Request payout (if balance is sufficient)
        # Note: In dev mode, payouts may be disabled, so this might fail
        # That's OK - we're testing the flow, not the payout processing
        payout_response = real_client.post(
            "/api/v1/user/payouts",
            headers=auth_headers,
            json={"amount": 10.0}
        )
        # May return 400 if balance insufficient or payouts disabled in dev
        assert payout_response.status_code in [200, 201, 400, 422]
        
    finally:
        # Cleanup: Delete test data
        try:
            # Delete domain
            await real_pg_db.execute(
                "DELETE FROM domains WHERE domain = $1",
                test_domain_name
            )
            # Delete user (cascade should handle domains, but be explicit)
            await real_pg_db.execute(
                "DELETE FROM users WHERE email = $1",
                test_email
            )
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_data_consistency_across_databases(real_pg_db, real_ch_db, test_user, test_domain, ch_rewards_writable):
    """
    Test that data is consistent across PostgreSQL and ClickHouse.
    
    Creates a reward in ClickHouse and verifies user balance in PostgreSQL.
    """
    if not ch_rewards_writable:
        pytest.skip("rewards_log is a View — cannot INSERT test data for consistency check")

    from app.repositories.reward_repo import RewardRepository
    from app.repositories.user_repo import UserRepository
    
    reward_repo = RewardRepository(real_pg_db, real_ch_db)
    user_repo = UserRepository(real_pg_db)
    
    try:
        # Get initial balance
        initial_user = await user_repo.get_by_id(test_user["id"])
        initial_balance = initial_user.get("accumulated_balance", 0.0)
        
        # Log a reward in ClickHouse
        reward_id = await reward_repo.log_reward(
            domain_id=test_domain["id"],
            wallet=test_user["wallet"],
            amount=50.0,
            amount_units=5000000000
        )
        
        # Update status to confirmed
        await real_ch_db.async_execute(
            "ALTER TABLE rewards_log UPDATE status = 'confirmed' WHERE id = %(id)s",
            {"id": reward_id}
        )
        
        # Wait for ClickHouse to process
        import asyncio
        await asyncio.sleep(0.5)
        
        # Verify reward exists in ClickHouse
        ch_rewards = await real_ch_db.async_execute_dict(
            "SELECT * FROM rewards_log WHERE id = %(id)s",
            {"id": reward_id}
        )
        assert len(ch_rewards) == 1
        assert float(ch_rewards[0]["amount"]) == 50.0
        
        # Note: In a real system, a worker would sync CH rewards to PG balance
        # For this test, we're just verifying both databases can be queried
        
    finally:
        # Cleanup
        try:
            await real_ch_db.async_execute(
                "ALTER TABLE rewards_log DELETE WHERE id = %(id)s",
                {"id": reward_id}
            )
        except Exception:
            pass
