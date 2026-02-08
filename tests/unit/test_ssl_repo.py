"""
Unit tests for app.repositories.ssl_repo – SSLRepository.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.repositories.ssl_repo import SSLRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.execute = AsyncMock(return_value="INSERT 0 1")
    return db


@pytest.fixture
def ssl_repo(mock_db):
    return SSLRepository(mock_db)


class TestSSLRepository:
    """Tests for SSLRepository."""

    @pytest.mark.asyncio
    async def test_create_returns_cert_dict(self, ssl_repo, mock_db):
        row = {"domain": "example.com", "cert_path": "/certs/x", "status": "active"}
        mock_db.fetchrow = AsyncMock(return_value=row)
        result = await ssl_repo.create("example.com", "/certs/x.pem", "/certs/x.key")
        assert result["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_get_by_domain_returns_none(self, ssl_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await ssl_repo.get_by_domain("unknown.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_certificates(self, ssl_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await ssl_repo.get_active_certificates()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_expiring_soon(self, ssl_repo, mock_db):
        mock_db.fetch = AsyncMock(return_value=[])
        result = await ssl_repo.get_expiring_soon(days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_update_status_raises_when_not_found(self, ssl_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await ssl_repo.update_status("x.com", "expired")

    @pytest.mark.asyncio
    async def test_update_status_returns_row(self, ssl_repo, mock_db):
        row = {"domain": "x.com", "status": "expired"}
        mock_db.fetchrow = AsyncMock(return_value=row)
        result = await ssl_repo.update_status("x.com", "expired")
        assert result["domain"] == "x.com"

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self, ssl_repo, mock_db):
        mock_db.execute = AsyncMock(return_value="DELETE 1")
        result = await ssl_repo.delete("x.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, ssl_repo, mock_db):
        mock_db.execute = AsyncMock(return_value="DELETE 0")
        result = await ssl_repo.delete("x.com")
        assert result is False
