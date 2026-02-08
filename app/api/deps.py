"""
FastAPI dependencies for dependency injection.
"""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings, Settings
from app.core.security import SecurityManager
from app.db.postgresql import get_pg_pool, PostgreSQLDatabase
from app.db.clickhouse import get_ch_client, ClickHouseDatabase
from app.repositories.user_repo import UserRepository
from app.repositories.domain_repo import DomainRepository
from app.repositories.reward_repo import RewardRepository
from app.repositories.payout_repo import PayoutRepository
from app.repositories.ssl_repo import SSLRepository
from app.repositories.comment_repo import CommentRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.domain_service import DomainService
from app.services.dns_service import DNSService
from app.core.exceptions import AuthError


# Settings dependency
def get_app_settings() -> Settings:
    """Get application settings."""
    return get_settings()


# Database dependencies
def get_db() -> PostgreSQLDatabase:
    """Get PostgreSQL database."""
    return get_pg_pool()


def get_ch() -> ClickHouseDatabase:
    """Get ClickHouse database."""
    return get_ch_client()


# Repository dependencies
def get_user_repo(db: PostgreSQLDatabase = Depends(get_db)) -> UserRepository:
    """Get user repository."""
    return UserRepository(db)


def get_domain_repo(db: PostgreSQLDatabase = Depends(get_db)) -> DomainRepository:
    """Get domain repository."""
    return DomainRepository(db)


def get_reward_repo(
    db: PostgreSQLDatabase = Depends(get_db),
    ch: ClickHouseDatabase = Depends(get_ch)
) -> RewardRepository:
    """Get reward repository."""
    return RewardRepository(db, ch)


def get_payout_repo(db: PostgreSQLDatabase = Depends(get_db)) -> PayoutRepository:
    """Get payout repository."""
    return PayoutRepository(db)


def get_ssl_repo(db: PostgreSQLDatabase = Depends(get_db)) -> SSLRepository:
    """Get SSL repository."""
    return SSLRepository(db)


def get_comment_repo(db: PostgreSQLDatabase = Depends(get_db)) -> CommentRepository:
    """Get comment repository."""
    return CommentRepository(db)


# Security dependency
def get_security(settings: Settings = Depends(get_app_settings)) -> SecurityManager:
    """Get security manager."""
    return SecurityManager(settings.security)


# Service dependencies
def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repo),
    security: SecurityManager = Depends(get_security)
) -> AuthService:
    """Get auth service."""
    return AuthService(user_repo, security)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repo),
    domain_repo: DomainRepository = Depends(get_domain_repo)
) -> UserService:
    """Get user service."""
    return UserService(user_repo, domain_repo)


def get_domain_service(
    domain_repo: DomainRepository = Depends(get_domain_repo),
    user_repo: UserRepository = Depends(get_user_repo),
    settings: Settings = Depends(get_app_settings)
) -> DomainService:
    """Get domain service."""
    return DomainService(domain_repo, user_repo, settings.domain)


def get_dns_service(settings: Settings = Depends(get_app_settings)) -> DNSService:
    """Get DNS service."""
    return DNSService(settings.dns)


# Authentication dependency
async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Get current authenticated user from JWT token.
    
    Args:
        authorization: Authorization header (Bearer token)
        x_auth_token: Alternative auth token header
        auth_service: Auth service
    
    Returns:
        Current user dictionary
    
    Raises:
        HTTPException: If authentication fails
    """
    # Extract token from headers
    token = None
    
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]
    
    if not token and x_auth_token:
        token = x_auth_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Verify token and get user
    try:
        user = await auth_service.get_current_user(token)
        return user
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


# Optional authentication dependency
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Get current user if authenticated, None otherwise.
    
    Args:
        authorization: Authorization header (Bearer token)
        x_auth_token: Alternative auth token header
        auth_service: Auth service
    
    Returns:
        Current user dictionary or None
    """
    try:
        return await get_current_user(authorization, x_auth_token, auth_service)
    except HTTPException:
        return None
