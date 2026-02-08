"""
Integration tests for RatingRepository against real PostgreSQL database.

Tests all 6 methods with real database operations.
"""

import pytest
import pytest_asyncio
from app.repositories.rating_repo import RatingRepository


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_domains_rating(real_pg_db, test_user):
    """Test getting domains rating."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_domains_rating(page=1, per_page=10)
    
    assert "items" in result
    assert "total" in result
    assert "page" in result
    assert "per_page" in result
    assert isinstance(result["items"], list)
    assert result["page"] == 1
    assert result["per_page"] == 10


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_domains_rating_with_filters(real_pg_db, test_user):
    """Test domains rating with filters."""
    repo = RatingRepository(real_pg_db)
    
    # Test with wallet filter
    result = await repo.get_domains_rating(
        page=1,
        per_page=10,
        wallet=test_user["wallet"]
    )
    assert "items" in result
    
    # Test with sld_length filter
    result = await repo.get_domains_rating(
        page=1,
        per_page=10,
        sld_length=18
    )
    assert "items" in result
    
    # Test with sort
    result = await repo.get_domains_rating(
        page=1,
        per_page=10,
        sort_by="weight",
        sort_order="asc"
    )
    assert "items" in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_domains_rating_by_registration_date(real_pg_db):
    """Test getting domains sorted by registration date."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_domains_rating_by_registration_date(
        page=1,
        per_page=10,
        sort_order="desc"
    )
    
    assert "items" in result
    assert "total" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_registrars_rating(real_pg_db):
    """Test getting registrars rating."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_registrars_rating(page=1, per_page=10)
    
    assert "items" in result
    assert "total" in result
    assert isinstance(result["items"], list)
    
    # May be empty if no registrars exist, that's OK
    if result["items"]:
        assert "id" in result["items"][0]
        assert "name" in result["items"][0]
        assert "total_earnings" in result["items"][0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_hosters_rating(real_pg_db):
    """Test getting hosters rating."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_hosters_rating(page=1, per_page=10)
    
    assert "items" in result
    assert "total" in result
    assert isinstance(result["items"], list)
    
    # May be empty if no hosters exist, that's OK
    if result["items"]:
        assert "id" in result["items"][0]
        assert "name" in result["items"][0]
        assert "total_earnings" in result["items"][0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_zones_rating(real_pg_db):
    """Test getting zones rating."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_zones_rating(page=1, per_page=10)
    
    assert "items" in result
    assert "total" in result
    assert isinstance(result["items"], list)
    
    # May be empty if no domains exist, that's OK
    if result["items"]:
        assert "zone" in result["items"][0]
        assert "total_earnings" in result["items"][0]
        assert "domains_count" in result["items"][0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_wallets_rating(real_pg_db):
    """Test getting wallets rating."""
    repo = RatingRepository(real_pg_db)
    
    result = await repo.get_wallets_rating(
        page=1,
        per_page=10,
        sort_by="rating",
        sort_order="desc"
    )
    
    assert "items" in result
    assert "total" in result
    assert isinstance(result["items"], list)
    
    # May be empty if no wallets exist, that's OK
    if result["items"]:
        assert "wallet" in result["items"][0]
        assert "domain_count" in result["items"][0]
        assert "total_earnings" in result["items"][0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rating_pagination(real_pg_db):
    """Test that pagination works correctly."""
    repo = RatingRepository(real_pg_db)
    
    page1 = await repo.get_domains_rating(page=1, per_page=5)
    page2 = await repo.get_domains_rating(page=2, per_page=5)
    
    assert page1["page"] == 1
    assert page2["page"] == 2
    assert page1["per_page"] == 5
    assert page2["per_page"] == 5
    
    # Items should be different (if enough domains exist)
    if page1["total"] > 5:
        page1_ids = {item["id"] for item in page1["items"]}
        page2_ids = {item["id"] for item in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids)
