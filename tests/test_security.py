"""
Unit tests for app.core.security – SecurityManager.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.config import SecuritySettings
from app.core.security import SecurityManager
from app.core.exceptions import AuthError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def settings() -> SecuritySettings:
    return SecuritySettings(
        jwt_secret_key="test-secret-key-long-enough-for-unit-tests-1234567890",
        jwt_algorithm="HS256",
        jwt_expiry_hours=1,
        bcrypt_rounds=4,
        nonce_length_bytes=12,
    )


@pytest.fixture
def sm(settings) -> SecurityManager:
    return SecurityManager(settings)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Tests for hash_password / verify_password."""

    def test_hash_and_verify_roundtrip(self, sm: SecurityManager):
        hashed = sm.hash_password("my_secure_password")
        assert sm.verify_password("my_secure_password", hashed) is True

    def test_wrong_password_fails(self, sm: SecurityManager):
        hashed = sm.hash_password("correct_password")
        assert sm.verify_password("wrong_password", hashed) is False

    def test_hash_is_different_each_time(self, sm: SecurityManager):
        h1 = sm.hash_password("same_password")
        h2 = sm.hash_password("same_password")
        assert h1 != h2  # different salts

    def test_hash_returns_string(self, sm: SecurityManager):
        hashed = sm.hash_password("password123")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2")

    def test_verify_with_corrupt_hash_returns_false(self, sm: SecurityManager):
        assert sm.verify_password("password", "not-a-valid-hash") is False


# ---------------------------------------------------------------------------
# JWT creation & verification
# ---------------------------------------------------------------------------

class TestJWT:
    """Tests for JWT token lifecycle."""

    def test_create_and_verify_access_token(self, sm: SecurityManager):
        token = sm.create_jwt_token(user_id=42, wallet_address="3Pxxx")
        payload = sm.verify_jwt_token(token, expected_type="access")

        assert payload["user_id"] == 42
        assert payload["wallet"] == "3Pxxx"
        assert payload["type"] == "access"

    def test_create_and_verify_refresh_token(self, sm: SecurityManager):
        token = sm.create_jwt_token(user_id=7, token_type="refresh")
        payload = sm.verify_jwt_token(token, expected_type="refresh")

        assert payload["user_id"] == 7
        assert payload["type"] == "refresh"

    def test_verify_rejects_wrong_token_type(self, sm: SecurityManager):
        access_token = sm.create_jwt_token(user_id=1, token_type="access")
        with pytest.raises(AuthError, match="Expected refresh token"):
            sm.verify_jwt_token(access_token, expected_type="refresh")

        refresh_token = sm.create_jwt_token(user_id=1, token_type="refresh")
        with pytest.raises(AuthError, match="Expected access token"):
            sm.verify_jwt_token(refresh_token, expected_type="access")

    def test_expired_token_raises(self, sm: SecurityManager, settings: SecuritySettings):
        """Create a token that is already expired and ensure it raises."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": 1,
            "wallet": None,
            "type": "access",
            "iat": now - timedelta(hours=10),
            "exp": now - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        with pytest.raises(AuthError, match="expired"):
            sm.verify_jwt_token(token)

    def test_invalid_token_raises(self, sm: SecurityManager):
        with pytest.raises(AuthError, match="Invalid token"):
            sm.verify_jwt_token("this.is.not.valid")

    def test_extra_claims(self, sm: SecurityManager):
        token = sm.create_jwt_token(
            user_id=1,
            extra_claims={"role": "admin"},
        )
        payload = sm.verify_jwt_token(token)
        assert payload["role"] == "admin"

    def test_access_token_default_type(self, sm: SecurityManager):
        """Token type defaults to 'access'."""
        token = sm.create_jwt_token(user_id=1)
        payload = sm.verify_jwt_token(token)
        assert payload["type"] == "access"


# ---------------------------------------------------------------------------
# Token pair
# ---------------------------------------------------------------------------

class TestTokenPair:
    """Tests for create_token_pair."""

    def test_returns_both_tokens(self, sm: SecurityManager):
        pair = sm.create_token_pair(user_id=5, wallet_address="3Pwallet")

        assert "access_token" in pair
        assert "refresh_token" in pair
        assert pair["access_token"] != pair["refresh_token"]

    def test_access_token_type(self, sm: SecurityManager):
        pair = sm.create_token_pair(user_id=5)
        payload = sm.verify_jwt_token(pair["access_token"], expected_type="access")
        assert payload["type"] == "access"

    def test_refresh_token_type(self, sm: SecurityManager):
        pair = sm.create_token_pair(user_id=5)
        payload = sm.verify_jwt_token(pair["refresh_token"], expected_type="refresh")
        assert payload["type"] == "refresh"


# ---------------------------------------------------------------------------
# Nonce generation
# ---------------------------------------------------------------------------

class TestNonce:
    """Tests for generate_nonce."""

    def test_nonce_returns_string(self, sm: SecurityManager):
        nonce = sm.generate_nonce()
        assert isinstance(nonce, str)
        assert len(nonce) > 0

    def test_nonce_uniqueness(self, sm: SecurityManager):
        nonces = {sm.generate_nonce() for _ in range(50)}
        assert len(nonces) == 50, "Nonces should be unique"


# ---------------------------------------------------------------------------
# Waves signature verification
# ---------------------------------------------------------------------------

class TestWavesSignature:
    """Tests for verify_waves_signature and related."""

    def test_verify_waves_returns_false_on_decode_failure(self, sm: SecurityManager):
        """Returns False when base58 decode fails."""
        with patch("app.core.security.base58_decode", return_value=None):
            result = sm.verify_waves_signature("msg", "sig", "key")
        assert result is False

    def test_verify_waves_returns_false_on_invalid_pubkey_length(self, sm: SecurityManager):
        """Returns False when public key is not 32 bytes."""
        with patch("app.core.security.base58_decode") as decode:
            decode.side_effect = lambda x: b"x" * 16 if x == "pk" else b"x" * 64
            result = sm.verify_waves_signature("msg", "sig", "pk")
        assert result is False

    def test_verify_waves_returns_false_on_invalid_sig_length(self, sm: SecurityManager):
        """Returns False when signature is not 64 bytes."""
        with patch("app.core.security.base58_decode") as decode:
            decode.side_effect = lambda x: b"x" * 32 if x == "key" else b"x" * 16
            result = sm.verify_waves_signature("msg", "sig", "key")
        assert result is False

    def test_verify_waves_returns_true_when_wx_auth_verifies(self, sm: SecurityManager):
        """Returns True when WX Web Auth format verifies."""
        with patch("app.core.security.base58_decode") as decode:
            decode.side_effect = lambda x: b"x" * 32 if x == "key" else b"x" * 64
            with patch.object(sm, "_verify_signature_bytes", return_value=True):
                result = sm.verify_waves_signature("data", "sig", "key", host="dev.d.onl")
        assert result is True

    def test_verify_waves_returns_true_when_raw_message_verifies(self, sm: SecurityManager):
        """Returns True when raw message format verifies."""
        with patch("app.core.security.base58_decode") as decode:
            decode.side_effect = lambda x: b"x" * 32 if x == "key" else b"x" * 64
            with patch.object(sm, "_verify_signature_bytes") as verify:
                verify.side_effect = lambda pk, msg, sig: msg == b"raw"
                result = sm.verify_waves_signature("raw", "sig", "key")
        assert result is True

    def test_verify_waves_returns_true_when_legacy_prefix_verifies(self, sm: SecurityManager):
        """Returns True when legacy binary prefix format verifies."""
        with patch("app.core.security.base58_decode") as decode:
            decode.side_effect = lambda x: b"x" * 32 if x == "key" else b"x" * 64
            with patch.object(sm, "_verify_signature_bytes") as verify:
                def check(pk, msg, sig):
                    return msg.startswith(b"\xff\x01")
                verify.side_effect = check
                result = sm.verify_waves_signature("x", "sig", "key")
        assert result is True


class TestVerifyWalletMatchesPublicKey:
    """Tests for verify_wallet_matches_public_key."""

    def test_returns_false_on_decode_failure(self, sm: SecurityManager):
        """Returns False when base58 decode fails."""
        with patch("app.core.security.base58_decode", return_value=None):
            result = sm.verify_wallet_matches_public_key("3Nxxx", "key")
        assert result is False

    def test_returns_false_on_wrong_key_length(self, sm: SecurityManager):
        """Returns False when public key is not 32 bytes."""
        with patch("app.core.security.base58_decode", return_value=b"x" * 16):
            result = sm.verify_wallet_matches_public_key("3Nxxx", "key")
        assert result is False

    def test_returns_true_when_wallet_matches(self, sm: SecurityManager):
        """Returns True when derived address matches wallet."""
        mock_pw = MagicMock()
        mock_addr = MagicMock()
        mock_addr.address = "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW"
        mock_pw.Address.return_value = mock_addr
        with patch("app.core.security.base58_decode", return_value=b"x" * 32):
            with patch.dict("sys.modules", {"pywaves": mock_pw}):
                result = sm.verify_wallet_matches_public_key(
                    "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW", "key"
                )
        assert result is True

    def test_returns_false_when_wallet_mismatches(self, sm: SecurityManager):
        """Returns False when derived address does not match."""
        mock_pw = MagicMock()
        mock_addr = MagicMock()
        mock_addr.address = "3Nother"
        mock_pw.Address.return_value = mock_addr
        with patch("app.core.security.base58_decode", return_value=b"x" * 32):
            with patch.dict("sys.modules", {"pywaves": mock_pw}):
                result = sm.verify_wallet_matches_public_key(
                    "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW", "key"
                )
        assert result is False


class TestBase58Decode:
    """Tests for base58_decode standalone function."""

    def test_base58_decode_with_library(self):
        """base58_decode uses base58 lib when available."""
        from app.core.security import base58_decode
        # "1" decodes to 0, which is b'\x00'
        result = base58_decode("1")
        assert result is not None
        assert isinstance(result, bytes)

    def test_base58_decode_valid_input(self):
        """base58_decode returns bytes for valid base58 input."""
        from app.core.security import base58_decode
        result = base58_decode("2")
        assert result is not None
        assert isinstance(result, bytes)
