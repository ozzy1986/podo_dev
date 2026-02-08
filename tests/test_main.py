"""
Unit tests for app.main – create_app and lifespan.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, lifespan


class TestCreateApp:
    """Tests for create_app factory."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app returns a configured FastAPI app."""
        app = create_app()
        assert app is not None
        assert app.title == "d.onl API"
        assert app.version == "2.0.0"

    @patch("app.workers.scheduler.stop_scheduler", new_callable=AsyncMock)
    @patch("app.workers.scheduler.start_scheduler", new_callable=AsyncMock)
    @patch("app.main.ClickHouseDatabase")
    @patch("app.main.PostgreSQLDatabase")
    def test_create_app_includes_health_endpoint(
        self, MockPG, MockCH, _start, _stop
    ):
        """create_app registers /health endpoint."""
        mock_pg = MagicMock()
        mock_pg.connect = AsyncMock()
        mock_pg.disconnect = AsyncMock()
        MockPG.return_value = mock_pg

        mock_ch = MagicMock()
        mock_ch.connect = MagicMock()
        mock_ch.disconnect = MagicMock()
        MockCH.return_value = mock_ch

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @patch("app.workers.scheduler.stop_scheduler", new_callable=AsyncMock)
    @patch("app.workers.scheduler.start_scheduler", new_callable=AsyncMock)
    @patch("app.main.ClickHouseDatabase")
    @patch("app.main.PostgreSQLDatabase")
    def test_create_app_root_endpoint(
        self, MockPG, MockCH, _start, _stop
    ):
        """Root endpoint returns service info."""
        mock_pg = MagicMock()
        mock_pg.connect = AsyncMock()
        mock_pg.disconnect = AsyncMock()
        MockPG.return_value = mock_pg

        mock_ch = MagicMock()
        mock_ch.connect = MagicMock()
        mock_ch.disconnect = MagicMock()
        MockCH.return_value = mock_ch

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "d.onl API" in data["service"]
        assert "version" in data


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_and_shutdown(self):
        """Lifespan runs startup and shutdown with mocked DBs."""
        app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.validate_production_config = MagicMock()

        mock_pg = MagicMock()
        mock_pg.connect = AsyncMock()
        mock_pg.disconnect = AsyncMock()

        mock_ch = MagicMock()
        mock_ch.connect = MagicMock()
        mock_ch.disconnect = MagicMock()

        with patch("app.main.get_settings", return_value=mock_settings):
            with patch("app.main.PostgreSQLDatabase", return_value=mock_pg):
                with patch("app.main.ClickHouseDatabase", return_value=mock_ch):
                    with patch("app.main.set_pg_pool"):
                        with patch("app.main.set_ch_client"):
                            with patch("app.workers.scheduler.start_scheduler", new_callable=AsyncMock):
                                with patch("app.workers.scheduler.stop_scheduler", new_callable=AsyncMock):
                                    async with lifespan(app):
                                        pass

        mock_pg.connect.assert_called_once()
        mock_pg.disconnect.assert_called_once()
        mock_ch.connect.assert_called_once()
        mock_ch.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_raises_on_config_error(self):
        """Lifespan raises when validate_production_config fails."""
        app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.validate_production_config.side_effect = ValueError("Bad config")

        with patch("app.main.get_settings", return_value=mock_settings):
            with pytest.raises(ValueError, match="Bad config"):
                async with lifespan(app):
                    pass
