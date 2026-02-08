"""
Unit tests for app.repositories.base – BaseRepository.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.base import BaseRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value="OK")
    return db


@pytest.fixture
def repo(mock_db):
    return BaseRepository(mock_db)


class TestBaseRepository:
    """Tests for BaseRepository."""

    @pytest.mark.asyncio
    async def test_fetch_one_returns_dict_when_row_exists(self, repo, mock_db):
        row = {"id": 1, "name": "x"}
        mock_db.fetchrow = AsyncMock(return_value=row)
        result = await repo.fetch_one("SELECT 1")
        assert result == row

    @pytest.mark.asyncio
    async def test_fetch_one_returns_none_when_no_row(self, repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await repo.fetch_one("SELECT 1")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_all_returns_list(self, repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[{"id": 1, "name": "a"}])
        result = await repo.fetch_all("SELECT * FROM t")
        assert len(result) == 1
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_fetch_val_returns_value(self, repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=42)
        result = await repo.fetch_val("SELECT 1")
        assert result == 42

    @pytest.mark.asyncio
    async def test_execute_returns_status(self, repo, mock_db):
        mock_db.execute = AsyncMock(return_value="INSERT 0 1")
        result = await repo.execute("INSERT INTO t VALUES (1)")
        assert "INSERT" in result

    @pytest.mark.asyncio
    async def test_exists_returns_true(self, repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=True)
        result = await repo.exists("users", "id = $1", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=False)
        result = await repo.exists("users", "id = $1", 999)
        assert result is False

    @pytest.mark.asyncio
    async def test_count_returns_number(self, repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=5)
        result = await repo.count("users")
        assert result == 5
