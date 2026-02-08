"""
Unit tests for app.repositories.payout_repo – PayoutRepository.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.repositories.payout_repo import PayoutRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=0.0)
    db.execute = AsyncMock(return_value="OK")
    return db


@pytest.fixture
def payout_repo(mock_db):
    return PayoutRepository(mock_db)


class TestPayoutRepository:
    """Tests for PayoutRepository."""

    @pytest.mark.asyncio
    async def test_create_request_returns_payout(self, payout_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "status": "pending"})
        result = await payout_repo.create_request(1, "3Nxxx", 1.0, 100000000)
        assert "id" in result or "status" in result

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(self, payout_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await payout_repo.get_by_id(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pending_requests(self, payout_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await payout_repo.get_pending_requests()
        assert result == []

    @pytest.mark.asyncio
    async def test_update_status_raises_when_not_found(self, payout_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await payout_repo.update_status(999, "completed")

    @pytest.mark.asyncio
    async def test_update_status_returns_row(self, payout_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "status": "completed"})
        result = await payout_repo.update_status(1, "completed", tx_id="tx1")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_user_payout_history(self, payout_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await payout_repo.get_user_payout_history(1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_total_paid_out_with_user(self, payout_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=10.5)
        result = await payout_repo.get_total_paid_out(user_id=1)
        assert result == 10.5

    @pytest.mark.asyncio
    async def test_get_total_paid_out_global(self, payout_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=100.0)
        result = await payout_repo.get_total_paid_out()
        assert result == 100.0
