"""
Unit tests for Ratings API endpoints with mocked dependencies.

The ratings endpoints create RatingRepository(get_pg_pool()) which receives
the mock_pg_db. We configure mock_pg_db.fetchval to return 0 (int) so that
the _paginated() helper doesn't fail on None / int division.
"""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_get_domains_rating(client, mock_pg_db):
    """Test GET /domains/rating endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/domains/rating?page=1&per_page=10")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "domains" in data


@pytest.mark.asyncio
async def test_get_domains_rating_filters(client, mock_pg_db):
    """Test GET /domains/rating with filters."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get(
        "/api/v1/domains/rating?wallet=3TestWallet123&sld_length=18&sort_by=weight"
    )

    assert response.status_code == 200
    data = response.json()
    assert "total" in data


@pytest.mark.asyncio
async def test_get_domains_rating_by_registration_date(client, mock_pg_db):
    """Test GET /domains/rating/by-registration-date endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/domains/rating/by-registration-date?sort_order=desc")

    assert response.status_code == 200
    data = response.json()
    assert "domains" in data


@pytest.mark.asyncio
async def test_get_registrars_rating(client, mock_pg_db):
    """Test GET /registrars/rating endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/registrars/rating")

    assert response.status_code == 200
    data = response.json()
    assert "registrars" in data


@pytest.mark.asyncio
async def test_get_hosters_rating(client, mock_pg_db):
    """Test GET /hosters/rating endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/hosters/rating")

    assert response.status_code == 200
    data = response.json()
    assert "hosters" in data


@pytest.mark.asyncio
async def test_get_zones_rating(client, mock_pg_db):
    """Test GET /zones/rating endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/zones/rating")

    assert response.status_code == 200
    data = response.json()
    assert "zones" in data


@pytest.mark.asyncio
async def test_get_wallets_rating(client, mock_pg_db):
    """Test GET /wallets/rating endpoint."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    response = client.get("/api/v1/wallets/rating?sort_by=rating&sort_order=desc")

    assert response.status_code == 200
    data = response.json()
    assert "wallets" in data


@pytest.mark.asyncio
async def test_ratings_no_auth_required(client, mock_pg_db):
    """Test that ratings endpoints don't require authentication."""
    mock_pg_db.fetchval = AsyncMock(return_value=0)
    mock_pg_db.fetch = AsyncMock(return_value=[])

    endpoints = [
        "/api/v1/domains/rating",
        "/api/v1/registrars/rating",
        "/api/v1/hosters/rating",
        "/api/v1/zones/rating",
        "/api/v1/wallets/rating",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        # Should not return 401 (unauthorized)
        assert response.status_code != 401, f"{endpoint} returned 401"
