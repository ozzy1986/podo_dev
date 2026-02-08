"""
Unit tests for configuration module.
"""

import pytest
from app.config import Settings, get_settings, is_development


@pytest.mark.unit
def test_settings_creation():
    """Test that settings can be created."""
    settings = Settings()
    assert settings is not None
    assert settings.app_env in ['development', 'production', 'test']


@pytest.mark.unit
def test_get_settings():
    """Test get_settings returns singleton."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2


@pytest.mark.unit
def test_is_development():
    """Test is_development function."""
    result = is_development()
    assert isinstance(result, bool)


@pytest.mark.unit
def test_database_dsn():
    """Test database DSN generation."""
    settings = Settings()
    dsn = settings.database.dsn
    assert "postgresql://" in dsn
    assert settings.database.user in dsn
    assert settings.database.database in dsn


@pytest.mark.unit
def test_nested_settings():
    """Test nested settings are properly initialized."""
    settings = Settings()
    assert settings.database is not None
    assert settings.clickhouse is not None
    assert settings.blockchain is not None
    assert settings.dns is not None
    assert settings.security is not None
    assert settings.domain is not None
    assert settings.retry is not None
