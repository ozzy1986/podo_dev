"""
Unit tests for app.repositories.rating_repo – RatingRepository.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.rating_repo import RatingRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=0)
    return db


@pytest.fixture
def rating_repo(mock_db):
    return RatingRepository(mock_db)


class TestRatingRepository:
    """Tests for RatingRepository."""

    @pytest.mark.asyncio
    async def test_get_domains_rating_returns_paginated(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(page=1, per_page=10)
        assert "items" in result
        assert "total" in result
        assert result["page"] == 1
        assert result["per_page"] == 10

    @pytest.mark.asyncio
    async def test_get_domains_rating_by_registration_date(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating_by_registration_date(page=1, per_page=10)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_registrars_rating(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_registrars_rating()
        assert "items" in result
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_get_hosters_rating(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_hosters_rating()
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_zones_rating(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_zones_rating()
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_wallets_rating(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_wallets_rating(page=1, per_page=10)
        assert "items" in result or isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_domains_rating_with_sld_length_lt_18(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(sld_length=5)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_domains_rating_with_sld_length_gte_18(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(sld_length=20)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_domains_rating_with_registrar_id(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(registrar_id=1)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_domains_rating_with_hoster_id(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(hoster_id=1)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_domains_rating_with_zone(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating(zone="com")
        assert "items" in result

    @pytest.mark.asyncio
    async def test_get_domains_rating_by_registration_date_with_wallet(self, rating_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=0)
        mock_db.fetch = AsyncMock(return_value=[])
        result = await rating_repo.get_domains_rating_by_registration_date(wallet="3Nxxx")
        assert "items" in result
