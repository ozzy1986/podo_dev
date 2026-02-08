"""
Integration tests for the /api/v1/auth endpoints.

Uses the synchronous TestClient with fully mocked databases.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:

    def test_register_success(self, client, mock_pg_db, sample_user, security_manager):
        """Successful registration returns 201 with access and refresh tokens."""
        created_user = {**sample_user, "email": "new@example.com"}
        # The user repo goes through BaseRepository -> db.fetchrow / db.fetchval
        # Mock the path: exists-check returns False, then INSERT returns user
        mock_pg_db.fetchval.return_value = False  # email does not exist
        mock_pg_db.fetchrow.return_value = MagicMock(**{
            "__iter__": lambda s: iter(created_user.items()),
            "items": lambda: created_user.items(),
            "__getitem__": created_user.__getitem__,
            "get": created_user.get,
            "keys": created_user.keys,
        })
        # Make dict(row) work by mocking as a dict-like Record
        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(created_user.items()),
            "items": lambda s: created_user.items(),
            "__getitem__": lambda s, k: created_user[k],
            "get": lambda s, k, d=None: created_user.get(k, d),
            "keys": lambda s: created_user.keys(),
            "values": lambda s: created_user.values(),
        })()

        resp = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "strongpassword123",
            "language": "en",
        })

        assert resp.status_code == 201
        body = resp.json()
        assert "token" in body
        assert "user" in body

    def test_register_invalid_email(self, client):
        """Invalid email format returns 422 validation error."""
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "strongpassword123",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        """Password below minimum length returns 422."""
        resp = client.post("/api/v1/auth/register", json={
            "email": "user@example.com",
            "password": "short",
        })
        assert resp.status_code == 422

    def test_register_missing_fields(self, client):
        """Missing required fields returns 422."""
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

class TestLoginEndpoint:

    def test_login_success(self, client, mock_pg_db, sample_user, security_manager):
        """Valid credentials return tokens."""
        hashed = security_manager.hash_password("validpass123")
        user_row = {**sample_user, "password_hash": hashed}

        # get_by_email -> fetchrow
        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(user_row.items()),
            "items": lambda s: user_row.items(),
            "__getitem__": lambda s, k: user_row[k],
            "get": lambda s, k, d=None: user_row.get(k, d),
            "keys": lambda s: user_row.keys(),
            "values": lambda s: user_row.values(),
        })()

        resp = client.post("/api/v1/auth/login", json={
            "email": "user@example.com",
            "password": "validpass123",
        })

        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert body["user"]["id"] == sample_user["id"]

    def test_login_wrong_password(self, client, mock_pg_db, sample_user, security_manager):
        hashed = security_manager.hash_password("correct")
        user_row = {**sample_user, "password_hash": hashed}
        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(user_row.items()),
            "items": lambda s: user_row.items(),
            "__getitem__": lambda s, k: user_row[k],
            "get": lambda s, k, d=None: user_row.get(k, d),
            "keys": lambda s: user_row.keys(),
            "values": lambda s: user_row.values(),
        })()

        resp = client.post("/api/v1/auth/login", json={
            "email": "user@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login-wallet
# ---------------------------------------------------------------------------

class TestLoginWalletEndpoint:

    def test_login_wallet_success(self, client, test_app, mock_pg_db, sample_user):
        """Wallet login with valid signature returns tokens."""
        from app.api.deps import get_auth_service
        from unittest.mock import AsyncMock

        mock_auth = MagicMock()
        mock_auth.login_with_wallet = AsyncMock(return_value={
            "token": "access.jwt",
            "refresh_token": "refresh.jwt",
            "user": {**sample_user},
        })
        test_app.dependency_overrides[get_auth_service] = lambda: mock_auth

        resp = client.post("/api/v1/auth/login-wallet", json={
            "wallet_address": "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
            "signature": "base58signature",
            "public_key": "base58pubkey",
            "message": "signed message",
        })

        assert resp.status_code == 200
        body = resp.json()
        assert body["token"] == "access.jwt"
        assert body["refresh_token"] == "refresh.jwt"
        assert body["user"]["id"] == sample_user["id"]
        test_app.dependency_overrides.pop(get_auth_service, None)

    def test_login_wallet_auth_error(self, client, test_app, sample_user):
        """Wallet login with invalid signature returns 401."""
        from app.api.deps import get_auth_service
        from app.core.exceptions import AuthError
        from unittest.mock import AsyncMock

        mock_auth = MagicMock()
        mock_auth.login_with_wallet = AsyncMock(side_effect=AuthError("Invalid signature"))
        test_app.dependency_overrides[get_auth_service] = lambda: mock_auth

        resp = client.post("/api/v1/auth/login-wallet", json={
            "wallet_address": "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
            "signature": "bad",
            "public_key": "bad",
            "message": "msg",
        })

        assert resp.status_code == 401
        test_app.dependency_overrides.pop(get_auth_service, None)

    def test_login_wallet_missing_fields(self, client):
        """Missing required fields returns 422."""
        resp = client.post("/api/v1/auth/login-wallet", json={
            "wallet_address": "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
        })
        assert resp.status_code == 422

    def test_login_wallet_wallet_data_alias(self, client, test_app, sample_user):
        """Wallet login accepts wallet/data (WX format) instead of wallet_address/message."""
        from app.api.deps import get_auth_service
        from unittest.mock import AsyncMock

        mock_auth = MagicMock()
        mock_auth.login_with_wallet = AsyncMock(return_value={
            "token": "t",
            "refresh_token": "r",
            "user": {**sample_user},
        })
        test_app.dependency_overrides[get_auth_service] = lambda: mock_auth

        resp = client.post("/api/v1/auth/login-wallet", json={
            "wallet": "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
            "signature": "sig",
            "public_key": "pk",
            "data": "signed data",
        })

        assert resp.status_code == 200
        test_app.dependency_overrides.pop(get_auth_service, None)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

class TestRefreshEndpoint:

    def test_refresh_success(self, client, mock_pg_db, sample_user, security_manager):
        refresh_tok = security_manager.create_jwt_token(user_id=1, token_type="refresh")

        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(sample_user.items()),
            "items": lambda s: sample_user.items(),
            "__getitem__": lambda s, k: sample_user[k],
            "get": lambda s, k, d=None: sample_user.get(k, d),
            "keys": lambda s: sample_user.keys(),
            "values": lambda s: sample_user.values(),
        })()

        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_tok,
        })

        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert "refresh_token" in body

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not.a.real.token",
        })
        assert resp.status_code == 401

    def test_refresh_missing_field(self, client):
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------

class TestMeEndpoint:

    def test_me_success(self, client, mock_pg_db, sample_user, security_manager):
        token = security_manager.create_jwt_token(user_id=1)

        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(sample_user.items()),
            "items": lambda s: sample_user.items(),
            "__getitem__": lambda s, k: sample_user[k],
            "get": lambda s, k, d=None: sample_user.get(k, d),
            "keys": lambda s: sample_user.keys(),
            "values": lambda s: sample_user.values(),
        })()

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["email"] == sample_user["email"]

    def test_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_me_x_auth_token_header(self, client, mock_pg_db, sample_user, security_manager):
        """Alternative X-Auth-Token header works."""
        token = security_manager.create_jwt_token(user_id=1)

        mock_pg_db.fetchrow.return_value = type("Row", (), {
            "__iter__": lambda s: iter(sample_user.items()),
            "items": lambda s: sample_user.items(),
            "__getitem__": lambda s, k: sample_user[k],
            "get": lambda s, k, d=None: sample_user.get(k, d),
            "keys": lambda s: sample_user.keys(),
            "values": lambda s: sample_user.values(),
        })()

        resp = client.get(
            "/api/v1/auth/me",
            headers={"X-Auth-Token": token},
        )
        assert resp.status_code == 200
