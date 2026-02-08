"""
User service for user-related operations.
"""

from typing import Dict, Any, Optional

from app.repositories.user_repo import UserRepository
from app.repositories.domain_repo import DomainRepository
from app.core.exceptions import NotFoundError, ValidationError


class UserService:
    """Service for user operations."""
    
    def __init__(
        self,
        user_repo: UserRepository,
        domain_repo: DomainRepository
    ):
        """
        Initialize user service.
        
        Args:
            user_repo: User repository
            domain_repo: Domain repository
        """
        self.user_repo = user_repo
        self.domain_repo = domain_repo
    
    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
        
        Returns:
            User dictionary
        
        Raises:
            NotFoundError: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user
    
    async def update_wallet(
        self,
        user_id: int,
        wallet_address: str
    ) -> Dict[str, Any]:
        """
        Update user's wallet address.
        
        Args:
            user_id: User ID
            wallet_address: New wallet address
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
            ValidationError: If wallet address is invalid
            ConflictError: If wallet already in use
        """
        # Validate wallet address (basic check)
        if not wallet_address or not wallet_address.startswith('3'):
            raise ValidationError("Invalid Waves wallet address")
        
        return await self.user_repo.update_wallet(user_id, wallet_address)
    
    async def update_language(
        self,
        user_id: int,
        language: str
    ) -> Dict[str, Any]:
        """
        Update user's language preference.
        
        Args:
            user_id: User ID
            language: Language code (en, ru, ar)
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
            ValidationError: If language is invalid
        """
        # Validate language
        valid_languages = ['en', 'ru', 'ar']
        if language not in valid_languages:
            raise ValidationError(f"Invalid language. Must be one of: {', '.join(valid_languages)}")
        
        return await self.user_repo.update_language(user_id, language)
    
    async def get_balance(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's balance.
        
        Args:
            user_id: User ID
        
        Returns:
            Balance information
        
        Raises:
            NotFoundError: If user not found
        """
        user = await self.get_user(user_id)
        
        return {
            'balance': user.get('accumulated_balance', 0.0),
            'balance_units': user.get('accumulated_units', 0),
            'payout_mode': user.get('payout_mode', 'manual'),
            'payout_threshold': user.get('payout_threshold'),
            'last_payout_at': user.get('last_payout_at')
        }
    
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
            payout_threshold: Auto-payout threshold (required for auto mode)
        
        Returns:
            Updated user dictionary
        
        Raises:
            NotFoundError: If user not found
            ValidationError: If settings are invalid
        """
        # Validate payout mode
        if payout_mode not in ['manual', 'auto']:
            raise ValidationError("Payout mode must be 'manual' or 'auto'")
        
        # Validate threshold for auto mode
        if payout_mode == 'auto':
            if not payout_threshold or payout_threshold < 100:
                raise ValidationError("Auto-payout threshold must be at least 100 tokens")
        
        return await self.user_repo.update_payout_settings(
            user_id,
            payout_mode,
            payout_threshold
        )
    
    async def update_widget_preferences(
        self,
        user_id: int,
        enabled_widgets: list
    ) -> Dict[str, Any]:
        """
        Update user's widget preferences.
        
        Args:
            user_id: User ID
            enabled_widgets: List of enabled widget IDs
        
        Returns:
            Updated widget preferences dict
        
        Raises:
            NotFoundError: If user not found
            ValidationError: If enabled_widgets is not a list
        """
        import json
        
        if not isinstance(enabled_widgets, list):
            raise ValidationError("enabled_widgets must be a list")
        
        # Validate widget IDs are strings
        for widget_id in enabled_widgets:
            if not isinstance(widget_id, str):
                raise ValidationError(f"Widget ID must be a string, got {type(widget_id).__name__}")
        
        prefs_json = json.dumps({"enabled_widgets": enabled_widgets})
        await self.user_repo.update_widget_preferences(user_id, prefs_json)
        
        return {"enabled_widgets": enabled_widgets}

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get user statistics.
        
        Args:
            user_id: User ID
        
        Returns:
            User statistics
        
        Raises:
            NotFoundError: If user not found
        """
        user = await self.get_user(user_id)
        
        # Get domain count
        domain_count = await self.domain_repo.count_user_domains(user_id)
        
        # Get mining domains count
        domains = await self.domain_repo.get_user_domains(user_id)
        mining_count = sum(1 for d in domains if d.get('is_mining'))
        
        return {
            'total_domains': domain_count,
            'mining_domains': mining_count,
            'accumulated_balance': user.get('accumulated_balance', 0.0),
            'wallet': user.get('wallet'),
            'payout_mode': user.get('payout_mode', 'manual'),
            'member_since': user.get('created_at')
        }
