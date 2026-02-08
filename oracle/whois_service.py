"""
WHOIS Service for domain age lookup.
Provides creation date, registrar and name servers retrieval with caching and rate limiting.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Tuple, List
import time

logger = logging.getLogger(__name__)

# Cache: domain -> (creation_date, cache_timestamp)
_whois_cache: Dict[str, Tuple[Optional[datetime], float]] = {}
# Cache for full WHOIS extra: domain -> (creation_date, registrar_name, name_servers_list, cache_timestamp)
_whois_extra_cache: Dict[str, Tuple[Optional[datetime], Optional[str], List[str], float]] = {}
CACHE_TTL = 86400  # 24 hours in seconds

# Rate limiting
_last_query_time = 0.0
MIN_QUERY_INTERVAL = 1.0  # 1 second between queries

def _rate_limit():
    """Enforce rate limiting between WHOIS queries."""
    global _last_query_time
    now = time.time()
    elapsed = now - _last_query_time
    if elapsed < MIN_QUERY_INTERVAL:
        time.sleep(MIN_QUERY_INTERVAL - elapsed)
    _last_query_time = time.time()


def _normalize_hoster_from_ns(ns_host: str) -> str:
    """
    Derive hoster name from NS hostname (e.g. ns1.reg.ru -> reg.ru).
    Strips leading labels that look like ns1, ns2, dns1, etc.
    """
    if not ns_host or not isinstance(ns_host, str):
        return ""
    s = ns_host.strip().lower()
    if not s:
        return ""
    parts = s.split(".")
    if len(parts) >= 2:
        first = parts[0]
        if re.match(r"^ns\d*$", first) or re.match(r"^dns\d*$", first) or first in ("ns", "dns"):
            return ".".join(parts[1:])
    return s


def get_domain_whois_extra(domain: str) -> Tuple[Optional[datetime], Optional[str], List[str]]:
    """
    Lookup domain creation date, registrar name and name servers via WHOIS.
    Returns (creation_date, registrar_name, name_servers_list).
    name_servers_list is normalized to lowercase strings.
    """
    if domain in _whois_extra_cache:
        cached = _whois_extra_cache[domain]
        if (time.time() - cached[3]) < CACHE_TTL:
            logger.debug(f"WHOIS extra cache hit for {domain}")
            return (cached[0], cached[1], cached[2])

    try:
        import whois
        _rate_limit()
        logger.debug(f"WHOIS query for {domain} (extra)")
        w = whois.whois(domain)

        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0] if creation_date else None
        if creation_date and not isinstance(creation_date, datetime):
            try:
                creation_date = datetime.fromisoformat(str(creation_date))
            except ValueError:
                creation_date = None

        registrar_name = None
        if getattr(w, "registrar", None):
            r = w.registrar
            if isinstance(r, list):
                r = r[0] if r else None
            if r and isinstance(r, str) and r.strip():
                registrar_name = r.strip()

        name_servers = []
        if getattr(w, "name_servers", None):
            ns = w.name_servers
            if ns is None:
                ns = []
            if not isinstance(ns, list):
                ns = [ns] if ns else []
            for n in ns:
                if n and isinstance(n, str) and n.strip():
                    name_servers.append(n.strip().lower())

        _whois_extra_cache[domain] = (creation_date, registrar_name, name_servers, time.time())
        if creation_date:
            logger.info(f"WHOIS: {domain} created on {creation_date.date()}, registrar={registrar_name}, ns={len(name_servers)}")
        return (creation_date, registrar_name, name_servers)

    except ImportError:
        logger.warning("python-whois not installed. Run: pip install python-whois")
        _whois_extra_cache[domain] = (None, None, [], time.time())
        return (None, None, [])
    except Exception as e:
        logger.warning(f"WHOIS lookup failed for {domain}: {e}")
        _whois_extra_cache[domain] = (None, None, [], time.time())
        return (None, None, [])


def get_domain_creation_date(domain: str) -> Optional[datetime]:
    """
    Lookup domain creation date via WHOIS.
    
    Args:
        domain: Domain name (e.g., "example.com")
        
    Returns:
        Creation date or None if lookup fails.
    """
    # Check cache first
    if domain in _whois_cache:
        cached_date, cached_time = _whois_cache[domain]
        if (time.time() - cached_time) < CACHE_TTL:
            logger.debug(f"WHOIS cache hit for {domain}")
            return cached_date
    
    try:
        # Try to import whois (optional dependency)
        import whois
        
        # Rate limit
        _rate_limit()
        
        logger.debug(f"WHOIS query for {domain}")
        w = whois.whois(domain)
        
        # Handle different WHOIS response formats
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        
        # Normalize to datetime
        if creation_date and not isinstance(creation_date, datetime):
            try:
                creation_date = datetime.fromisoformat(str(creation_date))
            except ValueError:
                creation_date = None
        
        # Cache result (even if None)
        _whois_cache[domain] = (creation_date, time.time())
        
        if creation_date:
            logger.info(f"WHOIS: {domain} created on {creation_date.date()}")
        
        return creation_date
            
    except ImportError:
        logger.warning("python-whois not installed. Run: pip install python-whois")
        return None
    except Exception as e:
        logger.warning(f"WHOIS lookup failed for {domain}: {e}")
        # Cache the failure to avoid repeated queries
        _whois_cache[domain] = (None, time.time())
        return None

def get_domain_age_years(domain: str, fallback_to_zero: bool = True) -> float:
    """
    Get domain age in years.
    
    Args:
        domain: Domain name
        fallback_to_zero: If True, return 0 years if WHOIS fails
        
    Returns:
        Age in years (float)
        
    Raises:
        ValueError: If fallback_to_zero is False and WHOIS fails
    """
    creation_date = get_domain_creation_date(domain)
    
    if creation_date:
        now = datetime.now()
        if creation_date > now:
            # Future date? Treat as new
            logger.warning(f"Domain {domain} has future creation date: {creation_date}")
            return 0.0
        delta = now - creation_date
        return delta.total_seconds() / (365.25 * 24 * 3600)
    
    if fallback_to_zero:
        logger.info(f"Using age=0 for {domain} (WHOIS unavailable)")
        return 0.0
    
    raise ValueError(f"Could not determine age for {domain}")

def clear_cache():
    """Clear the WHOIS cache. Useful for testing."""
    global _whois_cache, _whois_extra_cache
    _whois_cache = {}
    _whois_extra_cache = {}
    logger.info("WHOIS cache cleared")

def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics."""
    now = time.time()
    valid = sum(1 for _, (_, ts) in _whois_cache.items() if (now - ts) < CACHE_TTL)
    extra_valid = sum(1 for _, (_, _, _, ts) in _whois_extra_cache.items() if (now - ts) < CACHE_TTL)
    return {
        'total_entries': len(_whois_cache),
        'valid_entries': valid,
        'expired_entries': len(_whois_cache) - valid,
        'extra_total_entries': len(_whois_extra_cache),
        'extra_valid_entries': extra_valid,
    }

