"""
Domain service for domain management operations.
"""

import secrets
from typing import Dict, Any, List, Optional

from app.repositories.domain_repo import DomainRepository
from app.repositories.user_repo import UserRepository
from app.config import DomainSettings
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionError as AppPermissionError
)


class DomainService:
    """Service for domain operations."""
    
    def __init__(
        self,
        domain_repo: DomainRepository,
        user_repo: UserRepository,
        settings: DomainSettings
    ):
        """
        Initialize domain service.
        
        Args:
            domain_repo: Domain repository
            user_repo: User repository
            settings: Domain settings
        """
        self.domain_repo = domain_repo
        self.user_repo = user_repo
        self.settings = settings
    
    def _validate_domain_name(self, domain: str) -> tuple[str, str, int]:
        """
        Validate and parse domain name.
        
        Args:
            domain: Domain name
        
        Returns:
            Tuple of (sld, tld, sld_length)
        
        Raises:
            ValidationError: If domain is invalid
        """
        domain = domain.lower().strip()
        
        # Basic validation
        if not domain or '.' not in domain:
            raise ValidationError("Invalid domain format")
        
        # Check length
        if len(domain) < self.settings.min_domain_length:
            raise ValidationError(f"Domain too short (min {self.settings.min_domain_length} chars)")
        
        if len(domain) > self.settings.max_domain_length:
            raise ValidationError(f"Domain too long (max {self.settings.max_domain_length} chars)")
        
        # Parse SLD and TLD
        parts = domain.split('.')
        if len(parts) < 2:
            raise ValidationError("Domain must have at least SLD and TLD")
        
        if len(parts) > 2:
            raise ValidationError("Subdomains are not allowed")
        
        sld, tld = parts
        
        # Calculate SLD length (Unicode character count)
        sld_length = len(sld)
        
        if sld_length < 1:
            raise ValidationError("SLD cannot be empty")
        
        return sld, tld, sld_length
    
    async def add_domain(
        self,
        user_id: int,
        domain: str
    ) -> Dict[str, Any]:
        """
        Add a domain for a user.
        
        Args:
            user_id: User ID
            domain: Domain name
        
        Returns:
            Created domain dictionary
        
        Raises:
            NotFoundError: If user not found
            ValidationError: If domain is invalid
            ConflictError: If domain already exists or user has too many domains
        """
        # Check if user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        
        # Check domain limit
        domain_count = await self.domain_repo.count_user_domains(user_id)
        if domain_count >= self.settings.max_domains_per_user:
            raise ConflictError(
                f"Maximum {self.settings.max_domains_per_user} domains per user"
            )
        
        # Validate and parse domain
        sld, tld, sld_length = self._validate_domain_name(domain)
        
        # Generate nonce for verification
        nonce = secrets.token_urlsafe(16)
        
        # Create domain
        return await self.domain_repo.create(
            user_id=user_id,
            domain=domain,
            sld=sld,
            tld=tld,
            sld_length=sld_length,
            nonce=nonce
        )
    
    async def get_domain(self, domain_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get domain by ID.
        
        Args:
            domain_id: Domain ID
            user_id: Optional user ID to check ownership
        
        Returns:
            Domain dictionary
        
        Raises:
            NotFoundError: If domain not found
            PermissionError: If user doesn't own the domain
        """
        domain = await self.domain_repo.get_by_id(domain_id)
        if not domain:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        # Check ownership if user_id provided
        if user_id is not None and domain['user_id'] != user_id:
            raise AppPermissionError("You don't own this domain")
        
        return domain
    
    async def get_user_domains(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get domains owned by user.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of domain dictionaries
        """
        return await self.domain_repo.get_user_domains(user_id, limit, offset)
    
    async def delete_domain(self, domain_id: int, user_id: int) -> bool:
        """
        Delete a domain.
        
        Args:
            domain_id: Domain ID
            user_id: User ID (for ownership check)
        
        Returns:
            True if deleted
        
        Raises:
            NotFoundError: If domain not found
            PermissionError: If user doesn't own the domain
        """
        # Check ownership
        await self.get_domain(domain_id, user_id)
        
        # Delete domain
        return await self.domain_repo.delete(domain_id)
    
    async def update_description(
        self,
        domain_id: int,
        user_id: int,
        description: Optional[str]
    ) -> Dict[str, Any]:
        """
        Update domain description.
        
        Args:
            domain_id: Domain ID
            user_id: User ID (for ownership check)
            description: New description
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
            PermissionError: If user doesn't own the domain
        """
        # Check ownership
        await self.get_domain(domain_id, user_id)
        
        # Update description
        return await self.domain_repo.update_description(domain_id, description)
    
    async def update_parking_content(
        self,
        domain_id: int,
        user_id: int,
        parking_content: Optional[str],
        parking_mode: str = 'redirect'
    ) -> Dict[str, Any]:
        """
        Update domain parking content.
        
        Args:
            domain_id: Domain ID
            user_id: User ID (for ownership check)
            parking_content: HTML content for parking page
            parking_mode: 'redirect' or 'non_redirect'
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
            PermissionError: If user doesn't own the domain
            ValidationError: If parking mode is invalid
        """
        # Check ownership
        await self.get_domain(domain_id, user_id)
        
        # Validate parking mode
        if parking_mode not in ['redirect', 'non_redirect']:
            raise ValidationError("Parking mode must be 'redirect' or 'non_redirect'")
        
        # Update parking content
        return await self.domain_repo.update_parking_content(
            domain_id,
            parking_content,
            parking_mode
        )
    
    async def verify_domain(self, domain_id: int, user_id: int) -> Dict[str, Any]:
        """
        Verify a domain after DNS TXT record check passes.
        Marks domain as verified and enables mining in production.

        Args:
            domain_id: Domain ID
            user_id: User ID (for ownership check)

        Returns:
            Updated domain dictionary
        """
        # Check ownership
        await self.get_domain(domain_id, user_id)

        # Mark as verified
        domain = await self.domain_repo.verify_domain(domain_id)

        # In production, also enable mining automatically
        from app.config import get_settings
        settings = get_settings()
        if settings.is_production:
            domain = await self.domain_repo.start_mining(domain_id)

        return domain

    async def get_verification_txt_record(self, domain_id: int) -> str:
        """
        Get TXT record value for domain verification.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            TXT record value
        
        Raises:
            NotFoundError: If domain not found
        """
        domain = await self.domain_repo.get_by_id(domain_id)
        if not domain:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        # Get user's wallet
        user = await self.user_repo.get_by_id(domain['user_id'])
        if not user or not user.get('wallet'):
            raise ValidationError("User must have a wallet address set")
        
        # Format: d.onl;wallet=3Pxxx...
        return f"d.onl;wallet={user['wallet']}"
