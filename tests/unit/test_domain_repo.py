"""
Unit tests for app.repositories.domain_repo – DomainRepository.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.domain_repo import DomainRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value="OK")
    return db


@pytest.fixture
def domain_repo(mock_db):
    return DomainRepository(mock_db)


class TestDomainRepository:
    """Tests for DomainRepository."""

    @pytest.mark.asyncio
    async def test_create_raises_when_domain_exists(self, domain_repo, mock_db):
        with patch.object(domain_repo, "exists", new_callable=AsyncMock, return_value=True):
            with pytest.raises(ConflictError, match="already exists"):
                await domain_repo.create(1, "x.com", "x", "com", 1, "nonce")

    @pytest.mark.asyncio
    async def test_create_returns_domain(self, domain_repo, mock_db):
        with patch.object(domain_repo, "exists", new_callable=AsyncMock, return_value=False):
            mock_db.fetchrow = AsyncMock(return_value={"id": 1, "domain": "x.com", "user_id": 1})
            result = await domain_repo.create(1, "x.com", "x", "com", 1, "nonce")
            assert result["domain"] == "x.com"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await domain_repo.get_by_id(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_domain_returns_none(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await domain_repo.get_by_domain("unknown.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_domains_returns_list(self, domain_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await domain_repo.get_user_domains(1)
        assert result == []

    @pytest.mark.asyncio
    async def test_count_user_domains(self, domain_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=3)
        result = await domain_repo.count_user_domains(1)
        assert result == 3

    @pytest.mark.asyncio
    async def test_verify_domain_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "verified": True}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.verify_domain(1)
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_verify_domain_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.verify_domain(999)

    @pytest.mark.asyncio
    async def test_start_mining_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "is_mining": True}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.start_mining(1)
        assert result["is_mining"] is True

    @pytest.mark.asyncio
    async def test_start_mining_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.start_mining(999)

    @pytest.mark.asyncio
    async def test_stop_mining_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "is_mining": False}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.stop_mining(1, reason="manual")
        assert result["is_mining"] is False

    @pytest.mark.asyncio
    async def test_stop_mining_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.stop_mining(999)

    @pytest.mark.asyncio
    async def test_update_check_status_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "verified": True, "failed_checks": 0}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.update_check_status(1, True, 0)
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_update_check_status_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.update_check_status(999, True, 0)

    @pytest.mark.asyncio
    async def test_update_a_record_status_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "a_record_points_to_us": True}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.update_a_record_status(1, True)
        assert result["a_record_points_to_us"] is True

    @pytest.mark.asyncio
    async def test_update_a_record_status_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.update_a_record_status(999, True)

    @pytest.mark.asyncio
    async def test_update_description_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "description": "New desc"}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.update_description(1, "New desc")
        assert result["description"] == "New desc"

    @pytest.mark.asyncio
    async def test_update_description_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.update_description(999, "desc")

    @pytest.mark.asyncio
    async def test_update_parking_content_returns_updated(self, domain_repo, mock_db):
        updated = {"id": 1, "parking_content": "<html>", "parking_mode": "non_redirect"}
        mock_db.fetchrow = AsyncMock(return_value=updated)
        result = await domain_repo.update_parking_content(1, "<html>", "non_redirect")
        assert result["parking_mode"] == "non_redirect"

    @pytest.mark.asyncio
    async def test_update_parking_content_raises_when_not_found(self, domain_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_repo.update_parking_content(999, "<html>", "non_redirect")

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self, domain_repo, mock_db):
        mock_db.execute = AsyncMock(return_value="DELETE 1")
        result = await domain_repo.delete(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, domain_repo, mock_db):
        mock_db.execute = AsyncMock(return_value="DELETE 0")
        result = await domain_repo.delete(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_mining_domains(self, domain_repo, mock_db):
        rows = [{"id": 1, "domain": "x.com", "is_mining": True}]
        mock_db.fetch = AsyncMock(return_value=rows)
        result = await domain_repo.get_mining_domains(10)
        assert len(result) == 1
        assert result[0]["domain"] == "x.com"

    @pytest.mark.asyncio
    async def test_get_domains_needing_check(self, domain_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await domain_repo.get_domains_needing_check(12)
        assert result == []
