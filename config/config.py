"""
d.onl System Configuration
All constants and configuration values for the oracle/background processing system.

Note: DAPP_ADDRESS and ORACLE_ADDRESS can be set in .env file,
which will override these defaults.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Environment
APP_ENV = os.getenv('APP_ENV', 'production').strip().lower()


def is_development() -> bool:
    """Return True if running in development (dev.d.onl)."""
    return APP_ENV == 'development'


# ============================================================================
# WAVES BLOCKCHAIN CONFIGURATION
# ============================================================================

TOKEN_ASSET_ID = "6Q7Q6phS6ZnL3V28YGKAp2qJ6bWjYwsPbuciteTeLdKn"
TOKEN_DECIMALS = 8
TOKEN_NAME = "DOMAIN"

DAPP_ADDRESS = os.getenv('DAPP_ADDRESS', "3P_DUMMY_DAPP_ADDRESS_REPLACE_ME")
ORACLE_ADDRESS = os.getenv('ORACLE_ADDRESS', "3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW")

WAVES_NODE_URL = "https://nodes.wavesnodes.com"
WAVES_CHAIN_ID = "W"

# ============================================================================
# REWARD CONFIGURATION
# ============================================================================

REWARD_BY_LENGTH = {
    1: 36666.0,
    2: 2263.0,
    3: 1398.0,
    4: 864.0,
    5: 534.0,
}

DECAY_FACTOR = 534.0 / 864.0  # ~0.618 (inverse golden ratio)

REWARD_BY_LENGTH_UNITS = {
    L: int(amount * (10 ** TOKEN_DECIMALS))
    for L, amount in REWARD_BY_LENGTH.items()
}

ORACLE_CHECK_INTERVAL_SECONDS = 12 * 60 * 60
MIN_REWARD_INTERVAL_MS = 60 * 1000
MAX_TOKENS_PER_CLAIM = 1000.0
MAX_TOKENS_PER_CLAIM_UNITS = int(MAX_TOKENS_PER_CLAIM * (10 ** TOKEN_DECIMALS))

# ============================================================================
# DOMAIN VALIDATION RULES
# ============================================================================

MIN_DOMAIN_LENGTH = 3
MAX_DOMAIN_LENGTH = 253
MAX_DOMAINS_PER_USER = 100
MAX_FAILED_CHECKS = 3
WHOIS_RECHECK_INTERVAL_DAYS = 30

# ============================================================================
# DNS VERIFICATION CONFIGURATION
# ============================================================================

DNS_RESOLVERS = [
    '1.1.1.1',
    '8.8.8.8',
    '9.9.9.9',
    '208.67.222.222',
]
DNS_CONSENSUS_MINIMUM = 2
DNS_TIMEOUT = 10
DNS_ENABLE_DNSSEC = True

OUR_SERVER_IP = os.getenv('OUR_SERVER_IP', '193.33.170.175')

# ============================================================================
# TXT RECORD FORMAT
# ============================================================================

TXT_RECORD_PREFIX = "d.onl"
TXT_FIELD_SEPARATOR = ";"
TXT_KEY_VALUE_SEPARATOR = "="

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DB_POOL_SIZE = 5
DB_POOL_OVERFLOW = 10
DB_POOL_TIMEOUT = 30
ORACLE_BATCH_SIZE = 10

# ============================================================================
# SECURITY & RATE LIMITING
# ============================================================================

NONCE_LENGTH_BYTES = 12
NONCE_EXPIRY_HOURS = 72
RATE_LIMIT_ADDDOMAIN_PER_HOUR = 10
RATE_LIMIT_VERIFY_PER_HOUR = 20

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_DIR = "logs"
ORACLE_LOG_FILE = "logs/oracle.log"
MAX_LOG_SIZE_MB = 10
LOG_BACKUP_COUNT = 5

# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_INITIAL_WAIT = 1
WAVES_TX_MAX_RETRIES = 5
WAVES_TX_RETRY_WAIT = 3
WAVES_TX_CONFIRMATION_TIMEOUT = 60

# ============================================================================
# FEATURE FLAGS
# ============================================================================

ENABLE_WHOIS_CHECK = True
ENABLE_DNSSEC_VALIDATION = True

# ============================================================================
# CONSTANTS
# ============================================================================

DOMAIN_STATUS_PENDING = 'pending'
DOMAIN_STATUS_VERIFIED = 'verified'
DOMAIN_STATUS_MINING = 'mining'
DOMAIN_STATUS_STOPPED = 'stopped'
DOMAIN_STATUS_FAILED = 'failed'

REWARD_STATUS_PENDING = 'pending'
REWARD_STATUS_CONFIRMED = 'confirmed'
REWARD_STATUS_FAILED = 'failed'
