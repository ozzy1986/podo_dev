"""
Integration test fixtures for real database connections.

All fixtures in this module connect to actual PostgreSQL and ClickHouse
databases using credentials from .env file.
"""

import os
import pytest
from datetime import datetime
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
import httpx

# Force test environment
os.environ["APP_ENV"] = "development"

from app.config import get_settings, Settings
from app.db.postgresql import PostgreSQLDatabase, set_pg_pool
from app.db.clickhouse import ClickHouseDatabase, set_ch_client
from app.core.security import SecurityManager
from app.repositories.user_repo import UserRepository
from app.repositories.domain_repo import DomainRepository
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.middleware import (
    ErrorHandlerMiddleware,
    setup_cors,
    setup_exception_handlers,
)


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Load settings from .env for integration tests."""
    return get_settings()


@pytest.fixture
async def real_pg_db(integration_settings) -> AsyncGenerator[PostgreSQLDatabase, None]:
    """
    Create a real PostgreSQL database connection in the test's event loop.

    Connects to domain_mining_dev using .env credentials. Function-scoped
    so the connection is created and used in the same loop as the test.
    """
    db = PostgreSQLDatabase(integration_settings.database)
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


@pytest.fixture
def real_ch_db(integration_settings) -> Generator[ClickHouseDatabase, None, None]:
    """
    Create a real ClickHouse database connection.

    Connects to domain_mining_dev using .env credentials. Function-scoped.
    """
    ch_db = ClickHouseDatabase(integration_settings.clickhouse)
    ch_db.connect()
    try:
        yield ch_db
    finally:
        ch_db.disconnect()


@pytest.fixture
async def test_user(real_pg_db: PostgreSQLDatabase) -> AsyncGenerator[dict, None]:
    """
    Create a test user in the database.
    
    Uses unique identifiers (test_runner_ prefix) and cleans up after test.
    """
    user_repo = UserRepository(real_pg_db)
    
    # Create unique test user
    timestamp = int(datetime.now().timestamp())
    test_email = f"test_runner_{timestamp}@test.d.onl"
    test_wallet = f"3TestWallet{timestamp:010d}"
    
    try:
        user = await user_repo.create(
            email=test_email,
            wallet_address=test_wallet,
            language="en"
        )
        yield user
        
    finally:
        # Cleanup: delete test user (cascade will delete domains)
        try:
            await real_pg_db.execute(
                "DELETE FROM users WHERE email = $1 OR wallet = $2",
                test_email, test_wallet
            )
        except Exception as e:
            # Log but don't fail test on cleanup errors
            print(f"Warning: Failed to cleanup test user: {e}")


@pytest.fixture
async def test_domain(
    real_pg_db: PostgreSQLDatabase,
    test_user: dict
) -> AsyncGenerator[dict, None]:
    """
    Create a test domain linked to test_user.
    
    Cleans up after test.
    """
    domain_repo = DomainRepository(real_pg_db)
    
    # Create unique test domain
    timestamp = int(datetime.now().timestamp())
    test_domain_name = f"test-runner-{timestamp}.test.d.onl"
    test_nonce = f"test_nonce_{timestamp}"
    
    try:
        domain = await domain_repo.create(
            user_id=test_user["id"],
            domain=test_domain_name,
            sld=f"test-runner-{timestamp}",
            tld="onl",
            sld_length=len(f"test-runner-{timestamp}"),
            nonce=test_nonce
        )
        yield domain
        
    finally:
        # Cleanup: delete test domain
        try:
            await real_pg_db.execute(
                "DELETE FROM domains WHERE domain = $1",
                test_domain_name
            )
        except Exception as e:
            print(f"Warning: Failed to cleanup test domain: {e}")


@pytest.fixture
def ch_rewards_writable(real_ch_db) -> bool:
    """
    Check if rewards_log supports direct INSERT.
    
    Returns False when rewards_log is a ClickHouse View or MaterializedView
    (cannot INSERT directly — must target the underlying MergeTree table).
    """
    engine_result = real_ch_db.execute(
        "SELECT engine FROM system.tables "
        "WHERE database = currentDatabase() AND name = 'rewards_log'"
    )
    if not engine_result:
        return False
    engine = engine_result[0][0]
    return engine not in ("View", "MaterializedView")


@pytest.fixture
def security_manager(integration_settings) -> SecurityManager:
    """Create SecurityManager for generating auth tokens."""
    return SecurityManager(integration_settings.security)


@pytest.fixture
def auth_token(test_user: dict, security_manager: SecurityManager) -> str:
    """
    Generate a real JWT token for the test user.
    
    Returns a valid access token that can be used in API requests.
    """
    return security_manager.create_jwt_token(
        user_id=test_user["id"],
        wallet_address=test_user.get("wallet")
    )


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Return Authorization headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def real_app(integration_settings) -> AsyncGenerator[FastAPI, None]:
    """
    Build a FastAPI app with DB connections in the test's event loop.

    Creates PG/CH connections so the app and tests share the same loop.
    """
    app_pg = PostgreSQLDatabase(integration_settings.database)
    app_ch = ClickHouseDatabase(integration_settings.clickhouse)
    await app_pg.connect()
    app_ch.connect()

    set_pg_pool(app_pg)
    set_ch_client(app_ch)

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    app = FastAPI(lifespan=_noop_lifespan)
    setup_cors(app, ["*"])
    app.add_middleware(ErrorHandlerMiddleware)
    setup_exception_handlers(app)
    app.include_router(api_router, prefix="/api")

    try:
        yield app
    finally:
        await app_pg.disconnect()
        app_ch.disconnect()


@pytest.fixture
def real_client(real_app: FastAPI) -> TestClient:
    """Synchronous TestClient wrapping the real FastAPI app (may conflict with async DB in same loop)."""
    return TestClient(real_app, raise_server_exceptions=False)


@pytest.fixture
async def async_client(real_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async HTTP client that calls the app in the same event loop as tests.

    Use this for integration tests that hit the API with real DB to avoid
    'another operation in progress' (TestClient runs the app in a thread).
    """
    transport = httpx.ASGITransport(app=real_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# Mark all fixtures in this module as integration tests
pytestmark = pytest.mark.integration
