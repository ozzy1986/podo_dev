"""
Unit tests for app.api.deps – dependency injection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.deps import (
    get_app_settings,
    get_db,
    get_ch,
    get_user_repo,
    get_domain_repo,
    get_reward_repo,
    get_payout_repo,
    get_ssl_repo,
    get_security,
    get_auth_service,
    get_user_service,
    get_domain_service,
    get_dns_service,
    get_current_user,
    get_current_user_optional,
)


class TestDeps:
    """Tests for dependency functions."""

    def test_get_app_settings_returns_settings(self):
        result = get_app_settings()
        assert result is not None
        assert hasattr(result, "app_env")

    def test_get_db_raises_when_not_initialized(self):
        import app.db.postgresql as mod
        orig = mod._pg_db
        mod._pg_db = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_db()
        finally:
            mod._pg_db = orig

    def test_get_ch_raises_when_not_initialized(self):
        import app.db.clickhouse as mod
        orig = mod._ch_db
        mod._ch_db = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_ch()
        finally:
            mod._ch_db = orig

    def test_get_user_repo_returns_repository(self, mock_pg_db):
        repo = get_user_repo(db=mock_pg_db)
        assert repo is not None
        assert hasattr(repo, "get_by_id")

    def test_get_domain_repo_returns_repository(self, mock_pg_db):
        repo = get_domain_repo(db=mock_pg_db)
        assert repo is not None

    def test_get_reward_repo_returns_repository(self, mock_pg_db, mock_ch_client):
        repo = get_reward_repo(db=mock_pg_db, ch=mock_ch_client)
        assert repo is not None

    def test_get_payout_repo_returns_repository(self, mock_pg_db):
        repo = get_payout_repo(db=mock_pg_db)
        assert repo is not None

    def test_get_ssl_repo_returns_repository(self, mock_pg_db):
        repo = get_ssl_repo(db=mock_pg_db)
        assert repo is not None

    def test_get_security_returns_security_manager(self):
        settings = MagicMock()
        settings.security = MagicMock()
        sm = get_security(settings=settings)
        assert sm is not None

    def test_get_auth_service_returns_service(self, mock_user_repo):
        security = MagicMock()
        svc = get_auth_service(user_repo=mock_user_repo, security=security)
        assert svc is not None

    def test_get_user_service_returns_service(self, mock_user_repo, mock_domain_repo):
        svc = get_user_service(user_repo=mock_user_repo, domain_repo=mock_domain_repo)
        assert svc is not None

    def test_get_domain_service_returns_service(self, mock_domain_repo, mock_user_repo):
        settings = MagicMock()
        settings.domain = MagicMock()
        svc = get_domain_service(
            domain_repo=mock_domain_repo,
            user_repo=mock_user_repo,
            settings=settings,
        )
        assert svc is not None

    def test_get_dns_service_returns_service(self):
        settings = MagicMock()
        settings.dns = MagicMock()
        svc = get_dns_service(settings=settings)
        assert svc is not None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_none_when_no_token(self):
        auth_svc = MagicMock()
        result = await get_current_user_optional(
            authorization=None,
            x_auth_token=None,
            auth_service=auth_svc,
        )
        assert result is None
        auth_svc.get_current_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_user_when_valid_token(self):
        auth_svc = MagicMock()
        auth_svc.get_current_user = AsyncMock(return_value={"id": 1, "email": "u@x.com"})
        result = await get_current_user_optional(
            authorization="Bearer valid-token",
            x_auth_token=None,
            auth_service=auth_svc,
        )
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_current_user_optional_uses_x_auth_token_when_no_bearer(self):
        auth_svc = MagicMock()
        auth_svc.get_current_user = AsyncMock(return_value={"id": 2})
        result = await get_current_user_optional(
            authorization=None,
            x_auth_token="alt-token",
            auth_service=auth_svc,
        )
        assert result["id"] == 2

    @pytest.mark.asyncio
    async def test_get_current_user_raises_when_no_token(self):
        with pytest.raises(HTTPException, match="Missing"):
            await get_current_user(
                authorization=None,
                x_auth_token=None,
                auth_service=MagicMock(),
            )

    @pytest.mark.asyncio
    async def test_get_current_user_uses_bearer_token(self):
        auth_svc = MagicMock()
        auth_svc.get_current_user = AsyncMock(return_value={"id": 1, "email": "u@x.com"})
        result = await get_current_user(
            authorization="Bearer my-token",
            x_auth_token=None,
            auth_service=auth_svc,
        )
        assert result["id"] == 1
        auth_svc.get_current_user.assert_called_once_with("my-token")

    @pytest.mark.asyncio
    async def test_get_current_user_raises_on_auth_error(self):
        from app.core.exceptions import AuthError
        auth_svc = MagicMock()
        auth_svc.get_current_user = AsyncMock(side_effect=AuthError("Token expired"))
        with pytest.raises(HTTPException, match="Token expired"):
            await get_current_user(
                authorization="Bearer bad",
                x_auth_token=None,
                auth_service=auth_svc,
            )
