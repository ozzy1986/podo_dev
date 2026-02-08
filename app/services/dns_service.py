"""
DNS service for domain verification.
Uses asyncio.to_thread() to prevent blocking the event loop.
"""

import asyncio
import logging
from typing import Optional, List

import dns.resolver
import dns.exception

from app.config import DNSSettings
from app.core.exceptions import DNSError

logger = logging.getLogger(__name__)


class DNSService:
    """Service for DNS operations. All DNS queries run in thread pool to avoid blocking."""

    def __init__(self, settings: DNSSettings):
        self.settings = settings
        self._resolvers = []
        for nameserver in self.settings.resolvers:
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = [nameserver]
            resolver.timeout = self.settings.timeout
            resolver.lifetime = self.settings.timeout
            self._resolvers.append(resolver)

    async def verify_txt_record(self, domain: str, expected_value: str) -> bool:
        """Verify TXT record for domain (checks _mining subdomain first, then root)."""
        subdomains = [f"_mining.{domain}", domain]

        for subdomain in subdomains:
            try:
                records = await self._query_txt_records(subdomain)
                for record in records:
                    if expected_value in record:
                        logger.info(f"TXT record verified for {subdomain}")
                        return True
            except DNSError as e:
                logger.debug(f"TXT query failed for {subdomain}: {e}")
                continue

        return False

    async def verify_a_record(self, domain: str, expected_ip: Optional[str] = None) -> bool:
        """Verify A record for domain points to expected IP."""
        if expected_ip is None:
            expected_ip = self.settings.our_server_ip

        try:
            records = await self._query_a_records(domain)
            return expected_ip in records
        except DNSError as e:
            logger.debug(f"A record query failed for {domain}: {e}")
            return False

    async def _query_txt_records(self, domain: str) -> List[str]:
        """Query TXT records with consensus from multiple resolvers (non-blocking)."""
        results = await asyncio.to_thread(self._sync_query_txt, domain)

        successful = [r for r in results if r is not None]
        if len(successful) < self.settings.consensus_minimum:
            raise DNSError(f"Not enough resolvers responded (need {self.settings.consensus_minimum})")

        non_empty = [r for r in successful if r]
        if not non_empty:
            return []

        # Find records with consensus
        all_records = set()
        for r in non_empty:
            all_records.update(r)

        consensus_records = set()
        for record in all_records:
            count = sum(1 for r in successful if r and record in r)
            if count >= self.settings.consensus_minimum:
                consensus_records.add(record)

        return list(consensus_records)

    async def _query_a_records(self, domain: str) -> List[str]:
        """Query A records with consensus from multiple resolvers (non-blocking)."""
        results = await asyncio.to_thread(self._sync_query_a, domain)

        successful = [r for r in results if r is not None]
        if len(successful) < self.settings.consensus_minimum:
            raise DNSError(f"Not enough resolvers responded (need {self.settings.consensus_minimum})")

        non_empty = [r for r in successful if r]
        if not non_empty:
            return []

        all_ips = set()
        for r in non_empty:
            all_ips.update(r)

        consensus_ips = set()
        for ip in all_ips:
            count = sum(1 for r in successful if r and ip in r)
            if count >= self.settings.consensus_minimum:
                consensus_ips.add(ip)

        return list(consensus_ips)

    def _sync_query_txt(self, domain: str) -> List[Optional[set]]:
        """Synchronous TXT query across all resolvers (runs in thread)."""
        results = []
        for resolver in self._resolvers:
            try:
                answers = resolver.resolve(domain, 'TXT')
                records = set()
                for rdata in answers:
                    txt = ''.join(
                        s.decode('utf-8') if isinstance(s, bytes) else str(s)
                        for s in rdata.strings
                    )
                    records.add(txt)
                results.append(records)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                results.append(set())
            except dns.exception.DNSException as e:
                logger.warning(f"DNS TXT query failed for {domain} ({resolver.nameservers[0]}): {e}")
                results.append(None)
        return results

    def _sync_query_a(self, domain: str) -> List[Optional[set]]:
        """Synchronous A record query across all resolvers (runs in thread)."""
        results = []
        for resolver in self._resolvers:
            try:
                answers = resolver.resolve(domain, 'A')
                ips = {str(rdata.address) for rdata in answers}
                results.append(ips)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                results.append(set())
            except dns.exception.DNSException as e:
                logger.warning(f"DNS A query failed for {domain} ({resolver.nameservers[0]}): {e}")
                results.append(None)
        return results
