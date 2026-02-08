"""
Authentication service for user authentication and authorization.
"""

import logging
from typing import Dict, Any

from app.repositories.user_repo import UserRepository
from app.core.security import SecurityManager
from app.core.exceptions import AuthError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, user_repo: UserRepository, security: SecurityManager):
        self.user_repo = user_repo
        self.security = security

    def _build_auth_response(self, user: dict) -> Dict[str, Any]:
        """Build a standard auth response with access + refresh tokens."""
        tokens = self.security.create_token_pair(
            user_id=user['id'],
            wallet_address=user.get('wallet'),
        )
        return {
            'user': user,
            'token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
        }

    async def register_with_email(
        self,
        email: str,
        password: str,
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Register a new user with email and password."""
        if not email or '@' not in email:
            raise ValidationError("Invalid email address")
        if not password or len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")

        password_hash = self.security.hash_password(password)
        user = await self.user_repo.create(
            email=email,
            password_hash=password_hash,
            language=language,
        )
        logger.info("user_registered user_id=%d email=%s", user['id'], email)
        return self._build_auth_response(user)

    async def login_with_email(self, email: str, password: str) -> Dict[str, Any]:
        """Login with email and password."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AuthError("Invalid email or password")

        if not user.get('password_hash'):
            raise AuthError("Password authentication not available for this account")

        if not self.security.verify_password(password, user['password_hash']):
            raise AuthError("Invalid email or password")

        logger.info("user_login_email user_id=%d", user['id'])
        return self._build_auth_response(user)

    async def login_with_wallet(
        self,
        wallet_address: str,
        signature: str,
        public_key: str,
        message: str,
        host: str = "",
        referrer: str = "",
    ) -> Dict[str, Any]:
        """Login with Waves wallet signature (supports WX Network callback; referrer = full origin, host = hostname)."""
        if not self.security.verify_waves_signature(
            message, signature, public_key, host=host or None, referrer=referrer or None
        ):
            raise AuthError("Invalid signature")

        user = await self.user_repo.get_by_wallet(wallet_address)
        if not user:
            user = await self.user_repo.create(wallet_address=wallet_address)

        logger.info("user_login_wallet user_id=%d wallet=%s", user['id'], wallet_address)
        return self._build_auth_response(user)

    async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
        """
        Exchange a valid refresh token for a new access + refresh token pair.

        Args:
            refresh_token: A JWT refresh token.

        Returns:
            Dict with ``token``, ``refresh_token``, and ``user``.

        Raises:
            AuthError: If the refresh token is invalid or expired.
        """
        payload = self.security.verify_jwt_token(refresh_token, expected_type="refresh")

        user_id = payload.get('user_id')
        if not user_id:
            raise AuthError("Invalid refresh token payload")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthError("User no longer exists")

        logger.info("token_refreshed user_id=%d", user_id)
        return self._build_auth_response(user)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT access token and return user."""
        payload = self.security.verify_jwt_token(token, expected_type="access")

        user_id = payload.get('user_id')
        if not user_id:
            raise AuthError("Invalid token payload")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        return user

    async def get_current_user(self, token: str) -> Dict[str, Any]:
        """Get current user from token."""
        return await self.verify_token(token)
