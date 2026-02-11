"""
Unit tests for app.core.middleware.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from app.core.middleware import (
    make_error_response,
    RateLimitMiddleware,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    setup_exception_handlers,
)
from app.core.exceptions import AppException, AuthError, NotFoundError, PaidVoteRequiredError


# ---------------------------------------------------------------------------
# make_error_response
# ---------------------------------------------------------------------------

class TestMakeErrorResponse:

    def test_basic_error_response(self):
        resp = make_error_response(400, "Bad request")
        assert resp.status_code == 400
        import json
        body = json.loads(resp.body)
        assert body["ok"] is False
        assert body["error"] == "Bad request"
        assert body["status_code"] == 400
        assert body["details"] == {}

    def test_error_response_with_details(self):
        resp = make_error_response(422, "Validation", {"field": "email"})
        import json
        body = json.loads(resp.body)
        assert body["details"]["field"] == "email"

    def test_server_error_code(self):
        resp = make_error_response(500, "Internal")
        assert resp.status_code == 500

    def test_404_error_code(self):
        resp = make_error_response(404, "Not found")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:

    def _build_app(self, rate_per_minute: int = 5, burst: int = 3) -> FastAPI:
        """Build a minimal app with rate limiting."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            rate_per_minute=rate_per_minute,
            burst=burst,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        @app.get("/api/v1/auth/login")
        async def auth_login():
            return {"login": True}

        return app

    def test_allows_requests_within_burst(self):
        app = self._build_app(rate_per_minute=60, burst=5)
        client = TestClient(app)

        for _ in range(5):
            resp = client.get("/ping")
            assert resp.status_code == 200

    def test_blocks_after_exceeding_burst(self):
        app = self._build_app(rate_per_minute=1, burst=2)
        client = TestClient(app)

        # First two should succeed (burst = 2)
        assert client.get("/ping").status_code == 200
        assert client.get("/ping").status_code == 200

        # Third should be rate-limited (burst exhausted, refill is slow)
        resp = client.get("/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert "Rate limit" in body["error"]

    def test_rate_limit_response_has_retry_after(self):
        app = self._build_app(rate_per_minute=1, burst=1)
        client = TestClient(app)

        client.get("/ping")  # exhaust burst
        resp = client.get("/ping")
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "60"

    def test_auth_endpoints_stricter_limits(self):
        """Auth endpoints use a separate, stricter bucket."""
        app = self._build_app(rate_per_minute=600, burst=100)
        client = TestClient(app)

        # Exhaust the auth-specific bucket (starts at 10 tokens)
        blocked = False
        for i in range(15):
            resp = client.get("/api/v1/auth/login")
            if resp.status_code == 429:
                blocked = True
                break

        assert blocked, "Auth endpoint should eventually be rate limited"


# ---------------------------------------------------------------------------
# ErrorHandlerMiddleware
# ---------------------------------------------------------------------------

class TestErrorHandlerMiddleware:

    def _build_app(self, handler) -> FastAPI:
        """Build an app where the route raises an exception."""
        app = FastAPI()
        app.add_middleware(ErrorHandlerMiddleware)

        @app.get("/test")
        async def test_route():
            return handler()

        return app

    def test_catches_app_exception(self):
        def raise_auth():
            raise AuthError("Invalid creds")

        app = self._build_app(raise_auth)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/test")
        assert resp.status_code == 401
        body = resp.json()
        assert body["ok"] is False
        assert "Invalid creds" in body["error"]

    def test_catches_not_found_error(self):
        def raise_nf():
            raise NotFoundError("Gone")

        app = self._build_app(raise_nf)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/test")
        assert resp.status_code == 404
        body = resp.json()
        assert "Gone" in body["error"]

    def test_catches_generic_exception(self):
        """Unexpected errors produce 500 with safe message."""
        def raise_generic():
            raise RuntimeError("oops")

        app = self._build_app(raise_generic)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/test")
        assert resp.status_code == 500

    def test_app_exception_with_details(self):
        def raise_detailed():
            raise AppException("Whoops", status_code=418, details={"tea": "pot"})

        app = self._build_app(raise_detailed)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/test")
        assert resp.status_code == 418
        body = resp.json()
        assert body["details"]["tea"] == "pot"

    def test_generic_exception_hides_message_in_production(self):
        """In production, generic exceptions return safe message."""
        def raise_generic():
            raise RuntimeError("secret internal error")

        app = self._build_app(raise_generic)
        with patch("app.config.get_settings") as m:
            m.return_value.is_development = False
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test")
        assert resp.status_code == 500
        body = resp.json()
        assert "Internal server error" in body["error"]


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_adds_x_process_time_header(self):
        app = FastAPI()
        app.add_middleware(LoggingMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "X-Process-Time" in resp.headers

    def test_logs_and_propagates_exception(self):
        app = FastAPI()
        app.add_middleware(LoggingMiddleware)

        @app.get("/fail")
        async def fail():
            raise ValueError("route error")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/fail")
        assert resp.status_code == 500


class TestSetupExceptionHandlers:
    """Tests for setup_exception_handlers."""

    def test_http_exception_returns_envelope(self):
        app = FastAPI()
        setup_exception_handlers(app)

        @app.get("/err")
        async def err():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/err")
        assert resp.status_code == 404
        body = resp.json()
        assert body["ok"] is False
        assert "Not found" in body["error"]

    def test_validation_error_returns_envelope(self):
        app = FastAPI()
        setup_exception_handlers(app)

        @app.get("/validate")
        async def validate(x: int):
            return x

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/validate")  # x missing
        assert resp.status_code == 422
        body = resp.json()
        assert body["ok"] is False
        assert "validation_errors" in body.get("details", {})

    def test_paid_vote_required_returns_409_envelope(self):
        """Route raising PaidVoteRequiredError returns 409 with details.code for frontend."""
        app = FastAPI()
        setup_exception_handlers(app)

        @app.get("/vote")
        async def vote():
            raise PaidVoteRequiredError("Paid vote required")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/vote")
        assert resp.status_code == 409
        body = resp.json()
        assert body.get("ok") is False
        assert body.get("details", {}).get("code") == "PAID_VOTE_REQUIRED"
        assert "error" in body
