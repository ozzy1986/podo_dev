"""
Unit tests for app.config – Settings, validation, properties.
"""

import os
import pytest
from unittest.mock import patch

from app.config import (
    Settings,
    SecuritySettings,
    DatabaseSettings,
    ClickHouseSettings,
    get_settings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides) -> Settings:
    """Create a Settings instance with sensible test defaults + overrides."""
    defaults = dict(
        app_env="development",
        debug=True,
        database=DatabaseSettings(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_password",
        ),
        clickhouse=ClickHouseSettings(host="localhost"),
        security=SecuritySettings(
            jwt_secret_key="a-long-enough-secret-key-for-testing-purpose-1234",
            bcrypt_rounds=4,
        ),
    )
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Basic Settings creation
# ---------------------------------------------------------------------------

class TestSettingsDefaults:

    def test_settings_loads_defaults(self):
        s = _make_settings()
        assert s.app_env == "development"
        assert s.database.host == "localhost"
        assert s.security.jwt_algorithm == "HS256"

    def test_nested_settings_initialised(self):
        s = _make_settings()
        assert s.database is not None
        assert s.clickhouse is not None
        assert s.security is not None
        assert s.dns is not None
        assert s.blockchain is not None
        assert s.domain is not None
        assert s.retry is not None

    def test_database_dsn(self):
        s = _make_settings()
        dsn = s.database.dsn
        assert dsn.startswith("postgresql://")
        assert "test_user" in dsn
        assert "test_db" in dsn


# ---------------------------------------------------------------------------
# is_development / is_production
# ---------------------------------------------------------------------------

class TestEnvironmentProperties:

    def test_is_development(self):
        s = _make_settings(app_env="development")
        assert s.is_development is True
        assert s.is_production is False

    def test_is_production(self):
        s = _make_settings(app_env="production")
        assert s.is_production is True
        assert s.is_development is False

    def test_case_insensitive(self):
        s = _make_settings(app_env="Development")
        assert s.is_development is True

    def test_whitespace_stripped(self):
        s = _make_settings(app_env="  production  ")
        assert s.is_production is True

    def test_other_env(self):
        s = _make_settings(app_env="staging")
        assert s.is_development is False
        assert s.is_production is False


# ---------------------------------------------------------------------------
# validate_production_config
# ---------------------------------------------------------------------------

class TestProductionValidation:

    def test_does_not_raise_in_dev(self):
        s = _make_settings(app_env="development")
        # Should silently pass – not production
        s.validate_production_config()

    def test_raises_for_insecure_jwt_secret(self):
        s = _make_settings(
            app_env="production",
            security=SecuritySettings(jwt_secret_key="CHANGE_ME_IN_PRODUCTION"),
            database=DatabaseSettings(password="pw"),
        )
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            s.validate_production_config()

    def test_raises_for_short_jwt_secret(self):
        s = _make_settings(
            app_env="production",
            security=SecuritySettings(jwt_secret_key="short"),
            database=DatabaseSettings(password="pw"),
        )
        with pytest.raises(ValueError, match="at least 32"):
            s.validate_production_config()

    def test_raises_for_missing_pg_password(self):
        s = _make_settings(
            app_env="production",
            security=SecuritySettings(
                jwt_secret_key="a-very-long-secret-key-that-is-longer-than-32-characters"
            ),
            database=DatabaseSettings(password=""),
        )
        with pytest.raises(ValueError, match="PG_PASSWORD"):
            s.validate_production_config()

    def test_passes_for_valid_production(self):
        s = _make_settings(
            app_env="production",
            security=SecuritySettings(
                jwt_secret_key="a-very-long-secret-key-that-is-longer-than-32-characters"
            ),
            database=DatabaseSettings(password="real_password"),
        )
        # Replace the dummy dapp address
        s.blockchain.dapp_address = "3PRealContractAddressHere12345678"

        s.validate_production_config()  # should not raise


# ---------------------------------------------------------------------------
# CORS helpers
# ---------------------------------------------------------------------------

class TestCORSOrigins:

    def test_wildcard(self):
        sec = SecuritySettings(cors_origins="*")
        assert sec.get_cors_origins_list() == ["*"]

    def test_comma_separated(self):
        sec = SecuritySettings(cors_origins="https://a.com, https://b.com")
        origins = sec.get_cors_origins_list()
        assert origins == ["https://a.com", "https://b.com"]

    def test_empty_string_returns_wildcard(self):
        sec = SecuritySettings(cors_origins="")
        assert sec.get_cors_origins_list() == ["*"]
