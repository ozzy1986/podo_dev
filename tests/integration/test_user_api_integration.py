"""
Integration tests for User API endpoints against real databases.

Tests all user endpoints end-to-end with real PostgreSQL and ClickHouse.
Uses async_client so the app runs in the same event loop as the test.
"""

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_get_user_domains_integration(async_client, auth_headers, test_user, test_domain):
    """Test GET /user/domains with real database."""
    response = await async_client.get(
        "/api/v1/user/domains?page=1&per_page=10", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "domains" in data
    assert isinstance(data["domains"], list)
    domain_names = [d["domain"] for d in data["domains"]]
    assert test_domain["domain"] in domain_names


@pytest.mark.asyncio
async def test_get_user_stats_integration(async_client, auth_headers, test_user):
    """Test GET /user/stats with real database."""
    response = await async_client.get("/api/v1/user/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_domains" in data
    assert "mining_domains" in data
    assert "accumulated_balance" in data
    assert "wallet" in data


@pytest.mark.asyncio
async def test_get_user_balance_integration(async_client, auth_headers, test_user):
    """Test GET /user/balance with real database."""
    response = await async_client.get("/api/v1/user/balance", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "balance" in data or "accumulated_balance" in data
    assert "payout_mode" in data


@pytest.mark.asyncio
async def test_get_user_language_integration(async_client, auth_headers, test_user):
    """Test GET /user/language with real database."""
    response = await async_client.get("/api/v1/user/language", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "language" in data
    assert data["language"] in ["en", "ru", "ar"]


@pytest.mark.asyncio
async def test_update_user_language_integration(async_client, auth_headers, test_user):
    """Test PUT /user/language with real database."""
    response = await async_client.put(
        "/api/v1/user/language",
        headers=auth_headers,
        json={"language": "ru"}
    )
    assert response.status_code == 200
    assert response.json()["language"] == "ru"
    get_response = await async_client.get("/api/v1/user/language", headers=auth_headers)
    assert get_response.json()["language"] == "ru"


@pytest.mark.asyncio
async def test_get_user_widgets_integration(async_client, auth_headers, test_user):
    """Test GET /user/widgets with real database."""
    response = await async_client.get("/api/v1/user/widgets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "enabled_widgets" in data


@pytest.mark.asyncio
async def test_set_user_widgets_integration(async_client, auth_headers, test_user):
    """Test POST /user/widgets with real database."""
    widgets = ["earnings", "domains", "stats"]
    response = await async_client.post(
        "/api/v1/user/widgets",
        headers=auth_headers,
        json={"enabled_widgets": widgets}
    )
    assert response.status_code == 200
    assert response.json()["enabled_widgets"] == widgets
    get_response = await async_client.get("/api/v1/user/widgets", headers=auth_headers)
    assert set(get_response.json()["enabled_widgets"]) == set(widgets)


@pytest.mark.asyncio
async def test_get_user_rewards_integration(async_client, auth_headers, test_user):
    """Test GET /user/rewards with real database."""
    response = await async_client.get("/api/v1/user/rewards", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "rewards" in data or isinstance(data, list)


@pytest.mark.asyncio
async def test_get_user_payouts_integration(async_client, auth_headers, test_user):
    """Test GET /user/payouts with real database."""
    response = await async_client.get("/api/v1/user/payouts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "payouts" in data or isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_user_domains_health_integration(
    async_client, auth_headers, test_user, test_domain
):
    """Test GET /user/domains/health with real database."""
    response = await async_client.get(
        "/api/v1/user/domains/health", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "healthy" in data or "expiring_soon" in data or "failed_checks" in data


@pytest.mark.asyncio
async def test_get_user_earnings_integration(async_client, auth_headers, test_user):
    """Test GET /user/earnings with real database."""
    response = await async_client.get("/api/v1/user/earnings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "daily_earnings" in data
    assert "weekly_earnings" in data
    assert "avg_daily" in data
    assert "avg_weekly" in data


@pytest.mark.asyncio
async def test_get_user_dashboard_integration(async_client, auth_headers, test_user):
    """Test GET /user/dashboard with real database."""
    response = await async_client.get("/api/v1/user/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "balance" in data or "stats" in data or "domains" in data


@pytest.mark.asyncio
async def test_user_api_unauthorized(async_client):
    """Test that user endpoints require authentication."""
    endpoints = [
        "/api/v1/user/domains",
        "/api/v1/user/stats",
        "/api/v1/user/balance",
        "/api/v1/user/widgets",
        "/api/v1/user/rewards",
    ]
    for endpoint in endpoints:
        response = await async_client.get(endpoint)
        assert response.status_code == 401, f"{endpoint} should require auth"
