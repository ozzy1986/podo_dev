"""
Unit tests for Stats API endpoints with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_stats(client, mock_ch_client):
    """Test GET /stats endpoint."""
    mock_ch_client.async_execute_dict = AsyncMock(return_value=[{
        "total_rewards": 1000,
        "total_distributed": 500.0,
        "unique_wallets": 50,
        "domains_rewarded": 25,
        "failed_transactions": 5,
    }])
    
    response = client.get("/api/v1/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert "total_domains" in data or "total_rewards_distributed" in data


@pytest.mark.asyncio
async def test_get_stats_error_handling(client, mock_ch_client):
    """Test GET /stats handles errors gracefully."""
    mock_ch_client.async_execute_dict = AsyncMock(side_effect=Exception("DB error"))
    
    response = client.get("/api/v1/stats")
    
    # Should return 200 with default values even on error
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_config(client):
    """Test GET /config endpoint."""
    response = client.get("/api/v1/config")
    
    assert response.status_code == 200
    data = response.json()
    assert "token_name" in data
    assert "token_decimals" in data
    assert "site_url" in data
    assert "debug" in data


@pytest.mark.asyncio
async def test_get_subscription_frequencies(client):
    """Test GET /subscription/frequencies endpoint."""
    response = client.get("/api/v1/subscription/frequencies")
    
    assert response.status_code == 200
    data = response.json()
    assert "frequencies" in data
    assert isinstance(data["frequencies"], list)
    assert len(data["frequencies"]) > 0
    
    # Check structure of first frequency
    freq = data["frequencies"][0]
    assert "id" in freq
    assert "label" in freq
    assert "minutes" in freq
