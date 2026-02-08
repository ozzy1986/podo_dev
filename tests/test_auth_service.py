"""
Unit tests for app.services.auth_service – AuthService.

All repository calls are mocked; no database required.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.auth_service import AuthService
from app.core.security import SecurityManager
from app.core.exceptions import AuthError, NotFoundError, ValidationError, ConflictError


# ---------------------------------------------------------------------------
# register_with_email
# ---------------------------------------------------------------------------

class TestRegisterWithEmail:

    @pytest.mark.asyncio
    async def test_success(self, auth_service, mock_user_repo, sample_user, security_manager):
        """Successful registration returns user + tokens."""
        created_user = {**sample_user, "email": "new@example.com"}
        mock_user_repo.create.return_value = created_user

        result = await auth_service.register_with_email(
            email="new@example.com",
            password="strongpassword",
            language="en",
        )

        assert "user" in result
        assert "token" in result
        assert "refresh_token" in result
        assert result["user"]["email"] == "new@example.com"
        mock_user_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_email(self, auth_service, mock_user_repo):
        """ConflictError from repo propagates up."""
        mock_user_repo.create.side_effect = ConflictError("User with email exists")

        with pytest.raises(ConflictError, match="email"):
            await auth_service.register_with_email(
                email="dup@example.com",
                password="strongpassword",
            )

    @pytest.mark.asyncio
    async def test_invalid_email_raises_validation(self, auth_service):
        with pytest.raises(ValidationError, match="Invalid email"):
            await auth_service.register_with_email(email="not-an-email", password="12345678")

    @pytest.mark.asyncio
    async def test_short_password_raises_validation(self, auth_service):
        with pytest.raises(ValidationError, match="at least 8"):
            await auth_service.register_with_email(email="a@b.com", password="short")

    @pytest.mark.asyncio
    async def test_empty_email_raises_validation(self, auth_service):
        with pytest.raises(ValidationError, match="Invalid email"):
            await auth_service.register_with_email(email="", password="12345678")


# ---------------------------------------------------------------------------
# login_with_email
# ---------------------------------------------------------------------------

class TestLoginWithEmail:

    @pytest.mark.asyncio
    async def test_success(self, auth_service, mock_user_repo, sample_user, security_manager):
        """Valid credentials return user + tokens."""
        hashed = security_manager.hash_password("correct_pw")
        user_with_pw = {**sample_user, "password_hash": hashed}
        mock_user_repo.get_by_email.return_value = user_with_pw

        result = await auth_service.login_with_email("user@example.com", "correct_pw")

        assert result["user"]["id"] == sample_user["id"]
        assert "token" in result
        assert "refresh_token" in result

    @pytest.mark.asyncio
    async def test_wrong_password(self, auth_service, mock_user_repo, sample_user, security_manager):
        hashed = security_manager.hash_password("correct_pw")
        mock_user_repo.get_by_email.return_value = {**sample_user, "password_hash": hashed}

        with pytest.raises(AuthError, match="Invalid email or password"):
            await auth_service.login_with_email("user@example.com", "wrong_pw")

    @pytest.mark.asyncio
    async def test_user_not_found(self, auth_service, mock_user_repo):
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(AuthError, match="Invalid email or password"):
            await auth_service.login_with_email("nobody@example.com", "whatever")

    @pytest.mark.asyncio
    async def test_no_password_hash(self, auth_service, mock_user_repo, sample_user):
        """User registered via wallet only – no password_hash."""
        mock_user_repo.get_by_email.return_value = {**sample_user, "password_hash": None}

        with pytest.raises(AuthError, match="not available"):
            await auth_service.login_with_email("user@example.com", "pw")


# ---------------------------------------------------------------------------
# login_with_wallet
# ---------------------------------------------------------------------------

class TestLoginWithWallet:

    @pytest.mark.asyncio
    async def test_success_existing_user(self, auth_service, mock_user_repo, sample_user, security_manager):
        """Existing wallet user logs in successfully."""
        with patch.object(security_manager, "verify_waves_signature", return_value=True):
            mock_user_repo.get_by_wallet.return_value = sample_user

            result = await auth_service.login_with_wallet(
                wallet_address="3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
                signature="fakesig",
                public_key="fakepub",
                message="login",
            )

            assert result["user"]["id"] == sample_user["id"]
            mock_user_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_success_new_user(self, auth_service, mock_user_repo, sample_user, security_manager):
        """First-time wallet login creates the user automatically."""
        with patch.object(security_manager, "verify_waves_signature", return_value=True):
            mock_user_repo.get_by_wallet.return_value = None
            mock_user_repo.create.return_value = sample_user

            result = await auth_service.login_with_wallet(
                wallet_address="3Pnewwallet12345678901234567890ab",
                signature="fakesig",
                public_key="fakepub",
                message="login",
            )

            assert "token" in result
            mock_user_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_signature(self, auth_service, security_manager):
        with patch.object(security_manager, "verify_waves_signature", return_value=False):
            with pytest.raises(AuthError, match="Invalid signature"):
                await auth_service.login_with_wallet(
                    wallet_address="3Pxxx",
                    signature="badsig",
                    public_key="badpub",
                    message="login",
                )


# ---------------------------------------------------------------------------
# refresh_tokens
# ---------------------------------------------------------------------------

class TestRefreshTokens:

    @pytest.mark.asyncio
    async def test_success(self, auth_service, mock_user_repo, sample_user, security_manager):
        """Valid refresh token returns new token pair."""
        refresh_tok = security_manager.create_jwt_token(user_id=1, token_type="refresh")
        mock_user_repo.get_by_id.return_value = sample_user

        result = await auth_service.refresh_tokens(refresh_tok)

        assert "token" in result
        assert "refresh_token" in result
        assert result["user"]["id"] == 1

    @pytest.mark.asyncio
    async def test_expired_refresh_token(self, auth_service, security_manager):
        """Expired refresh token raises AuthError."""
        import jwt as pyjwt
        from datetime import datetime, timedelta

        expired_payload = {
            "user_id": 1,
            "wallet": None,
            "type": "refresh",
            "iat": datetime.utcnow() - timedelta(days=90),
            "exp": datetime.utcnow() - timedelta(days=1),
        }
        expired_tok = pyjwt.encode(
            expired_payload,
            security_manager.settings.jwt_secret_key,
            algorithm="HS256",
        )

        with pytest.raises(AuthError, match="expired"):
            await auth_service.refresh_tokens(expired_tok)

    @pytest.mark.asyncio
    async def test_access_token_rejected(self, auth_service, security_manager):
        """Using an access token as refresh must fail."""
        access_tok = security_manager.create_jwt_token(user_id=1, token_type="access")

        with pytest.raises(AuthError, match="Expected refresh"):
            await auth_service.refresh_tokens(access_tok)

    @pytest.mark.asyncio
    async def test_user_no_longer_exists(self, auth_service, mock_user_repo, security_manager):
        refresh_tok = security_manager.create_jwt_token(user_id=999, token_type="refresh")
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(AuthError, match="no longer exists"):
            await auth_service.refresh_tokens(refresh_tok)


# ---------------------------------------------------------------------------
# verify_token
# ---------------------------------------------------------------------------

class TestVerifyToken:

    @pytest.mark.asyncio
    async def test_success(self, auth_service, mock_user_repo, sample_user, security_manager):
        token = security_manager.create_jwt_token(user_id=1)
        mock_user_repo.get_by_id.return_value = sample_user

        user = await auth_service.verify_token(token)
        assert user["id"] == 1

    @pytest.mark.asyncio
    async def test_invalid_token(self, auth_service):
        with pytest.raises(AuthError):
            await auth_service.verify_token("garbage.token.value")

    @pytest.mark.asyncio
    async def test_user_not_found(self, auth_service, mock_user_repo, security_manager):
        token = security_manager.create_jwt_token(user_id=999)
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="not found"):
            await auth_service.verify_token(token)

    @pytest.mark.asyncio
    async def test_invalid_payload_no_user_id(self, auth_service, security_manager):
        """Verify token with payload missing user_id raises AuthError."""
        with patch.object(security_manager, "verify_jwt_token", return_value={"type": "access"}):
            with pytest.raises(AuthError, match="Invalid token payload"):
                await auth_service.verify_token("x.y.z")


# ---------------------------------------------------------------------------
# refresh_tokens – invalid payload
# ---------------------------------------------------------------------------

class TestRefreshTokensInvalidPayload:

    @pytest.mark.asyncio
    async def test_refresh_token_no_user_id_in_payload(self, auth_service, security_manager):
        """Refresh token with payload missing user_id raises AuthError."""
        with patch.object(security_manager, "verify_jwt_token", return_value={"type": "refresh"}):
            with pytest.raises(AuthError, match="Invalid refresh token payload"):
                await auth_service.refresh_tokens("x.y.z")


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:

    @pytest.mark.asyncio
    async def test_delegates_to_verify_token(self, auth_service, mock_user_repo, sample_user, security_manager):
        """get_current_user delegates to verify_token and returns user."""
        token = security_manager.create_jwt_token(user_id=1)
        mock_user_repo.get_by_id.return_value = sample_user

        user = await auth_service.get_current_user(token)
        assert user["id"] == 1
