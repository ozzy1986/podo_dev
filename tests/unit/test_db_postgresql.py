"""
Unit tests for app.db.postgresql – PostgreSQLDatabase, get_pg_pool, set_pg_pool.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import DatabaseSettings
from app.db.postgresql import (
    PostgreSQLDatabase,
    get_pg_pool,
    set_pg_pool,
)


@pytest.fixture
def db_settings():
    return DatabaseSettings(
        host="localhost", port=5432, database="test",
        user="u", password="p", pool_min_size=1, pool_max_size=5
    )


class TestPostgreSQLDatabase:
    """Tests for PostgreSQLDatabase."""

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, db_settings):
        with patch("app.db.postgresql.asyncpg.create_pool", new_callable=AsyncMock) as m:
            m.return_value = MagicMock()
            db = PostgreSQLDatabase(db_settings)
            await db.connect()
            m.assert_called_once()
            assert db._pool is not None

    @pytest.mark.asyncio
    async def test_connect_idempotent_skips_when_already_connected(self, db_settings):
        mock_pool = MagicMock()
        with patch("app.db.postgresql.asyncpg.create_pool", new_callable=AsyncMock):
            db = PostgreSQLDatabase(db_settings)
            db._pool = mock_pool
            await db.connect()
            # create_pool not called again
            assert db._pool is mock_pool

    @pytest.mark.asyncio
    async def test_connect_raises_on_failure(self, db_settings):
        with patch("app.db.postgresql.asyncpg.create_pool", new_callable=AsyncMock, side_effect=OSError("conn refused")):
            db = PostgreSQLDatabase(db_settings)
            with pytest.raises(OSError, match="conn refused"):
                await db.connect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self, db_settings):
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        db = PostgreSQLDatabase(db_settings)
        db._pool = mock_pool
        await db.disconnect()
        mock_pool.close.assert_called_once()
        assert db._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_not_connected(self, db_settings):
        db = PostgreSQLDatabase(db_settings)
        db._pool = None
        await db.disconnect()
        assert db._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_clears_pool_on_exception(self, db_settings):
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock(side_effect=OSError("close failed"))
        db = PostgreSQLDatabase(db_settings)
        db._pool = mock_pool
        await db.disconnect()
        assert db._pool is None

    @pytest.mark.asyncio
    async def test_acquire_raises_when_not_connected(self, db_settings):
        db = PostgreSQLDatabase(db_settings)
        with pytest.raises(RuntimeError, match="not initialized"):
            async with db.acquire():
                pass

    @pytest.mark.asyncio
    async def test_acquire_yields_connection(self, db_settings):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        db = PostgreSQLDatabase(db_settings)
        db._pool = mock_pool
        async with db.acquire() as conn:
            assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_execute_fetch_fetchrow_fetchval(self, db_settings):
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_conn.fetch = AsyncMock(return_value=[(1, "a")])
        mock_conn.fetchrow = AsyncMock(return_value=(1, "a"))
        mock_conn.fetchval = AsyncMock(return_value=42)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        db = PostgreSQLDatabase(db_settings)
        db._pool = mock_pool

        r = await db.execute("INSERT INTO x VALUES (1)")
        assert r == "INSERT 0 1"

        rows = await db.fetch("SELECT 1")
        assert len(rows) == 1

        row = await db.fetchrow("SELECT 1")
        assert row == (1, "a")

        val = await db.fetchval("SELECT 1")
        assert val == 42

    @pytest.mark.asyncio
    async def test_transaction_raises_when_not_connected(self, db_settings):
        db = PostgreSQLDatabase(db_settings)
        with pytest.raises(RuntimeError, match="not initialized"):
            async with db.transaction():
                pass

    def test_pool_property(self, db_settings):
        db = PostgreSQLDatabase(db_settings)
        assert db.pool is None
        db._pool = MagicMock()
        assert db.pool is not None


class TestGetSetPgPool:
    """Tests for get_pg_pool and set_pg_pool."""

    def test_get_pg_pool_raises_when_not_set(self):
        import app.db.postgresql as mod
        orig = mod._pg_db
        mod._pg_db = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_pg_pool()
        finally:
            mod._pg_db = orig

    def test_set_and_get_pg_pool(self, db_settings):
        db = PostgreSQLDatabase(db_settings)
        import app.db.postgresql as mod
        orig = mod._pg_db
        try:
            set_pg_pool(db)
            assert get_pg_pool() is db
        finally:
            mod._pg_db = orig
