"""
Unit tests for app.db.clickhouse – ClickHouseDatabase, get_ch_client, set_ch_client.
"""

from decimal import Decimal
from datetime import datetime, date
from unittest.mock import MagicMock, patch

import pytest

from app.config import ClickHouseSettings
from app.db.clickhouse import (
    ClickHouseDatabase,
    get_ch_client,
    set_ch_client,
)


@pytest.fixture
def ch_settings():
    return ClickHouseSettings(host="localhost", port=9000, database="test")


class TestClickHouseDatabase:
    """Tests for ClickHouseDatabase."""

    def test_connect_creates_client(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = [(1,)]
        with patch("app.db.clickhouse.Client", return_value=mock_client):
            db = ClickHouseDatabase(ch_settings)
            db.connect()
            assert db._client is mock_client

    def test_connect_skips_when_already_connected(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = [(1,)]
        with patch("app.db.clickhouse.Client", return_value=mock_client):
            db = ClickHouseDatabase(ch_settings)
            db.connect()
            db.connect()
            assert mock_client.execute.call_count == 1

    def test_connect_raises_on_failure(self, ch_settings):
        with patch("app.db.clickhouse.Client", side_effect=OSError("conn refused")):
            db = ClickHouseDatabase(ch_settings)
            with pytest.raises(OSError, match="conn refused"):
                db.connect()

    def test_disconnect_closes_client(self, ch_settings):
        mock_client = MagicMock()
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        db.disconnect()
        mock_client.disconnect.assert_called_once()
        assert db._client is None

    def test_disconnect_noop_when_not_connected(self, ch_settings):
        db = ClickHouseDatabase(ch_settings)
        db.disconnect()
        assert db._client is None

    def test_disconnect_clears_client_on_exception(self, ch_settings):
        mock_client = MagicMock()
        mock_client.disconnect.side_effect = OSError("close failed")
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        db.disconnect()
        assert db._client is None

    def test_connect_adds_password_when_set(self, ch_settings):
        ch_settings.password = "secret"
        mock_client = MagicMock()
        mock_client.execute.return_value = [(1,)]
        with patch("app.db.clickhouse.Client", return_value=mock_client) as m:
            db = ClickHouseDatabase(ch_settings)
            db.connect()
            call_kwargs = m.call_args[1]
            assert call_kwargs.get("password") == "secret"

    def test_execute_raises_when_not_connected(self, ch_settings):
        db = ClickHouseDatabase(ch_settings)
        with pytest.raises(RuntimeError, match="not initialized"):
            db.execute("SELECT 1")

    def test_execute_returns_rows(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = [(1, "a"), (2, "b")]
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        result = db.execute("SELECT * FROM t")
        assert result == [(1, "a"), (2, "b")]

    def test_execute_dict_converts_decimal_and_datetime(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = (
            [(Decimal("1.5"), date(2025, 1, 15))],
            [("amount", "Decimal"), ("day", "Date")],
        )
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        result = db.execute_dict("SELECT 1")
        assert len(result) == 1
        assert result[0]["amount"] == 1.5
        assert "2025-01-15" in str(result[0]["day"])

    def test_insert_empty_returns_zero(self, ch_settings):
        db = ClickHouseDatabase(ch_settings)
        db._client = MagicMock()
        n = db.insert("t", [])
        assert n == 0

    def test_insert_returns_count(self, ch_settings):
        mock_client = MagicMock()
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        n = db.insert("t", [{"a": 1}, {"a": 2}], columns=["a"])
        assert n == 2
        mock_client.execute.assert_called_once()

    def test_fetchval_returns_first_value(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = [(42,)]
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        assert db.fetchval("SELECT 1") == 42

    def test_fetchval_returns_none_when_empty(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = []
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        assert db.fetchval("SELECT 1") is None

    @pytest.mark.asyncio
    async def test_async_wrappers(self, ch_settings):
        mock_client = MagicMock()
        mock_client.execute.return_value = [(1,)]
        db = ClickHouseDatabase(ch_settings)
        db._client = mock_client
        r = await db.async_execute("SELECT 1")
        assert r == [(1,)]
        r2 = await db.async_fetchval("SELECT 1")
        assert r2 == 1

    def test_client_property(self, ch_settings):
        db = ClickHouseDatabase(ch_settings)
        assert db.client is None
        db._client = MagicMock()
        assert db.client is not None


class TestGetSetChClient:
    """Tests for get_ch_client and set_ch_client."""

    def test_get_ch_client_raises_when_not_set(self):
        import app.db.clickhouse as mod
        orig = mod._ch_db
        mod._ch_db = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                get_ch_client()
        finally:
            mod._ch_db = orig

    def test_set_and_get_ch_client(self, ch_settings):
        db = ClickHouseDatabase(ch_settings)
        import app.db.clickhouse as mod
        orig = mod._ch_db
        try:
            set_ch_client(db)
            assert get_ch_client() is db
        finally:
            mod._ch_db = orig
