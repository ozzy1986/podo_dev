"""
Application Configuration using Pydantic Settings.
Replaces config/config.py with type-safe, validated configuration.
"""

import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path relative to project root (parent of app/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILE = os.path.join(_PROJECT_ROOT, '.env')

# Load .env into os.environ before any Settings load (ensures nested models get values)
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE)
except ImportError:
    pass


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='PG_',
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    host: str = Field(default='localhost', description='PostgreSQL host')
    port: int = Field(default=5432, description='PostgreSQL port')
    database: str = Field(default='domain_mining', description='Database name')
    user: str = Field(default='domain_user', description='Database user')
    password: str = Field(default='', description='Database password')
    
    # Connection pool settings
    pool_min_size: int = Field(default=2, description='Minimum pool connections')
    pool_max_size: int = Field(default=10, description='Maximum pool connections')
    pool_timeout: float = Field(default=30.0, description='Pool connection timeout')
    
    @property
    def dsn(self) -> str:
        """Build PostgreSQL DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class ClickHouseSettings(BaseSettings):
    """ClickHouse database configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='CH_',
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    host: str = Field(default='localhost', description='ClickHouse host')
    port: int = Field(default=9000, description='ClickHouse native port')
    database: str = Field(default='domain_mining', description='Database name')
    user: str = Field(default='default', description='ClickHouse user')
    password: str = Field(default='', description='ClickHouse password')


class BlockchainSettings(BaseSettings):
    """Waves blockchain configuration."""
    
    model_config = SettingsConfigDict(case_sensitive=True)
    
    # Token configuration
    token_asset_id: str = Field(
        default="6Q7Q6phS6ZnL3V28YGKAp2qJ6bWjYwsPbuciteTeLdKn",
        description='DOMAIN token asset ID'
    )
    token_decimals: int = Field(default=8, description='Token decimals')
    token_name: str = Field(default='DOMAIN', description='Token name')
    
    # Smart contract addresses
    dapp_address: str = Field(
        default="3P_DUMMY_DAPP_ADDRESS_REPLACE_ME",
        env='DAPP_ADDRESS',
        description='DApp smart contract address'
    )
    oracle_address: str = Field(
        default="3N7KEH73pBRE4HZ83PX91uj9Kf6fG4dLEjW",
        env='ORACLE_ADDRESS',
        description='Oracle wallet address'
    )
    
    # Node configuration
    waves_node_url: str = Field(
        default="https://nodes.wavesnodes.com",
        env='WAVES_NODE_URL',
        description='Waves node URL'
    )
    waves_chain_id: str = Field(
        default="W",
        env='WAVES_CHAIN_ID',
        description='Waves chain ID (W=mainnet, T=testnet)'
    )
    
    # Transaction settings
    tx_max_retries: int = Field(default=5, description='Max transaction retries')
    tx_retry_wait: int = Field(default=3, description='Seconds between retries')
    tx_confirmation_timeout: int = Field(default=60, description='Confirmation timeout')


class DNSSettings(BaseSettings):
    """DNS verification configuration."""
    
    model_config = SettingsConfigDict(case_sensitive=False)
    
    # DNS resolvers for consensus
    resolvers: List[str] = Field(
        default=['1.1.1.1', '8.8.8.8', '9.9.9.9', '208.67.222.222'],
        description='DNS resolvers for consensus'
    )
    consensus_minimum: int = Field(default=2, description='Minimum resolvers that must agree')
    timeout: int = Field(default=10, description='DNS query timeout in seconds')
    enable_dnssec: bool = Field(default=True, description='Enable DNSSEC validation')
    
    # Server IP for A-record verification
    our_server_ip: str = Field(
        default='193.33.170.175',
        env='OUR_SERVER_IP',
        description='Our server IP for A-record verification'
    )
    
    # TXT record format
    txt_record_prefix: str = Field(default='d.onl', description='TXT record prefix')
    txt_field_separator: str = Field(default=';', description='Field separator')
    txt_key_value_separator: str = Field(default='=', description='Key-value separator')


class SecuritySettings(BaseSettings):
    """Security and authentication configuration."""
    
    model_config = SettingsConfigDict(case_sensitive=False)
    
    # JWT settings
    jwt_secret_key: str = Field(
        default='CHANGE_ME_IN_PRODUCTION',
        env='JWT_SECRET_KEY',
        description='JWT signing secret'
    )
    jwt_algorithm: str = Field(default='HS256', description='JWT algorithm')
    jwt_expiry_hours: int = Field(default=720, description='JWT expiry in hours (30 days)')
    
    # Password hashing
    bcrypt_rounds: int = Field(default=12, description='Bcrypt rounds')
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, description='Requests per minute per IP')
    rate_limit_burst: int = Field(default=10, description='Burst allowance')
    
    # Nonce settings
    nonce_length_bytes: int = Field(default=12, description='Nonce length in bytes')
    nonce_expiry_hours: int = Field(default=72, description='Nonce validity hours')
    
    # CORS (str in .env: "*" or "https://a.com,https://b.com" - avoid JSON)
    cors_origins: str = Field(
        default='*',
        env='CORS_ORIGINS',
        description='Allowed CORS origins (comma-separated, * for all)'
    )
    
    def get_cors_origins_list(self) -> List[str]:
        """Return CORS origins as list for middleware."""
        if not self.cors_origins or self.cors_origins.strip() == '*':
            return ['*']
        return [x.strip() for x in self.cors_origins.split(',') if x.strip()]


class DomainSettings(BaseSettings):
    """Domain validation and mining configuration."""
    
    model_config = SettingsConfigDict(case_sensitive=False)
    
    # Validation rules
    min_domain_length: int = Field(default=3, description='Minimum domain length')
    max_domain_length: int = Field(default=253, description='Maximum domain length (RFC 1035)')
    max_domains_per_user: int = Field(default=100, description='Max domains per user')
    
    # Mining settings
    max_failed_checks: int = Field(default=3, description='Failed checks before disabling')
    whois_recheck_interval_days: int = Field(default=30, description='WHOIS recheck interval')
    
    # Reward settings
    oracle_check_interval_seconds: int = Field(
        default=43200,
        description='Oracle check interval (12 hours)'
    )
    min_reward_interval_ms: int = Field(
        default=60000,
        description='Min interval between rewards (ms)'
    )
    max_tokens_per_claim: float = Field(
        default=1000.0,
        description='Max tokens per single claim'
    )


class RetrySettings(BaseSettings):
    """Retry configuration for external services."""
    
    model_config = SettingsConfigDict(case_sensitive=False)
    
    max_retries: int = Field(default=3, description='Maximum retry attempts')
    backoff_factor: float = Field(default=2.0, description='Exponential backoff factor')
    initial_wait: float = Field(default=1.0, description='Initial wait in seconds')


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # Environment
    app_env: str = Field(default='production', env='APP_ENV', description='Environment')
    site_url: str = Field(default='https://d.onl', env='SITE_URL', description='Site URL')
    debug: bool = Field(default=False, description='Debug mode')
    
    # Logging
    log_level: str = Field(default='INFO', description='Log level')
    log_format: str = Field(
        default='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        description='Log format'
    )
    log_dir: str = Field(default='logs', description='Log directory')
    
    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    blockchain: BlockchainSettings = Field(default_factory=BlockchainSettings)
    dns: DNSSettings = Field(default_factory=DNSSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    domain: DomainSettings = Field(default_factory=DomainSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env.lower().strip() == 'development'
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower().strip() == 'production'
    
    def validate_production_config(self) -> None:
        """
        Validate that critical settings are properly configured for production.
        Raises ValueError if insecure defaults are detected in production mode.
        """
        if not self.is_production:
            return
        
        errors = []
        
        if self.security.jwt_secret_key == 'CHANGE_ME_IN_PRODUCTION':
            errors.append("JWT_SECRET_KEY must be set to a secure value in production")
        
        if len(self.security.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters in production")
        
        if 'DUMMY' in self.blockchain.dapp_address.upper():
            errors.append("DAPP_ADDRESS must be set to a real contract address in production")
        
        if not self.database.password:
            errors.append("PG_PASSWORD must be set in production")
        
        if errors:
            error_msg = "Production configuration validation failed:\n  - " + "\n  - ".join(errors)
            raise ValueError(error_msg)


# Global settings instance (lazy loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience function for backward compatibility
def is_development() -> bool:
    """Check if running in development mode."""
    return get_settings().is_development
