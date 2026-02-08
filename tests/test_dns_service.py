"""
Unit tests for app.services.dns_service – DNSService.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from app.config import DNSSettings
from app.core.exceptions import DNSError
from app.services.dns_service import DNSService


@pytest.fixture
def dns_settings():
    """DNS settings with minimal consensus for tests."""
    return DNSSettings(
        resolvers=["1.1.1.1", "8.8.8.8"],
        consensus_minimum=1,
        timeout=5,
        our_server_ip="193.33.170.175",
    )


@pytest.fixture
def dns_service(dns_settings):
    """DNSService instance."""
    return DNSService(dns_settings)


class TestDNSServiceInit:
    """Tests for DNSService initialization."""

    def test_creates_resolver_per_nameserver(self, dns_settings):
        """Creates one resolver per configured nameserver."""
        service = DNSService(dns_settings)
        assert len(service._resolvers) == 2


class TestVerifyTxtRecord:
    """Tests for verify_txt_record."""

    @pytest.mark.asyncio
    async def test_returns_true_when_txt_matches_subdomain(self, dns_service):
        """Returns True when _mining.domain has expected TXT."""
        dns_service._query_txt_records = AsyncMock(return_value=["d.onl=abc123"])
        result = await dns_service.verify_txt_record("example.com", "d.onl=abc123")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_txt_matches_root_domain(self, dns_service):
        """Returns True when root domain has expected TXT."""
        call_count = 0
        async def mock_query(domain):
            nonlocal call_count
            call_count += 1
            if "example.com" == domain and "_mining" not in domain:
                return ["d.onl=expected_value"]
            return []
        dns_service._query_txt_records = mock_query
        result = await dns_service.verify_txt_record("example.com", "d.onl=expected_value")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(self, dns_service):
        """Returns False when no TXT matches."""
        dns_service._query_txt_records = AsyncMock(side_effect=DNSError("no consensus"))
        result = await dns_service.verify_txt_record("example.com", "d.onl=xyz")
        assert result is False


class TestVerifyARecord:
    """Tests for verify_a_record."""

    @pytest.mark.asyncio
    async def test_returns_true_when_ip_matches(self, dns_service):
        """Returns True when A record points to expected IP."""
        dns_service._query_a_records = AsyncMock(return_value=["193.33.170.175"])
        result = await dns_service.verify_a_record("example.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_with_explicit_expected_ip(self, dns_service):
        """Returns True when A record matches explicit expected_ip."""
        dns_service._query_a_records = AsyncMock(return_value=["10.0.0.1"])
        result = await dns_service.verify_a_record("example.com", expected_ip="10.0.0.1")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_ip_mismatch(self, dns_service):
        """Returns False when A record does not match."""
        dns_service._query_a_records = AsyncMock(return_value=["192.168.1.1"])
        result = await dns_service.verify_a_record("example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_dns_error(self, dns_service):
        """Returns False when query raises DNSError."""
        dns_service._query_a_records = AsyncMock(side_effect=DNSError("timeout"))
        result = await dns_service.verify_a_record("example.com")
        assert result is False


class TestQueryTxtRecords:
    """Tests for _query_txt_records (consensus logic)."""

    @pytest.mark.asyncio
    async def test_raises_when_not_enough_resolvers(self, dns_settings):
        """Raises DNSError when consensus_minimum not met."""
        dns_settings.consensus_minimum = 2
        service = DNSService(dns_settings)
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=[{"txt1"}, None]):
            with pytest.raises(DNSError, match="Not enough resolvers"):
                await service._query_txt_records("example.com")

    @pytest.mark.asyncio
    async def test_returns_consensus_records(self, dns_service):
        """Returns records that meet consensus."""
        results = [{"d.onl=abc"}, {"d.onl=abc"}]
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=results):
            records = await dns_service._query_txt_records("example.com")
        assert "d.onl=abc" in records


class TestQueryARecords:
    """Tests for _query_a_records."""

    @pytest.mark.asyncio
    async def test_raises_when_not_enough_resolvers(self, dns_settings):
        """Raises DNSError when consensus_minimum not met."""
        dns_settings.consensus_minimum = 2
        service = DNSService(dns_settings)
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=[{"1.2.3.4"}, None]):
            with pytest.raises(DNSError, match="Not enough resolvers"):
                await service._query_a_records("example.com")

    @pytest.mark.asyncio
    async def test_returns_consensus_ips(self, dns_service):
        """Returns IPs that meet consensus."""
        results = [{"193.33.170.175"}, {"193.33.170.175"}]
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=results):
            ips = await dns_service._query_a_records("example.com")
        assert "193.33.170.175" in ips


class TestSyncQueryTxt:
    """Tests for _sync_query_txt (runs in thread)."""

    def test_handles_nxdomain(self, dns_service):
        """Handles NXDOMAIN by returning empty set."""
        for r in dns_service._resolvers:
            r.resolve = MagicMock(side_effect=dns.resolver.NXDOMAIN())
        result = dns_service._sync_query_txt("nonexistent.example.com")
        assert all(r is not None for r in result)
        assert result[0] == set()
        assert result[1] == set()

    def test_handles_dns_exception(self, dns_service):
        """Handles generic DNSException by returning None for that resolver."""
        dns_service._resolvers[0].resolve = MagicMock(
            side_effect=dns.exception.DNSException("timeout")
        )
        mock_rdata = MagicMock()
        mock_rdata.strings = [b"txt1"]
        dns_service._resolvers[1].resolve = MagicMock(return_value=[mock_rdata])
        result = dns_service._sync_query_txt("example.com")
        assert result[0] is None
        assert isinstance(result[1], set)


class TestSyncQueryA:
    """Tests for _sync_query_a."""

    def test_handles_nxdomain(self, dns_service):
        """Handles NXDOMAIN by returning empty set."""
        for r in dns_service._resolvers:
            r.resolve = MagicMock(side_effect=dns.resolver.NXDOMAIN())
        result = dns_service._sync_query_a("nonexistent.example.com")
        assert result[0] == set()
        assert result[1] == set()
