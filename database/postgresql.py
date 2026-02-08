"""
PostgreSQL Database Connection Module for d.onl System.
Handles connections to PostgreSQL for transactional data.
"""

import os
import sys
import logging
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Find project root
_current_file = os.path.abspath(__file__)
_current_dir = os.path.dirname(_current_file)
PROJECT_ROOT = os.path.dirname(_current_dir)

# Try to load dotenv
try:
    from dotenv import load_dotenv
    env_file = os.path.join(PROJECT_ROOT, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
        logger.info(f"[PG] Loaded environment variables from .env file")
except ImportError:
    logger.info("[PG] python-dotenv not installed, using system environment variables")
except Exception as e:
    logger.warning(f"[PG] Failed to load .env file: {e}")

# Import psycopg2
try:
    import psycopg2
    from psycopg2 import pool, extras
    PSYCOPG2_AVAILABLE = True
    logger.info("[PG] psycopg2 imported successfully")
except ImportError as e:
    PSYCOPG2_AVAILABLE = False
    logger.warning(f"[PG] psycopg2 not available: {e}")
    psycopg2 = None
    pool = None
    extras = None


class PostgreSQLConnection:
    """PostgreSQL connection manager with connection pooling."""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._init_pool()
    
    def _init_pool(self):
        """Initialize the connection pool."""
        if not PSYCOPG2_AVAILABLE:
            logger.error("[PG] Cannot initialize pool: psycopg2 not available")
            return
        
        try:
            # Get connection parameters from environment (strip to avoid CRLF from .env on Windows)
            def _env(key: str, default: str = '') -> str:
                v = os.getenv(key, default)
                return (v or '').strip().strip('\r')
            self._config = {
                'host': _env('PG_HOST') or _env('DB_HOST') or 'localhost',
                'port': int(_env('PG_PORT') or '5432'),
                'database': _env('PG_DATABASE') or _env('DB_NAME') or 'domain_mining',
                'user': _env('PG_USER') or 'domain_user',
                'password': _env('PG_PASSWORD') or '',
            }
            
            # Create connection pool
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                **self._config
            )
            
            logger.info(f"[PG] Connection pool initialized: {self._config['host']}:{self._config['port']}/{self._config['database']}")
            
        except Exception as e:
            logger.error(f"[PG] Failed to initialize connection pool: {e}", exc_info=True)
            self._pool = None
    
    def get_connection(self):
        """Get a connection from the pool."""
        if self._pool is None:
            self._init_pool()
        
        if self._pool is None:
            raise Exception("PostgreSQL connection pool not available")
        
        return self._pool.getconn()
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self._pool is not None and conn is not None:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """
        Context manager for getting a cursor.
        
        Args:
            dict_cursor: If True, returns a RealDictCursor that returns rows as dicts
        
        Yields:
            Tuple of (cursor, connection)
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            if dict_cursor:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            else:
                cursor = conn.cursor()
            yield cursor, conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[PG] Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)
    
    def execute(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            List of rows as dicts for SELECT, None for other queries
        """
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, params)
            
            # Check if this is a SELECT query
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            else:
                conn.commit()
                return None
    
    def execute_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """
        Execute a query and return a single result.
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            Single row as dict, or None
        """
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, params)
            
            if cursor.description:
                row = cursor.fetchone()
                return dict(row) if row else None
            else:
                conn.commit()
                return None
    
    def insert(self, table: str, data: Dict[str, Any], returning: str = 'id') -> Optional[Any]:
        """
        Insert a row and return the specified column value.
        
        Args:
            table: Table name
            data: Dict of column -> value
            returning: Column to return (default 'id')
        
        Returns:
            Value of the returning column
        """
        columns = list(data.keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders}) RETURNING {returning}"
        
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, tuple(data.values()))
            result = cursor.fetchone()
            conn.commit()
            return result[returning] if result else None
    
    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple) -> int:
        """
        Update rows in a table.
        
        Args:
            table: Table name
            data: Dict of column -> value to update
            where: WHERE clause (without 'WHERE')
            where_params: Parameters for WHERE clause
        
        Returns:
            Number of rows affected
        """
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, tuple(data.values()) + where_params)
            conn.commit()
            return cursor.rowcount
    
    def delete(self, table: str, where: str, where_params: tuple) -> int:
        """
        Delete rows from a table.
        
        Args:
            table: Table name
            where: WHERE clause (without 'WHERE')
            where_params: Parameters for WHERE clause
        
        Returns:
            Number of rows affected
        """
        query = f"DELETE FROM {table} WHERE {where}"
        
        with self.get_cursor() as (cursor, conn):
            cursor.execute(query, where_params)
            conn.commit()
            return cursor.rowcount
    
    def close(self):
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.info("[PG] Connection pool closed")
    
    def is_available(self) -> bool:
        """Check if PostgreSQL connection is available."""
        if not PSYCOPG2_AVAILABLE:
            return False
        
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.warning(f"[PG] Connection check failed: {e}")
            return False


# Singleton instance
_pg_connection = None


def get_pg() -> PostgreSQLConnection:
    """Get the PostgreSQL connection singleton."""
    global _pg_connection
    if _pg_connection is None:
        _pg_connection = PostgreSQLConnection()
    return _pg_connection


def is_pg_available() -> bool:
    """Check if PostgreSQL is available."""
    if not PSYCOPG2_AVAILABLE:
        return False
    try:
        return get_pg().is_available()
    except Exception:
        return False
