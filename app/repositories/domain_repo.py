"""
Domain repository for database operations.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundError, ConflictError


class DomainRepository(BaseRepository):
    """Repository for domain operations."""
    
    async def create(
        self,
        user_id: int,
        domain: str,
        sld: str,
        tld: str,
        sld_length: int,
        nonce: str
    ) -> Dict[str, Any]:
        """
        Create a new domain.
        
        Args:
            user_id: Owner user ID
            domain: Full domain name
            sld: Second-level domain
            tld: Top-level domain
            sld_length: Length of SLD
            nonce: Verification nonce
        
        Returns:
            Created domain dictionary
        
        Raises:
            ConflictError: If domain already exists
        """
        # Check if domain already exists
        exists = await self.exists('domains', 'domain = $1', domain)
        if exists:
            raise ConflictError(f"Domain {domain} already exists")
        
        # Schema has user_id, domain, sld_length, nonce (sld/tld not stored)
        query = """
            INSERT INTO domains (
                user_id, domain, sld_length, nonce,
                verified, is_mining, failed_checks, age_r
            )
            VALUES ($1, $2, $3, $4, FALSE, FALSE, 0, 1.0)
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            user_id,
            domain,
            sld_length,
            nonce
        )
        
        return dict(row)
    
    async def get_by_id(self, domain_id: int) -> Optional[Dict[str, Any]]:
        """
        Get domain by ID.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            Domain dictionary or None
        """
        query = "SELECT * FROM domains WHERE id = $1"
        return await self.fetch_one(query, domain_id)
    
    async def get_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get domain by name.
        
        Args:
            domain: Domain name
        
        Returns:
            Domain dictionary or None
        """
        query = "SELECT * FROM domains WHERE domain = $1"
        return await self.fetch_one(query, domain)
    
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
        query = """
            SELECT *
            FROM domains
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        
        return await self.fetch_all(query, user_id, limit, offset)
    
    async def count_user_domains(self, user_id: int) -> int:
        """
        Count domains owned by user.
        
        Args:
            user_id: User ID
        
        Returns:
            Domain count
        """
        return await self.count('domains', 'user_id = $1', user_id)
    
    async def verify_domain(self, domain_id: int) -> Dict[str, Any]:
        """
        Mark domain as verified.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                verified = TRUE,
                verification_time = NOW(),
                last_check = NOW(),
                failed_checks = 0,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def start_mining(self, domain_id: int) -> Dict[str, Any]:
        """
        Start mining for domain.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                is_mining = TRUE,
                failed_checks = 0,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def stop_mining(self, domain_id: int, reason: str = 'manual') -> Dict[str, Any]:
        """
        Stop mining for domain.
        
        Args:
            domain_id: Domain ID
            reason: Reason for stopping
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                is_mining = FALSE,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def update_check_status(
        self,
        domain_id: int,
        verified: bool,
        failed_checks: int = 0
    ) -> Dict[str, Any]:
        """
        Update domain check status.
        
        Args:
            domain_id: Domain ID
            verified: Whether domain is verified
            failed_checks: Number of failed checks
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                verified = $1,
                failed_checks = $2,
                last_check = NOW(),
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, verified, failed_checks, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def update_a_record_status(
        self,
        domain_id: int,
        points_to_us: bool
    ) -> Dict[str, Any]:
        """
        Update A-record verification status.
        
        Args:
            domain_id: Domain ID
            points_to_us: Whether A-record points to our server
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                a_record_points_to_us = $1,
                updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, points_to_us, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def update_description(
        self,
        domain_id: int,
        description: Optional[str]
    ) -> Dict[str, Any]:
        """
        Update domain description.
        
        Args:
            domain_id: Domain ID
            description: Domain description
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET description = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, description, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def update_parking_content(
        self,
        domain_id: int,
        parking_content: Optional[str],
        parking_mode: str = 'redirect'
    ) -> Dict[str, Any]:
        """
        Update domain parking content and mode.
        
        Args:
            domain_id: Domain ID
            parking_content: HTML content for parking page
            parking_mode: 'redirect' or 'non_redirect'
        
        Returns:
            Updated domain dictionary
        
        Raises:
            NotFoundError: If domain not found
        """
        query = """
            UPDATE domains
            SET
                parking_content = $1,
                parking_mode = $2,
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, parking_content, parking_mode, domain_id)
        if not row:
            raise NotFoundError(f"Domain {domain_id} not found")
        
        return dict(row)
    
    async def delete(self, domain_id: int) -> bool:
        """
        Delete a domain.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM domains WHERE id = $1"
        result = await self.execute(query, domain_id)
        return "DELETE 1" in result
    
    async def get_mining_domains(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all domains currently mining.
        
        Args:
            limit: Optional limit on results
        
        Returns:
            List of domain dictionaries
        """
        query = """
            SELECT d.*, u.wallet
            FROM domains d
            JOIN users u ON d.user_id = u.id
            WHERE d.is_mining = TRUE
            ORDER BY d.last_check ASC NULLS FIRST
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return await self.fetch_all(query)
    
    async def get_domains_needing_check(
        self,
        hours_since_check: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get domains that need verification check.
        
        Args:
            hours_since_check: Hours since last check
        
        Returns:
            List of domain dictionaries
        """
        query = """
            SELECT d.*, u.wallet
            FROM domains d
            JOIN users u ON d.user_id = u.id
            WHERE d.is_mining = TRUE
              AND (
                  d.last_check IS NULL
                  OR d.last_check < NOW() - INTERVAL '%s hours'
              )
            ORDER BY d.last_check ASC NULLS FIRST
        """
        
        return await self.fetch_all(query % hours_since_check)
