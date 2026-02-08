"""
Oracle Domain Verification Module
Handles DNS TXT record verification and WHOIS expiry checking.
"""

import logging
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Lazy import DNS resolver
_dns_resolver = None
_dns_exception = None
DNS_AVAILABLE = False


def _import_dns():
    """Lazy import of dns module."""
    global _dns_resolver, _dns_exception, DNS_AVAILABLE

    if DNS_AVAILABLE:
        return _dns_resolver, _dns_exception

    try:
        import dns.resolver
        import dns.exception
        _dns_resolver = dns.resolver
        _dns_exception = dns.exception
        DNS_AVAILABLE = True
        logger.info("Successfully imported dnspython module")
        return _dns_resolver, _dns_exception
    except ImportError as e:
        DNS_AVAILABLE = False
        logger.error(f"Failed to import dnspython: {e}")
        raise ImportError(
            f"dnspython package is required but not installed. "
            f"Install it with: pip install dnspython==2.4.2. "
            f"Original error: {e}"
        ) from e


# Lazy import whois
_whois_module = None
WHOIS_AVAILABLE = False


def _import_whois():
    """Lazy import of whois module."""
    global _whois_module, WHOIS_AVAILABLE

    if WHOIS_AVAILABLE:
        return _whois_module

    try:
        import whois
        _whois_module = whois
        WHOIS_AVAILABLE = True
        return _whois_module
    except ImportError:
        WHOIS_AVAILABLE = False
        logger.warning("python-whois package not installed. WHOIS verification will be disabled.")
        return None


from config import config


def parse_txt_record(record: str) -> Optional[Dict[str, str]]:
    """
    Parse a d.onl TXT record string into a dict.

    Expected format: 'd.onl;wallet=3Pxxx...'
    Returns dict with parsed key-value pairs, or None if not a valid d.onl record.
    """
    if not record or not isinstance(record, str):
        return None

    record = record.strip().strip('"').strip("'")

    if not record.startswith(config.TXT_RECORD_PREFIX):
        return None

    result = {}
    parts = record.split(config.TXT_FIELD_SEPARATOR)

    for part in parts[1:]:  # Skip the prefix
        part = part.strip()
        if config.TXT_KEY_VALUE_SEPARATOR in part:
            key, value = part.split(config.TXT_KEY_VALUE_SEPARATOR, 1)
            result[key.strip().lower()] = value.strip()

    return result if result else None


# ============================================================================
# DNS VERIFICATION
# ============================================================================

class DNSVerifier:
    """Handles DNS TXT record verification with multiple resolvers."""

    def __init__(self):
        """Initialize DNS resolver with configured settings."""
        self.dns_resolver, self.dns_exception = _import_dns()
        self.timeout = config.DNS_TIMEOUT
        self.resolvers = self._create_resolvers()

    def _create_resolvers(self) -> List:
        """Create DNS resolver instances for each configured resolver."""
        resolvers = []
        for nameserver in config.DNS_RESOLVERS:
            resolver = self.dns_resolver.Resolver()
            resolver.nameservers = [nameserver]
            resolver.timeout = self.timeout
            resolver.lifetime = self.timeout
            resolvers.append(resolver)
        return resolvers

    def query_txt_records(self, domain: str, resolver) -> List[str]:
        """Query TXT records for a domain using specific resolver."""
        try:
            answers = resolver.resolve(domain, 'TXT')
            records = []
            for rdata in answers:
                txt_strings = [s.decode('utf-8') if isinstance(s, bytes) else str(s)
                              for s in rdata.strings]
                records.append(''.join(txt_strings))
            return records
        except self.dns_resolver.NXDOMAIN:
            logger.warning(f"Domain {domain} does not exist (NXDOMAIN)")
            return []
        except self.dns_resolver.NoAnswer:
            logger.warning(f"No TXT records found for {domain}")
            return []
        except self.dns_exception.Timeout:
            logger.warning(f"DNS query timeout for {domain} using {resolver.nameservers[0]}")
            return []
        except Exception as e:
            logger.error(f"DNS query error for {domain}: {e}")
            return []

    def verify_txt_with_consensus(self, domain: str) -> Tuple[bool, List[str]]:
        """Query multiple DNS resolvers and require consensus."""
        all_records = []
        successful_queries = 0

        for resolver in self.resolvers:
            try:
                records = self.query_txt_records(domain, resolver)
                if records:
                    all_records.extend(records)
                    successful_queries += 1
                    logger.debug(f"Resolver {resolver.nameservers[0]} found {len(records)} TXT records for {domain}")
            except Exception as e:
                logger.error(f"Error querying resolver {resolver.nameservers[0]}: {e}")
                continue

        if successful_queries < config.DNS_CONSENSUS_MINIMUM:
            logger.warning(f"Not enough resolvers agreed for {domain} ({successful_queries}/{config.DNS_CONSENSUS_MINIMUM})")
            return False, []

        unique_records = list(dict.fromkeys(all_records))
        return True, unique_records

    def query_a_records(self, domain: str, resolver) -> List[str]:
        """Query A records for a domain using specific resolver."""
        try:
            answers = resolver.resolve(domain, 'A')
            return [str(rdata.address) for rdata in answers]
        except self.dns_resolver.NXDOMAIN:
            logger.warning(f"Domain {domain} does not exist (NXDOMAIN)")
            return []
        except self.dns_resolver.NoAnswer:
            logger.warning(f"No A records found for {domain}")
            return []
        except self.dns_exception.Timeout:
            logger.warning(f"DNS query timeout for {domain} using {resolver.nameservers[0]}")
            return []
        except Exception as e:
            logger.error(f"DNS query error for {domain}: {e}")
            return []

    def verify_a_record_with_consensus(self, domain: str) -> Tuple[bool, Optional[str]]:
        """Check if domain's A-record points to our server IP."""
        all_ips = []
        successful_queries = 0

        for resolver in self.resolvers:
            try:
                ips = self.query_a_records(domain, resolver)
                if ips:
                    all_ips.extend(ips)
                    successful_queries += 1
                    logger.debug(f"Resolver {resolver.nameservers[0]} found A records for {domain}: {ips}")
            except Exception as e:
                logger.error(f"Error querying A record from resolver {resolver.nameservers[0]}: {e}")
                continue

        if successful_queries < config.DNS_CONSENSUS_MINIMUM:
            logger.warning(f"Not enough resolvers agreed for A record of {domain} ({successful_queries}/{config.DNS_CONSENSUS_MINIMUM})")
            return False, None

        unique_ips = list(dict.fromkeys(all_ips))
        if not unique_ips:
            return False, None

        resolved_ip = unique_ips[0]
        points_to_us = resolved_ip.strip() == config.OUR_SERVER_IP.strip()

        if points_to_us:
            logger.info(f"Domain {domain} A-record points to our server IP: {resolved_ip}")
        else:
            logger.info(f"Domain {domain} A-record: {resolved_ip}, expected: {config.OUR_SERVER_IP}")

        return points_to_us, resolved_ip

    def find_donl_record(self, domain: str) -> Optional[Dict[str, str]]:
        """Find and parse d.onl TXT record for a domain."""
        # Check _mining subdomain first
        mining_domain = f"_mining.{domain}"
        logger.info(f"Checking TXT records for {mining_domain}")
        success, records = self.verify_txt_with_consensus(mining_domain)

        if success and records:
            for record in records:
                parsed = parse_txt_record(record)
                if parsed:
                    logger.info(f"Found valid d.onl record at {mining_domain}")
                    return parsed

        # Fallback: check root domain
        logger.info(f"Checking TXT records for root domain {domain}")
        success, records = self.verify_txt_with_consensus(domain)

        if not success:
            logger.warning(f"DNS verification failed for both {mining_domain} and {domain}")
            return None

        for record in records:
            parsed = parse_txt_record(record)
            if parsed:
                logger.info(f"Found valid d.onl record at root domain {domain}")
                return parsed

        logger.warning(f"No valid d.onl TXT record found for {domain}")
        return None

    def verify_domain_ownership(self, domain: str, expected_wallet: str,
                                expected_nonce: str = None) -> bool:
        """Verify domain ownership by checking TXT record."""
        record = self.find_donl_record(domain)
        if not record:
            return False

        record_wallet = record.get('wallet', '')
        if not record_wallet or not expected_wallet:
            logger.warning(f"Missing wallet in record or expected wallet for {domain}")
            return False

        wallet_match = record_wallet.lower() == expected_wallet.lower()
        if wallet_match:
            logger.info(f"Domain ownership verified for {domain}")
        else:
            logger.warning(f"Wallet mismatch for {domain}: expected {expected_wallet}, got {record_wallet}")

        return wallet_match


# ============================================================================
# WHOIS VERIFICATION
# ============================================================================

class WHOISVerifier:
    """Handles WHOIS expiry date checking."""

    def __init__(self):
        self.cache_duration = timedelta(days=config.WHOIS_RECHECK_INTERVAL_DAYS)

    def get_domain_expiry(self, domain: str) -> Optional[datetime]:
        """Get domain expiry date from WHOIS."""
        whois_module = _import_whois()
        if not whois_module:
            return None

        try:
            logger.info(f"Querying WHOIS for {domain}")
            w = whois_module.whois(domain)
            expiry = w.expiration_date

            if isinstance(expiry, list):
                expiry = expiry[0] if expiry else None

            if expiry:
                logger.info(f"Domain {domain} expires on {expiry}")
            return expiry
        except Exception as e:
            logger.error(f"WHOIS query error for {domain}: {e}")
            return None

    def is_domain_expired(self, domain: str) -> Tuple[bool, Optional[datetime]]:
        """Check if domain is expired."""
        expiry = self.get_domain_expiry(domain)
        if expiry is None:
            return False, None

        is_expired = expiry < datetime.now()
        if is_expired:
            logger.warning(f"Domain {domain} is EXPIRED (expired on {expiry})")
        return is_expired, expiry

    def should_check_whois(self, last_check: Optional[datetime]) -> bool:
        """Determine if WHOIS should be checked again."""
        if last_check is None:
            return True
        return (datetime.now() - last_check) >= self.cache_duration


# ============================================================================
# COMBINED VERIFIER
# ============================================================================

class DomainVerifier:
    """Combined domain verifier using both DNS and WHOIS with retry logic."""

    def __init__(self):
        self.dns_verifier = DNSVerifier()
        self.whois_verifier = WHOISVerifier()

    def verify_with_retry(self, domain: str, expected_wallet: str,
                         expected_nonce: str = None, max_retries: int = None) -> bool:
        """Verify domain with retry logic and exponential backoff."""
        if max_retries is None:
            max_retries = config.MAX_RETRIES

        wait_time = config.RETRY_INITIAL_WAIT

        for attempt in range(max_retries):
            try:
                result = self.dns_verifier.verify_domain_ownership(
                    domain, expected_wallet, expected_nonce
                )
                if result:
                    return True

                if attempt < max_retries - 1:
                    logger.info(f"Retry {attempt + 1}/{max_retries} for {domain} in {wait_time}s")
                    time.sleep(wait_time)
                    wait_time *= config.RETRY_BACKOFF_FACTOR
            except Exception as e:
                logger.error(f"Verification attempt {attempt + 1} failed for {domain}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    wait_time *= config.RETRY_BACKOFF_FACTOR

        logger.error(f"All verification attempts failed for {domain}")
        return False

    def full_verification(self, domain: str, expected_wallet: str,
                         expected_nonce: str = None, check_whois: bool = True) -> Dict[str, any]:
        """Perform full verification including DNS and optionally WHOIS."""
        result = {
            'success': False,
            'dns_verified': False,
            'whois_checked': False,
            'is_expired': False,
            'expiry_date': None,
            'error': None
        }

        try:
            dns_ok = self.verify_with_retry(domain, expected_wallet, expected_nonce)
            result['dns_verified'] = dns_ok

            if not dns_ok:
                result['error'] = 'DNS verification failed'
                return result

            if check_whois and config.ENABLE_WHOIS_CHECK:
                try:
                    is_expired, expiry_date = self.whois_verifier.is_domain_expired(domain)
                    result['whois_checked'] = True
                    result['is_expired'] = is_expired
                    result['expiry_date'] = expiry_date

                    if is_expired:
                        result['error'] = 'Domain is expired'
                        return result
                except Exception as e:
                    logger.warning(f"WHOIS check failed for {domain}: {e}")
                    result['whois_checked'] = False

            result['success'] = True
            return result
        except Exception as e:
            logger.error(f"Full verification error for {domain}: {e}")
            result['error'] = str(e)
            return result

    def quick_check(self, domain: str, expected_wallet: str,
                   expected_nonce: str = None) -> bool:
        """Quick verification check (DNS only, single attempt)."""
        try:
            return self.dns_verifier.verify_domain_ownership(
                domain, expected_wallet, expected_nonce
            )
        except Exception as e:
            logger.error(f"Quick check error for {domain}: {e}")
            return False


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_verifier_instance = None


def get_verifier() -> DomainVerifier:
    """Get domain verifier singleton instance."""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = DomainVerifier()
    return _verifier_instance
