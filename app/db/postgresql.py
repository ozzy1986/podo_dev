"""
PostgreSQL database connection management using asyncpg.
Provides connection pooling with proper lifecycle management.
"""

import logging
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager

import asyncpg

from app.config import DatabaseSettings

logger = logging.getLogger(__name__)


class PostgreSQLDatabase:
    """PostgreSQL connection pool manager."""
    
    def __init__(self, settings: DatabaseSettings):
        """
        Initialize PostgreSQL database manager.
        
        Args:
            settings: Database configuration settings
        """
        self.settings = settings
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is not None:
            logger.warning("PostgreSQL pool already initialized")
            return
        
        try:
            self._pool = await asyncpg.create_pool(
                host=self.settings.host,
                port=self.settings.port,
                database=self.settings.database,
                user=self.settings.user,
                password=self.settings.password,
                min_size=self.settings.pool_min_size,
                max_size=self.settings.pool_max_size,
                timeout=self.settings.pool_timeout,
                command_timeout=60.0,  # Command timeout in seconds
            )
            logger.info(
                f"PostgreSQL pool created: {self.settings.host}:{self.settings.port}/{self.settings.database} "
                f"(pool: {self.settings.pool_min_size}-{self.settings.pool_max_size})"
            )
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}", exc_info=True)
            raise
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is None:
            logger.warning("PostgreSQL pool not initialized")
            return
        
        try:
            await self._pool.close()
            logger.info("PostgreSQL pool closed")
        except Exception as e:
            logger.error(f"Error closing PostgreSQL pool: {e}", exc_info=True)
        finally:
            self._pool = None
    
    @asynccontextmanager
    async def acquire(self) -> AsyncContextManager[asyncpg.Connection]:
        """
        Acquire a connection from the pool.
        
        Usage:
            async with db.acquire() as conn:
                result = await conn.fetch('SELECT * FROM users')
        
        Yields:
            Connection from the pool
        """
        if self._pool is None:
            raise RuntimeError("PostgreSQL pool not initialized. Call connect() first.")
        
        async with self._pool.acquire() as connection:
            yield connection
    
    @asynccontextmanager
    async def transaction(self) -> AsyncContextManager[asyncpg.Connection]:
        """
        Acquire a connection and start a transaction.
        
        Usage:
            async with db.transaction() as conn:
                await conn.execute('INSERT INTO users ...')
                await conn.execute('UPDATE domains ...')
        
        Yields:
            Connection with active transaction
        """
        if self._pool is None:
            raise RuntimeError("PostgreSQL pool not initialized. Call connect() first.")
        
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                yield connection
    
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query and return status.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            Query status string (e.g., 'INSERT 0 1')
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> list:
        """
        Fetch multiple rows.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            List of Record objects
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """
        Fetch a single row.
        
        Args:
            query: SQL query
            *args: Query parameters
        
        Returns:
            Record object or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args, column: int = 0):
        """
        Fetch a single value.
        
        Args:
            query: SQL query
            *args: Query parameters
            column: Column index to return (default: 0)
        
        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column)
    
    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        """Get the connection pool (for advanced usage)."""
        return self._pool


# Global database instance (managed by FastAPI lifespan)
_pg_db: Optional[PostgreSQLDatabase] = None


def get_pg_pool() -> PostgreSQLDatabase:
    """
    Get the global PostgreSQL database instance.
    
    This should be called from FastAPI dependencies after the pool
    has been initialized in the lifespan context manager.
    
    Returns:
        PostgreSQL database instance
    
    Raises:
        RuntimeError: If pool not initialized
    """
    if _pg_db is None:
        raise RuntimeError("PostgreSQL database not initialized")
    return _pg_db


def set_pg_pool(db: PostgreSQLDatabase) -> None:
    """
    Set the global PostgreSQL database instance.
    
    This is called by the FastAPI lifespan context manager.
    
    Args:
        db: PostgreSQL database instance
    """
    global _pg_db
    _pg_db = db
