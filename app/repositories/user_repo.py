"""
User repository for database operations.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundError, ConflictError


class UserRepository(BaseRepository):
    """Repository for user operations."""
    
    async def create(
        self,
        wallet_address: Optional[str] = None,
        telegram_id: Optional[int] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            wallet_address: Waves wallet address
            telegram_id: Telegram user ID (legacy)
            username: Username
            email: Email address
            password_hash: Hashed password
            language: Language code
        
        Returns:
            Created user dictionary
        
        Raises:
            ConflictError: If user already exists
        """
        # Check for duplicates
        if wallet_address:
            exists = await self.exists('users', 'wallet = $1', wallet_address)
            if exists:
                raise ConflictError(f"User with wallet {wallet_address} already exists")
        
        if email:
            exists = await self.exists('users', 'email = $1', email)
            if exists:
                raise ConflictError(f"User with email {email} already exists")
        
        if telegram_id:
            exists = await self.exists('users', 'telegram_id = $1', telegram_id)
            if exists:
                raise ConflictError(f"User with telegram_id {telegram_id} already exists")
        
        query = """
            INSERT INTO users (
                wallet, telegram_id, username, email, password_hash, language,
                accumulated_balance, accumulated_units, payout_mode
            )
            VALUES ($1, $2, $3, $4, $5, $6, 0, 0, 'manual')
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            wallet_address,
            telegram_id,
            username,
            email,
            password_hash,
            language
        )
        
        return dict(row)
    
    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
        
        Returns:
            User dictionary or None
        """
        query = "SELECT * FROM users WHERE id = $1"
        return await self.fetch_one(query, user_id)
    
    async def get_by_wallet(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """
        Get user by wallet address.
        
        Args:
            wallet_address: Waves wallet address
        
        Returns:
            User dictionary or None
        """
        query = "SELECT * FROM users WHERE wallet = $1"
        return await self.fetch_one(query, wallet_address)
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email.
        
        Args:
            email: Email address
        
        Returns:
            User dictionary or None
        """
        query = "SELECT * FROM users WHERE email = $1"
        return await self.fetch_one(query, email)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram ID (legacy).
        
        Args:
            telegram_id: Telegram user ID
        
        Returns:
            User dictionary or None
        """
        query = "SELECT * FROM users WHERE telegram_id = $1"
        return await self.fetch_one(query, telegram_id)
    
    async def update_wallet(self, user_id: int, wallet_address: str) -> Dict[str, Any]:
        """
        Update user's wallet address.
        
        Args:
            user_id: User ID
            wallet_address: New wallet address
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
            ConflictError: If wallet already in use
        """
        # Check if wallet is already in use by another user
        existing = await self.fetch_one(
            "SELECT id FROM users WHERE wallet = $1 AND id != $2",
            wallet_address,
            user_id
        )
        if existing:
            raise ConflictError(f"Wallet {wallet_address} is already in use")
        
        query = """
            UPDATE users
            SET wallet = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, wallet_address, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)
    
    async def update_balance(
        self,
        user_id: int,
        balance_delta: float,
        units_delta: int
    ) -> Dict[str, Any]:
        """
        Update user's accumulated balance.
        
        Args:
            user_id: User ID
            balance_delta: Balance change (can be negative for withdrawals)
            units_delta: Units change (smallest token units)
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        query = """
            UPDATE users
            SET
                accumulated_balance = accumulated_balance + $1,
                accumulated_units = accumulated_units + $2,
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, balance_delta, units_delta, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)
    
    async def update_payout_settings(
        self,
        user_id: int,
        payout_mode: str,
        payout_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Update user's payout settings.
        
        Args:
            user_id: User ID
            payout_mode: 'manual' or 'auto'
            payout_threshold: Auto-payout threshold (for auto mode)
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        query = """
            UPDATE users
            SET
                payout_mode = $1,
                payout_threshold = $2,
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, payout_mode, payout_threshold, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)
    
    async def update_language(self, user_id: int, language: str) -> Dict[str, Any]:
        """
        Update user's language preference.
        
        Args:
            user_id: User ID
            language: Language code (en, ru, ar)
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        query = """
            UPDATE users
            SET language = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, language, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)
    
    async def verify_email(self, user_id: int) -> Dict[str, Any]:
        """
        Mark user's email as verified.
        
        Args:
            user_id: User ID
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        query = """
            UPDATE users
            SET email_verified = TRUE, email_verified_at = NOW(), updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)
    
    async def update_widget_preferences(
        self,
        user_id: int,
        widget_preferences: str
    ) -> Dict[str, Any]:
        """
        Update user's widget preferences.
        
        Args:
            user_id: User ID
            widget_preferences: JSON string of widget preferences
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        query = """
            UPDATE users
            SET widget_preferences = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, widget_preferences, user_id)
        if not row:
            raise NotFoundError(f"User {user_id} not found")
        
        return dict(row)

    async def get_users_for_auto_payout(self, threshold: float) -> list:
        """
        Get users eligible for auto-payout.
        
        Args:
            threshold: Minimum balance threshold
        
        Returns:
            List of user dictionaries
        """
        query = """
            SELECT *
            FROM users
            WHERE payout_mode = 'auto'
              AND accumulated_balance >= COALESCE(payout_threshold, $1)
              AND wallet IS NOT NULL
            ORDER BY accumulated_balance DESC
        """
        
        return await self.fetch_all(query, threshold)
