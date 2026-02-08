"""
Base repository with common database operations.
"""

from typing import Optional, List, Dict, Any
from asyncpg import Pool, Record

from app.db.postgresql import PostgreSQLDatabase


class BaseRepository:
    """Base repository class with common database operations."""
    
    def __init__(self, db: PostgreSQLDatabase):
        """
        Initialize repository.
        
        Args:
            db: PostgreSQL database instance
        """
        self.db = db
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row as dictionary.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            Dictionary or None
        """
        row = await self.db.fetchrow(query, *args)
        return dict(row) if row else None
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Fetch all rows as list of dictionaries.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            List of dictionaries
        """
        rows = await self.db.fetch(query, *args)
        return [dict(row) for row in rows]
    
    async def fetch_val(self, query: str, *args) -> Any:
        """
        Fetch a single value.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            Single value or None
        """
        return await self.db.fetchval(query, *args)
    
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            Query status
        """
        return await self.db.execute(query, *args)
    
    async def exists(self, table: str, condition: str, *args) -> bool:
        """
        Check if a record exists.
        
        Args:
            table: Table name
            condition: WHERE condition
            *args: Condition parameters
        
        Returns:
            True if exists, False otherwise
        """
        query = f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {condition})"
        return await self.fetch_val(query, *args)
    
    async def count(self, table: str, condition: str = "TRUE", *args) -> int:
        """
        Count records.
        
        Args:
            table: Table name
            condition: WHERE condition (default: TRUE)
            *args: Condition parameters
        
        Returns:
            Record count
        """
        query = f"SELECT COUNT(*) FROM {table} WHERE {condition}"
        return await self.fetch_val(query, *args)
