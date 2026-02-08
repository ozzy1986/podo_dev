"""
ClickHouse database connection management.
Provides async-compatible client wrapper with proper lifecycle management.
All synchronous clickhouse_driver calls are wrapped in asyncio.to_thread().
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date

from clickhouse_driver import Client

from app.config import ClickHouseSettings

logger = logging.getLogger(__name__)


class ClickHouseDatabase:
    """ClickHouse client manager with lifecycle management."""
    
    def __init__(self, settings: ClickHouseSettings):
        """
        Initialize ClickHouse database manager.
        
        Args:
            settings: ClickHouse configuration settings
        """
        self.settings = settings
        self._client: Optional[Client] = None
    
    def connect(self) -> None:
        """Create ClickHouse client connection."""
        if self._client is not None:
            logger.warning("ClickHouse client already initialized")
            return
        
        try:
            config = {
                'host': self.settings.host,
                'port': self.settings.port,
                'database': self.settings.database,
                'user': self.settings.user,
            }
            
            # Only add password if set
            if self.settings.password:
                config['password'] = self.settings.password
            
            self._client = Client(**config)
            
            # Test connection
            self._client.execute('SELECT 1')
            
            logger.info(
                f"ClickHouse client connected: {self.settings.host}:{self.settings.port}/{self.settings.database}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}", exc_info=True)
            raise
    
    def disconnect(self) -> None:
        """Close ClickHouse client connection."""
        if self._client is None:
            logger.warning("ClickHouse client not initialized")
            return
        
        try:
            self._client.disconnect()
            logger.info("ClickHouse client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting ClickHouse client: {e}", exc_info=True)
        finally:
            self._client = None
    
    def execute(self, query: str, params: Optional[Dict] = None) -> List[tuple]:
        """
        Execute a query and return raw results.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            List of tuples (rows)
        """
        if self._client is None:
            raise RuntimeError("ClickHouse client not initialized. Call connect() first.")
        
        return self._client.execute(query, params or {})
    
    def execute_dict(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Execute a query and return results as list of dicts.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            List of dictionaries (rows)
        """
        if self._client is None:
            raise RuntimeError("ClickHouse client not initialized. Call connect() first.")
        
        result = self._client.execute(query, params or {}, with_column_types=True)
        rows, columns_with_types = result
        column_names = [col[0] for col in columns_with_types]
        
        # Convert rows to dicts
        dict_rows = []
        for row in rows:
            dict_row = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                # Convert Decimal to float for JSON serialization
                if isinstance(value, Decimal):
                    value = float(value)
                # Convert date/datetime to ISO format
                elif isinstance(value, (datetime, date)):
                    value = value.isoformat()
                dict_row[col_name] = value
            dict_rows.append(dict_row)
        
        return dict_rows
    
    def insert(self, table: str, data: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> int:
        """
        Insert data into a table.
        
        Args:
            table: Table name
            data: List of dictionaries to insert
            columns: Optional list of column names (if None, uses keys from first dict)
        
        Returns:
            Number of rows inserted
        """
        if self._client is None:
            raise RuntimeError("ClickHouse client not initialized. Call connect() first.")
        
        if not data:
            return 0
        
        # Get columns from first row if not provided
        if columns is None:
            columns = list(data[0].keys())
        
        # Convert dicts to tuples in column order
        rows = [tuple(row.get(col) for col in columns) for row in data]
        
        # Build INSERT query
        columns_str = ', '.join(columns)
        query = f"INSERT INTO {table} ({columns_str}) VALUES"
        
        self._client.execute(query, rows)
        return len(rows)
    
    def fetchval(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        Fetch a single value from a query.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            Single value or None
        """
        result = self.execute(query, params)
        if result and result[0]:
            return result[0][0]
        return None
    
    async def async_execute(self, query: str, params: Optional[Dict] = None) -> List[tuple]:
        """Async wrapper for execute() - runs in thread pool."""
        return await asyncio.to_thread(self.execute, query, params)

    async def async_execute_dict(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Async wrapper for execute_dict() - runs in thread pool."""
        return await asyncio.to_thread(self.execute_dict, query, params)

    async def async_insert(self, table: str, data: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> int:
        """Async wrapper for insert() - runs in thread pool."""
        return await asyncio.to_thread(self.insert, table, data, columns)

    async def async_fetchval(self, query: str, params: Optional[Dict] = None) -> Any:
        """Async wrapper for fetchval() - runs in thread pool."""
        return await asyncio.to_thread(self.fetchval, query, params)

    @property
    def client(self) -> Optional[Client]:
        """Get the ClickHouse client (for advanced usage)."""
        return self._client


# Global database instance (managed by FastAPI lifespan)
_ch_db: Optional[ClickHouseDatabase] = None


def get_ch_client() -> ClickHouseDatabase:
    """
    Get the global ClickHouse database instance.
    
    This should be called from FastAPI dependencies after the client
    has been initialized in the lifespan context manager.
    
    Returns:
        ClickHouse database instance
    
    Raises:
        RuntimeError: If client not initialized
    """
    if _ch_db is None:
        raise RuntimeError("ClickHouse database not initialized")
    return _ch_db


def set_ch_client(db: ClickHouseDatabase) -> None:
    """
    Set the global ClickHouse database instance.
    
    This is called by the FastAPI lifespan context manager.
    
    Args:
        db: ClickHouse database instance
    """
    global _ch_db
    _ch_db = db
