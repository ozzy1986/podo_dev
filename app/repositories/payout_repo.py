"""
Payout repository for database operations.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundError


class PayoutRepository(BaseRepository):
    """Repository for payout operations."""
    
    async def create_request(
        self,
        user_id: int,
        wallet: str,
        amount: float,
        amount_units: int,
        triggered_by: str = 'manual'
    ) -> Dict[str, Any]:
        """
        Create a payout request.
        
        Args:
            user_id: User ID
            wallet: Recipient wallet
            amount: Payout amount (tokens)
            amount_units: Payout amount (smallest units)
            triggered_by: 'manual' or 'auto_threshold'
        
        Returns:
            Created payout request dictionary
        """
        query = """
            INSERT INTO payout_requests (
                user_id, wallet, amount, amount_units, status, triggered_by
            )
            VALUES ($1, $2, $3, $4, 'pending', $5)
            RETURNING *
        """
        
        row = await self.db.fetchrow(
            query,
            user_id,
            wallet,
            amount,
            amount_units,
            triggered_by
        )
        
        return dict(row)
    
    async def get_by_id(self, payout_id: int) -> Optional[Dict[str, Any]]:
        """
        Get payout request by ID.
        
        Args:
            payout_id: Payout request ID
        
        Returns:
            Payout request dictionary or None
        """
        query = "SELECT * FROM payout_requests WHERE id = $1"
        return await self.fetch_one(query, payout_id)
    
    async def get_pending_requests(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get pending payout requests.
        
        Args:
            limit: Maximum number of results
        
        Returns:
            List of payout request dictionaries
        """
        query = """
            SELECT pr.*, u.wallet as user_wallet
            FROM payout_requests pr
            JOIN users u ON pr.user_id = u.id
            WHERE pr.status = 'pending'
            ORDER BY pr.created_at ASC
            LIMIT $1
        """
        
        return await self.fetch_all(query, limit)
    
    async def update_status(
        self,
        payout_id: int,
        status: str,
        tx_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update payout request status.
        
        Args:
            payout_id: Payout request ID
            status: New status ('processing', 'completed', 'failed')
            tx_id: Transaction ID (for completed)
            error_message: Error message (for failed)
        
        Returns:
            Updated payout request dictionary
        
        Raises:
            NotFoundError: If payout request not found
        """
        # Pass status twice to avoid asyncpg type inference (text vs varchar)
        query = """
            UPDATE payout_requests
            SET
                status = $1,
                tx_id = $2,
                error_message = $3,
                processed_at = CASE WHEN $5 IN ('completed', 'failed') THEN NOW() ELSE processed_at END
            WHERE id = $4
            RETURNING *
        """
        
        row = await self.db.fetchrow(query, status, tx_id, error_message, payout_id, status)
        if not row:
            raise NotFoundError(f"Payout request {payout_id} not found")
        
        return dict(row)
    
    async def get_user_payout_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get payout history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of payout request dictionaries
        """
        query = """
            SELECT *
            FROM payout_requests
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        
        return await self.fetch_all(query, user_id, limit, offset)
    
    async def get_total_paid_out(self, user_id: Optional[int] = None) -> float:
        """
        Get total amount paid out.
        
        Args:
            user_id: Optional user ID to filter by
        
        Returns:
            Total paid out amount
        """
        if user_id:
            query = """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM payout_requests
                WHERE user_id = $1 AND status = 'completed'
            """
            return await self.fetch_val(query, user_id)
        else:
            query = """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM payout_requests
                WHERE status = 'completed'
            """
            return await self.fetch_val(query)
