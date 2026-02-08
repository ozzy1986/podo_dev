"""
Domain IDN (Internationalized Domain Name) utilities.
Normalize Punycode (xn--...) to Unicode for DB lookups.
"""

import logging

logger = logging.getLogger(__name__)


def normalize_domain_for_lookup(domain: str) -> str:
    """
    Normalize domain for database lookup.
    - Strips leading "www." so that www.example.com and example.com match the same record.
    - Converts Punycode (e.g. xn--b1afblhileddcsait4e7g.xn--p1ai) to Unicode (пример.рф)
      so that lookups work regardless of whether the URL uses Punycode or Unicode.

    Returns the domain unchanged if it's already Unicode or if decoding fails.
    """
    if not domain or not isinstance(domain, str):
        return domain
    s = domain.strip().lower()
    if s.startswith("www.") and len(s) > 4:
        s = s[4:]
    if "xn--" not in s:
        return s
    try:
        import idna
        decoded = idna.decode(s)
        if decoded != s:
            logger.debug("Normalized domain for lookup: %r -> %r", s, decoded)
        return decoded
    except Exception as e:
        logger.debug("IDNA decode failed for %r: %s; using as-is", s, e)
        return s
