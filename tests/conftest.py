"""
Pytest configuration and shared fixtures for the d.onl test suite.

All database interactions are mocked — no real PostgreSQL or ClickHouse
connections are required to run these tests.
"""

import logging
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Environment – force test mode before any app code is imported
# ---------------------------------------------------------------------------
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests-1234567890"


# ---------------------------------------------------------------------------
# Logging – remove handlers with mock levels (from patched RotatingFileHandler etc.)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def fix_logging_handlers():
    """Ensure no handler has MagicMock level which breaks record.levelno >= hdlr.level."""
    root = logging.getLogger()
    to_remove = []
    for h in root.handlers:
        level = getattr(h, "level", None)
        if level is not None and not isinstance(level, int):
            to_remove.append(h)
    for h in to_remove:
        root.removeHandler(h)
    yield

# ---------------------------------------------------------------------------
# Fixtures – configuration
# ---------------------------------------------------------------------------

@pytest.fixture
def security_settings():
    """Create SecuritySettings for tests (low bcrypt rounds for speed)."""
    from app.config import SecuritySettings

    return SecuritySettings(
        jwt_secret_key="test-secret-key-that-is-long-enough-for-tests-1234567890",
        jwt_algorithm="HS256",
        jwt_expiry_hours=1,
        bcrypt_rounds=4,  # fast for tests
        nonce_length_bytes=12,
    )


@pytest.fixture
def test_settings(security_settings):
    """Build a full Settings object suitable for unit tests."""
    from app.config import Settings, DatabaseSettings, ClickHouseSettings

    return Settings(
        app_env="development",
        debug=True,
        database=DatabaseSettings(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_password",
        ),
        clickhouse=ClickHouseSettings(
            host="localhost",
            port=9000,
            database="test_db",
        ),
        security=security_settings,
    )


# ---------------------------------------------------------------------------
# Fixtures – mocked databases
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pg_db():
    """Return a mock PostgreSQLDatabase whose async helpers are AsyncMocks."""
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchval = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value="OK")
    return db


@pytest.fixture
def mock_ch_client():
    """Return a mock ClickHouseDatabase."""
    client = MagicMock()
    client.execute = MagicMock(return_value=[])
    client.execute_dict = MagicMock(return_value=[])
    client.insert = MagicMock(return_value=0)
    client.async_execute = AsyncMock(return_value=[])
    client.async_execute_dict = AsyncMock(return_value=[])
    client.async_insert = AsyncMock(return_value=0)
    client.async_fetchval = AsyncMock(return_value=0)
    return client


# ---------------------------------------------------------------------------
# Fixtures – repositories (mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user_repo():
    """Return a mock UserRepository with all async methods stubbed."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_wallet = AsyncMock(return_value=None)
    repo.get_by_telegram_id = AsyncMock(return_value=None)
    repo.update_wallet = AsyncMock()
    repo.update_balance = AsyncMock()
    repo.update_payout_settings = AsyncMock()
    repo.update_language = AsyncMock()
    repo.verify_email = AsyncMock()
    repo.update_widget_preferences = AsyncMock()
    # BaseRepository helpers
    repo.fetch_one = AsyncMock(return_value=None)
    repo.fetch_all = AsyncMock(return_value=[])
    repo.fetch_val = AsyncMock(return_value=None)
    repo.execute = AsyncMock(return_value="OK")
    repo.exists = AsyncMock(return_value=False)
    repo.count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_domain_repo():
    """Return a mock DomainRepository with all async methods stubbed."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_domain = AsyncMock(return_value=None)
    repo.get_user_domains = AsyncMock(return_value=[])
    repo.count_user_domains = AsyncMock(return_value=0)
    repo.verify_domain = AsyncMock()
    repo.start_mining = AsyncMock()
    repo.stop_mining = AsyncMock()
    repo.update_check_status = AsyncMock()
    repo.update_a_record_status = AsyncMock()
    repo.update_description = AsyncMock()
    repo.update_parking_content = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_payout_repo():
    """Return a mock PayoutRepository for user API tests."""
    repo = MagicMock()
    repo.get_user_payout_history = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create_request = AsyncMock()
    repo.get_pending_requests = AsyncMock(return_value=[])
    repo.update_status = AsyncMock()
    repo.get_total_paid_out = AsyncMock(return_value=0.0)
    return repo


# ---------------------------------------------------------------------------
# Fixtures – services
# ---------------------------------------------------------------------------

@pytest.fixture
def security_manager(security_settings):
    """Create a real SecurityManager (fast bcrypt rounds)."""
    from app.core.security import SecurityManager

    return SecurityManager(security_settings)


@pytest.fixture
def auth_service(mock_user_repo, security_manager):
    """Create an AuthService backed by mocked repos."""
    from app.services.auth_service import AuthService

    return AuthService(user_repo=mock_user_repo, security=security_manager)


# ---------------------------------------------------------------------------
# Fixtures – FastAPI test client (mocked lifespan)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(test_settings, mock_pg_db, mock_ch_client):
    """
    Build a FastAPI app **without** starting real databases.

    The lifespan context manager is replaced with a no-op so that no
    actual PostgreSQL / ClickHouse connections are attempted.
    """
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    from app.api.v1.router import api_router
    from app.core.middleware import (
        ErrorHandlerMiddleware,
        setup_cors,
        setup_exception_handlers,
    )
    from app.db.postgresql import set_pg_pool
    from app.db.clickhouse import set_ch_client

    # Inject mock databases into the global singletons
    set_pg_pool(mock_pg_db)
    set_ch_client(mock_ch_client)

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    app = FastAPI(lifespan=_noop_lifespan)
    setup_cors(app, ["*"])
    app.add_middleware(ErrorHandlerMiddleware)
    setup_exception_handlers(app)
    app.include_router(api_router, prefix="/api")
    return app


@pytest.fixture
def client(test_app):
    """Synchronous TestClient wrapping the mocked FastAPI app."""
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers(test_app, sample_user, mock_user_repo, mock_domain_repo, mock_payout_repo):
    """
    Generate auth headers for unit tests.

    Overrides ``get_current_user`` and repo dependencies so endpoints
    receive *sample_user* and use mocked repositories.
    """
    from app.api.deps import (
        get_current_user,
        get_user_repo,
        get_domain_repo,
        get_payout_repo,
    )

    test_app.dependency_overrides[get_current_user] = lambda: sample_user
    test_app.dependency_overrides[get_user_repo] = lambda: mock_user_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo
    test_app.dependency_overrides[get_payout_repo] = lambda: mock_payout_repo
    mock_user_repo.get_by_id = AsyncMock(return_value=sample_user)
    yield {"Authorization": "Bearer test-token"}
    test_app.dependency_overrides.pop(get_current_user, None)
    test_app.dependency_overrides.pop(get_user_repo, None)
    test_app.dependency_overrides.pop(get_domain_repo, None)
    test_app.dependency_overrides.pop(get_payout_repo, None)


# ---------------------------------------------------------------------------
# Fixtures – sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_user():
    """A typical user dict as returned from the database."""
    return {
        "id": 1,
        "wallet": "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
        "email": "user@example.com",
        "telegram_id": None,
        "username": None,
        "password_hash": None,  # set in specific tests when needed
        "language": "en",
        "accumulated_balance": 0.0,
        "accumulated_units": 0,
        "payout_mode": "manual",
        "payout_threshold": None,
        "email_verified": False,
        "email_verified_at": None,
        "created_at": datetime(2025, 1, 1, 0, 0, 0).isoformat(),
        "updated_at": None,
    }


@pytest.fixture
def sample_domain():
    """A typical domain dict as returned from the database."""
    return {
        "id": 10,
        "user_id": 1,
        "domain": "example.com",
        "sld": "example",
        "tld": "com",
        "sld_length": 7,
        "verified": False,
        "is_mining": False,
        "nonce": "abc123nonce",
        "failed_checks": 0,
        "age_r": 1.0,
        "description": None,
        "parking_mode": None,
        "parking_content": None,
        "a_record_points_to_us": None,
        "a_record_last_check": None,
        "created_at": datetime(2025, 1, 2, 0, 0, 0).isoformat(),
        "updated_at": None,
        "last_check": None,
        "verification_time": None,
    }


@pytest.fixture
def sample_reward():
    """Sample reward data."""
    return {
        "id": 100,
        "user_id": 1,
        "domain_id": 10,
        "amount": 0.5,
        "units": 50000000,
        "created_at": datetime(2025, 1, 3, 12, 0, 0).isoformat(),
    }
