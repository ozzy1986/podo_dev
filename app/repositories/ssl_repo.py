"""
SSL certificate repository for database operations.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundError


class SSLRepository(BaseRepository):
    """Repository for SSL certificate operations."""
    
    async def create(
        self,
        domain: str,
        cert_path: str,
        key_path: str,
        chain_path: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create SSL certificate record.
        
        Args:
            domain: Domain name
            cert_path: Path to certificate file
            key_path: Path to private key file
            chain_path: Path to chain file
            expires_at: Certificate expiry date
        
        Returns:
            Created certificate dictionary
        """
        query = """
            INSERT INTO ssl_certificates (
                domain, cert_path, key_path, chain_path, expires_at, status
            )
            VALUES ($1, $2, $3, $4, $5, 'active')
            ON CONFLICT (domain) DO UPDATE
            SET
                cert_path = EXCLUDED.cert_path,
                key_path = EXCLUDED.key_path,
                chain_path = EXCLUDED.chain_path,
                expires_at = EXCLUDED.expires_at,
                status = 'active',
                updated_at = NOW()
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            domain,
            cert_path,
            key_path,
            chain_path,
            expires_at
        )
        
        return dict(row)
    
    async def get_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get certificate by domain.
        
        Args:
            domain: Domain name
        
        Returns:
            Certificate dictionary or None
        """
        query = "SELECT * FROM ssl_certificates WHERE domain = $1"
        return await self.fetch_one(query, domain)
    
    async def get_active_certificates(self) -> List[Dict[str, Any]]:
        """
        Get all active certificates.
        
        Returns:
            List of certificate dictionaries
        """
        query = """
            SELECT *
            FROM ssl_certificates
            WHERE status = 'active'
            ORDER BY expires_at ASC
        """
        
        return await self.fetch_all(query)
    
    async def get_expiring_soon(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get certificates expiring soon.
        
        Args:
            days: Days until expiry
        
        Returns:
            List of certificate dictionaries
        """
        query = """
            SELECT *
            FROM ssl_certificates
            WHERE status = 'active'
              AND expires_at <= NOW() + INTERVAL '%s days'
            ORDER BY expires_at ASC
        """
        
        return await self.fetch_all(query % days)
    
    async def update_status(
        self,
        domain: str,
        status: str,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update certificate status.
        
        Args:
            domain: Domain name
            status: New status ('active', 'expired', 'failed')
            error_message: Error message (for failed)
        
        Returns:
            Updated certificate dictionary
        
        Raises:
            NotFoundError: If certificate not found
        """
        query = """
            UPDATE ssl_certificates
            SET
                status = $1,
                error_message = $2,
                updated_at = NOW()
            WHERE domain = $3
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, status, error_message, domain)
        if not row:
            raise NotFoundError(f"Certificate for {domain} not found")
        
        return dict(row)
    
    async def delete(self, domain: str) -> bool:
        """
        Delete a certificate record.
        
        Args:
            domain: Domain name
        
        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM ssl_certificates WHERE domain = $1"
        result = await self.execute(query, domain)
        return "DELETE 1" in result
