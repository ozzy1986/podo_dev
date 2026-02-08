"""
Unit tests for app.repositories.user_repo – UserRepository with mocked DB.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.repositories.user_repo import UserRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value="OK")
    return db


@pytest.fixture
def user_repo(mock_db):
    return UserRepository(mock_db)


class TestUserRepoCreate:
    @pytest.mark.asyncio
    async def test_create_with_wallet(self, user_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=False)
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "wallet": "3Nxxx", "email": None})
        result = await user_repo.create(wallet_address="3Nxxx")
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_create_with_email(self, user_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=False)
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "email": "u@x.com", "wallet": None})
        result = await user_repo.create(email="u@x.com", password_hash="hash", language="en")
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_create_raises_when_wallet_exists(self, user_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=True)
        with pytest.raises(ConflictError, match="wallet"):
            await user_repo.create(wallet_address="3Ndup")

    @pytest.mark.asyncio
    async def test_create_raises_when_email_exists(self, user_repo, mock_db):
        mock_db.fetchval = AsyncMock(return_value=True)
        with pytest.raises(ConflictError, match="email"):
            await user_repo.create(email="dup@x.com", password_hash="h")

    @pytest.mark.asyncio
    async def test_create_raises_when_telegram_id_exists(self, user_repo, mock_db):
        mock_db.fetchval = AsyncMock(side_effect=[False, False, True])
        with pytest.raises(ConflictError, match="telegram_id"):
            await user_repo.create(wallet_address="3Nx", email="u@x.com", telegram_id=123456)


class TestUserRepoGetBy:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_user(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "email": "u@x.com"})
        result = await user_repo.get_by_id(1)
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        result = await user_repo.get_by_id(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_wallet_returns_user(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "wallet": "3Nxxx"})
        result = await user_repo.get_by_wallet("3Nxxx")
        assert result["wallet"] == "3Nxxx"

    @pytest.mark.asyncio
    async def test_get_by_email_returns_user(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "email": "u@x.com"})
        result = await user_repo.get_by_email("u@x.com")
        assert result["email"] == "u@x.com"

    @pytest.mark.asyncio
    async def test_get_by_telegram_id_returns_user(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "telegram_id": 123456})
        result = await user_repo.get_by_telegram_id(123456)
        assert result["telegram_id"] == 123456


class TestUserRepoUpdate:
    @pytest.mark.asyncio
    async def test_update_wallet(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(side_effect=[None, {"id": 1, "wallet": "3Nnew"}])
        result = await user_repo.update_wallet(1, "3Nnew")
        assert result["wallet"] == "3Nnew"

    @pytest.mark.asyncio
    async def test_update_wallet_raises_conflict_when_in_use(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 99})
        with pytest.raises(ConflictError, match="already in use"):
            await user_repo.update_wallet(1, "3Ntaken")

    @pytest.mark.asyncio
    async def test_update_wallet_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(side_effect=[None, None])
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.update_wallet(999, "3Nnew")

    @pytest.mark.asyncio
    async def test_update_balance(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "accumulated_balance": 50.0, "accumulated_units": 500})
        result = await user_repo.update_balance(1, 10.0, 100)
        assert result["accumulated_balance"] == 50.0

    @pytest.mark.asyncio
    async def test_update_balance_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.update_balance(999, 10.0, 100)

    @pytest.mark.asyncio
    async def test_update_language(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "language": "ru"})
        result = await user_repo.update_language(1, "ru")
        assert result["language"] == "ru"

    @pytest.mark.asyncio
    async def test_update_language_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.update_language(999, "ru")

    @pytest.mark.asyncio
    async def test_update_payout_settings(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "payout_mode": "auto", "payout_threshold": 100})
        result = await user_repo.update_payout_settings(1, "auto", 100.0)
        assert result["payout_mode"] == "auto"

    @pytest.mark.asyncio
    async def test_update_payout_settings_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.update_payout_settings(999, "auto", 100.0)

    @pytest.mark.asyncio
    async def test_verify_email(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "email_verified": True})
        result = await user_repo.verify_email(1)
        assert result["email_verified"] is True

    @pytest.mark.asyncio
    async def test_verify_email_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.verify_email(999)

    @pytest.mark.asyncio
    async def test_update_widget_preferences(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value={"id": 1, "widget_preferences": "{}"})
        result = await user_repo.update_widget_preferences(1, "{}")
        assert result["widget_preferences"] == "{}"

    @pytest.mark.asyncio
    async def test_update_widget_preferences_raises_not_found(self, user_repo, mock_db):
        mock_db.fetchrow = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await user_repo.update_widget_preferences(999, "{}")


class TestUserRepoAutoPayout:
    @pytest.mark.asyncio
    async def test_get_users_for_auto_payout(self, user_repo, mock_db):
        users = [{"id": 1, "wallet": "3Nx", "accumulated_balance": 50.0}]
        mock_db.fetch = AsyncMock(return_value=users)
        result = await user_repo.get_users_for_auto_payout(10.0)
        assert result == users
