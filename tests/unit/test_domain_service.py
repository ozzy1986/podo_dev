"""
Unit tests for app.services.domain_service – DomainService.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import DomainSettings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
    PermissionError as AppPermissionError,
)
from app.services.domain_service import DomainService


@pytest.fixture
def domain_settings():
    return DomainSettings(
        min_domain_length=3, max_domain_length=253,
        max_domains_per_user=100,
    )


@pytest.fixture
def mock_domain_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_user_domains = AsyncMock(return_value=[])
    repo.count_user_domains = AsyncMock(return_value=0)
    repo.create = AsyncMock(return_value={"id": 1, "domain": "x.com"})
    repo.delete = AsyncMock(return_value=True)
    repo.verify_domain = AsyncMock(return_value={"id": 1, "verified": True})
    repo.start_mining = AsyncMock(return_value={"id": 1, "is_mining": True})
    repo.update_description = AsyncMock(return_value={"id": 1})
    repo.update_parking_content = AsyncMock(return_value={"id": 1})
    return repo


@pytest.fixture
def mock_user_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def domain_service(mock_domain_repo, mock_user_repo, domain_settings):
    return DomainService(mock_domain_repo, mock_user_repo, domain_settings)


class TestDomainServiceValidateDomainName:
    """Tests for _validate_domain_name."""

    def test_rejects_empty(self, domain_service):
        with pytest.raises(ValidationError, match="Invalid"):
            domain_service._validate_domain_name("")

    def test_rejects_no_dot(self, domain_service):
        with pytest.raises(ValidationError, match="Invalid"):
            domain_service._validate_domain_name("nodot")

    def test_rejects_too_short(self, domain_settings):
        domain_settings.min_domain_length = 10
        svc = DomainService(MagicMock(), MagicMock(), domain_settings)
        with pytest.raises(ValidationError, match="too short"):
            svc._validate_domain_name("ab.com")

    def test_rejects_too_long(self, domain_settings):
        domain_settings.max_domain_length = 10
        svc = DomainService(MagicMock(), MagicMock(), domain_settings)
        with pytest.raises(ValidationError, match="too long"):
            svc._validate_domain_name("verylongdomain.com")

    def test_rejects_empty_sld(self, domain_service):
        with pytest.raises(ValidationError, match="SLD cannot be empty"):
            domain_service._validate_domain_name(".com")

    def test_rejects_subdomains(self, domain_service):
        with pytest.raises(ValidationError, match="Subdomains"):
            domain_service._validate_domain_name("a.b.com")

    def test_returns_sld_tld_length(self, domain_service):
        sld, tld, length = domain_service._validate_domain_name("example.com")
        assert sld == "example"
        assert tld == "com"
        assert length == 7


class TestDomainServiceAddDomain:
    """Tests for add_domain."""

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self, domain_service, mock_user_repo):
        mock_user_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="User.*not found"):
            await domain_service.add_domain(999, "x.com")

    @pytest.mark.asyncio
    async def test_raises_when_domain_limit_reached(self, domain_service, mock_user_repo, mock_domain_repo):
        mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1})
        mock_domain_repo.count_user_domains = AsyncMock(return_value=100)
        with pytest.raises(ConflictError, match="Maximum"):
            await domain_service.add_domain(1, "x.com")

    @pytest.mark.asyncio
    async def test_returns_created_domain(self, domain_service, mock_user_repo, mock_domain_repo):
        mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1})
        mock_domain_repo.count_user_domains = AsyncMock(return_value=0)
        mock_domain_repo.create = AsyncMock(return_value={"id": 1, "domain": "x.com"})
        result = await domain_service.add_domain(1, "x.com")
        assert result["domain"] == "x.com"


class TestDomainServiceGetDomain:
    """Tests for get_domain."""

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_service.get_domain(999)

    @pytest.mark.asyncio
    async def test_raises_on_ownership_mismatch(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 2})
        with pytest.raises(AppPermissionError, match="don't own"):
            await domain_service.get_domain(1, user_id=1)

    @pytest.mark.asyncio
    async def test_returns_domain_when_owned(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        result = await domain_service.get_domain(1, user_id=1)
        assert result["id"] == 1


class TestDomainServiceGetVerificationTxtRecord:
    """Tests for get_verification_txt_record."""

    @pytest.mark.asyncio
    async def test_raises_when_domain_not_found(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError, match="not found"):
            await domain_service.get_verification_txt_record(999)

    @pytest.mark.asyncio
    async def test_raises_when_user_no_wallet(self, domain_service, mock_domain_repo, mock_user_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "wallet": None})
        with pytest.raises(ValidationError, match="wallet"):
            await domain_service.get_verification_txt_record(1)

    @pytest.mark.asyncio
    async def test_returns_txt_value(self, domain_service, mock_domain_repo, mock_user_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "wallet": "3Nxxx"})
        result = await domain_service.get_verification_txt_record(1)
        assert "d.onl" in result
        assert "3Nxxx" in result


class TestDomainServiceDeleteDomain:

    @pytest.mark.asyncio
    async def test_returns_true_when_deleted(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_domain_repo.delete = AsyncMock(return_value=True)
        result = await domain_service.delete_domain(1, 1)
        assert result is True


class TestDomainServiceUpdateDescription:

    @pytest.mark.asyncio
    async def test_returns_updated_domain(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_domain_repo.update_description = AsyncMock(
            return_value={"id": 1, "description": "New"}
        )
        result = await domain_service.update_description(1, 1, "New")
        assert result["description"] == "New"


class TestDomainServiceUpdateParkingContent:

    @pytest.mark.asyncio
    async def test_returns_updated_domain(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_domain_repo.update_parking_content = AsyncMock(
            return_value={"id": 1, "parking_mode": "non_redirect"}
        )
        result = await domain_service.update_parking_content(
            1, 1, "<html>", "non_redirect"
        )
        assert result["parking_mode"] == "non_redirect"

    @pytest.mark.asyncio
    async def test_raises_on_invalid_parking_mode(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        with pytest.raises(ValidationError, match="redirect.*non_redirect"):
            await domain_service.update_parking_content(1, 1, "x", "invalid")


class TestDomainServiceVerifyDomain:

    @pytest.mark.asyncio
    async def test_returns_verified_domain(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_domain_repo.verify_domain = AsyncMock(
            return_value={"id": 1, "verified": True}
        )
        mock_domain_repo.start_mining = AsyncMock(
            return_value={"id": 1, "verified": True, "is_mining": True}
        )
        with patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.is_production = True
            result = await domain_service.verify_domain(1, 1)
        assert result["verified"] is True
        assert result["is_mining"] is True

    @pytest.mark.asyncio
    async def test_skips_start_mining_in_dev(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
        mock_domain_repo.verify_domain = AsyncMock(
            return_value={"id": 1, "verified": True}
        )
        with patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.is_production = False
            result = await domain_service.verify_domain(1, 1)
        assert result["verified"] is True
        mock_domain_repo.start_mining.assert_not_called()


class TestDomainServiceGetUserDomains:

    @pytest.mark.asyncio
    async def test_returns_list_from_repo(self, domain_service, mock_domain_repo):
        mock_domain_repo.get_user_domains = AsyncMock(
            return_value=[{"id": 1, "domain": "x.com"}]
        )
        result = await domain_service.get_user_domains(1, limit=10, offset=0)
        assert len(result) == 1
        assert result[0]["domain"] == "x.com"
