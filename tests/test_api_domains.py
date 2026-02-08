"""
Integration tests for the /api/v1/domains endpoints.

Uses the synchronous TestClient with fully mocked databases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


def _make_row(data: dict):
    """Create a dict-like object that behaves like an asyncpg Record."""
    return type("Row", (), {
        "__iter__": lambda s: iter(data.items()),
        "items": lambda s: data.items(),
        "__getitem__": lambda s, k: data[k],
        "get": lambda s, k, d=None: data.get(k, d),
        "keys": lambda s: data.keys(),
        "values": lambda s: data.values(),
    })()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers(security_manager):
    """Return valid Authorization headers for user_id=1."""
    token = security_manager.create_jwt_token(user_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def _authed_user(mock_pg_db, sample_user):
    """Make the database always return sample_user for user lookups."""
    # fetchrow is used by get_by_id and other single-row queries
    mock_pg_db.fetchrow.return_value = _make_row(sample_user)
    # fetchval is used by exists() checks – default to False
    mock_pg_db.fetchval.return_value = False
    return sample_user


# ---------------------------------------------------------------------------
# POST /api/v1/domains
# ---------------------------------------------------------------------------

class TestAddDomain:

    def test_add_domain_success(
        self, client, mock_pg_db, auth_headers, sample_user, sample_domain
    ):
        call_count = 0
        user_row = _make_row(sample_user)
        domain_row = _make_row(sample_domain)

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 1st call: get_by_id (user check)
            # 2nd call: domain INSERT
            if call_count <= 1:
                return user_row
            return domain_row

        mock_pg_db.fetchrow.side_effect = _side_effect
        mock_pg_db.fetchval.return_value = False  # exists => False, count => 0
        # count_user_domains returns int via fetchval
        count_calls = 0
        original_fetchval = mock_pg_db.fetchval

        async def _fetchval_side(*args, **kwargs):
            nonlocal count_calls
            count_calls += 1
            if count_calls == 1:
                return False  # domain does not exist
            return 0  # domain count for user

        mock_pg_db.fetchval.side_effect = _fetchval_side

        resp = client.post(
            "/api/v1/domains",
            json={"domain": "example.com"},
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["domain"] == "example.com"

    def test_add_domain_no_auth(self, client):
        resp = client.post("/api/v1/domains", json={"domain": "example.com"})
        assert resp.status_code == 401

    def test_add_domain_missing_field(self, client, auth_headers, mock_pg_db, sample_user):
        mock_pg_db.fetchrow.return_value = _make_row(sample_user)
        resp = client.post("/api/v1/domains", json={}, headers=auth_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/domains
# ---------------------------------------------------------------------------

class TestListDomains:

    def test_list_domains_success(
        self, client, mock_pg_db, auth_headers, sample_user, sample_domain
    ):
        user_row = _make_row(sample_user)

        # fetchrow for auth (get user by id)
        mock_pg_db.fetchrow.return_value = user_row
        # fetch returns list of domain records
        mock_pg_db.fetch.return_value = [_make_row(sample_domain)]

        resp = client.get("/api/v1/domains", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1
        assert body[0]["domain"] == "example.com"

    def test_list_domains_no_auth(self, client):
        resp = client.get("/api/v1/domains")
        assert resp.status_code == 401

    def test_list_domains_empty(self, client, mock_pg_db, auth_headers, sample_user):
        mock_pg_db.fetchrow.return_value = _make_row(sample_user)
        mock_pg_db.fetch.return_value = []

        resp = client.get("/api/v1/domains", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/domains/{id}
# ---------------------------------------------------------------------------

class TestGetDomain:

    def test_get_domain_success(
        self, client, mock_pg_db, auth_headers, sample_user, sample_domain
    ):
        call_count = 0
        user_row = _make_row(sample_user)
        domain_row = _make_row(sample_domain)

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call: auth get_by_id -> user
            # Second call: domain get_by_id -> domain
            if call_count == 1:
                return user_row
            return domain_row

        mock_pg_db.fetchrow.side_effect = _side_effect

        resp = client.get(f"/api/v1/domains/{sample_domain['id']}", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == sample_domain["id"]

    def test_get_domain_not_found(self, client, mock_pg_db, auth_headers, sample_user):
        call_count = 0
        user_row = _make_row(sample_user)

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_row  # auth
            return None  # domain not found

        mock_pg_db.fetchrow.side_effect = _side_effect

        resp = client.get("/api/v1/domains/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_domain_no_auth(self, client):
        resp = client.get("/api/v1/domains/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/v1/domains/{id}
# ---------------------------------------------------------------------------

class TestDeleteDomain:

    def test_delete_domain_success(
        self, client, mock_pg_db, auth_headers, sample_user, sample_domain
    ):
        call_count = 0
        user_row = _make_row(sample_user)
        domain_row = _make_row(sample_domain)

        async def _fetchrow_side(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_row  # auth
            return domain_row  # domain lookup

        mock_pg_db.fetchrow.side_effect = _fetchrow_side
        mock_pg_db.execute.return_value = "DELETE 1"

        resp = client.delete(
            f"/api/v1/domains/{sample_domain['id']}",
            headers=auth_headers,
        )

        assert resp.status_code == 204

    def test_delete_domain_not_found(self, client, mock_pg_db, auth_headers, sample_user):
        call_count = 0
        user_row = _make_row(sample_user)

        async def _fetchrow_side(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_row
            return None

        mock_pg_db.fetchrow.side_effect = _fetchrow_side

        resp = client.delete("/api/v1/domains/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_domain_no_auth(self, client):
        resp = client.delete("/api/v1/domains/1")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/domains/{id}/verify
# ---------------------------------------------------------------------------

class TestVerifyDomain:

    def test_verify_domain_no_auth(self, client):
        resp = client.post("/api/v1/domains/1/verify")
        assert resp.status_code == 401

    def test_verify_domain_not_found(self, client, mock_pg_db, auth_headers, sample_user):
        call_count = 0
        user_row = _make_row(sample_user)

        async def _fetchrow_side(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_row  # auth
            return None  # domain not found

        mock_pg_db.fetchrow.side_effect = _fetchrow_side

        resp = client.post("/api/v1/domains/9999/verify", headers=auth_headers)
        assert resp.status_code == 404

    def test_verify_domain_success(
        self, client, test_app, mock_pg_db, auth_headers, sample_user,
        sample_domain
    ):
        from app.api.deps import get_domain_service, get_dns_service

        mock_pg_db.fetchrow.return_value = _make_row(sample_user)

        domain_verified = dict(sample_domain)
        domain_verified["verified"] = True
        mock_domain_service = MagicMock()
        mock_domain_service.get_domain = AsyncMock(return_value=sample_domain)
        mock_domain_service.get_verification_txt_record = AsyncMock(
            return_value="d.onl;wallet=3Nxxx"
        )
        mock_domain_service.verify_domain = AsyncMock(return_value=domain_verified)

        mock_dns_service = MagicMock()
        mock_dns_service.verify_txt_record = AsyncMock(return_value=True)

        test_app.dependency_overrides[get_domain_service] = lambda: mock_domain_service
        test_app.dependency_overrides[get_dns_service] = lambda: mock_dns_service
        try:
            resp = client.post(
                f"/api/v1/domains/{sample_domain['id']}/verify",
                headers=auth_headers,
            )
        finally:
            test_app.dependency_overrides.pop(get_domain_service, None)
            test_app.dependency_overrides.pop(get_dns_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["domain"] == "example.com"


# ---------------------------------------------------------------------------
# GET /api/v1/domains/{id}/verification
# ---------------------------------------------------------------------------

class TestGetVerificationInfo:

    def test_get_verification_info_success(
        self, client, test_app, mock_pg_db, auth_headers, sample_user,
        sample_domain
    ):
        from app.api.deps import get_domain_service

        mock_pg_db.fetchrow.return_value = _make_row(sample_user)

        mock_domain_service = MagicMock()
        mock_domain_service.get_domain = AsyncMock(return_value=sample_domain)
        mock_domain_service.get_verification_txt_record = AsyncMock(
            return_value="d.onl;wallet=3Nxxx"
        )

        test_app.dependency_overrides[get_domain_service] = lambda: mock_domain_service
        try:
            resp = client.get(
                f"/api/v1/domains/{sample_domain['id']}/verification",
                headers=auth_headers,
            )
        finally:
            test_app.dependency_overrides.pop(get_domain_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["domain"] == "example.com"
        assert "d.onl" in body["txt_record"]
        assert "instructions" in body

    def test_get_verification_info_no_auth(self, client):
        resp = client.get("/api/v1/domains/1/verification")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/v1/domains/{id}/description
# ---------------------------------------------------------------------------

class TestUpdateDescription:

    def test_update_description_success(
        self, client, test_app, mock_pg_db, auth_headers, sample_user,
        sample_domain
    ):
        from app.api.deps import get_domain_service

        mock_pg_db.fetchrow.return_value = _make_row(sample_user)

        updated = dict(sample_domain)
        updated["description"] = "My cool domain"

        mock_domain_service = MagicMock()
        mock_domain_service.update_description = AsyncMock(return_value=updated)

        test_app.dependency_overrides[get_domain_service] = lambda: mock_domain_service
        try:
            resp = client.put(
                f"/api/v1/domains/{sample_domain['id']}/description",
                json={"description": "My cool domain"},
                headers=auth_headers,
            )
        finally:
            test_app.dependency_overrides.pop(get_domain_service, None)

        assert resp.status_code == 200
        assert resp.json()["description"] == "My cool domain"

    def test_update_description_no_auth(self, client):
        resp = client.put("/api/v1/domains/1/description", json={"description": "x"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/v1/domains/{id}/parking
# ---------------------------------------------------------------------------

class TestUpdateParking:

    def test_update_parking_success(
        self, client, test_app, mock_pg_db, auth_headers, sample_user,
        sample_domain
    ):
        from app.api.deps import get_domain_service

        mock_pg_db.fetchrow.return_value = _make_row(sample_user)

        updated = dict(sample_domain)
        updated["parking_content"] = "<html>Hi</html>"
        updated["parking_mode"] = "non_redirect"

        mock_domain_service = MagicMock()
        mock_domain_service.update_parking_content = AsyncMock(return_value=updated)

        test_app.dependency_overrides[get_domain_service] = lambda: mock_domain_service
        try:
            resp = client.put(
                f"/api/v1/domains/{sample_domain['id']}/parking",
                json={"parking_content": "<html>Hi</html>", "parking_mode": "non_redirect"},
                headers=auth_headers,
            )
        finally:
            test_app.dependency_overrides.pop(get_domain_service, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["parking_mode"] == "non_redirect"

    def test_update_parking_no_auth(self, client):
        resp = client.put(
            "/api/v1/domains/1/parking",
            json={"parking_content": "x", "parking_mode": "redirect"}
        )
        assert resp.status_code == 401
