"""
Database repository pattern for clean data access.
Implements DRY principle and provides consistent database operations.

Updated to use PostgreSQL instead of MariaDB.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Try to import PostgreSQL module first, fall back to MariaDB pool
_use_postgresql = True
_pg_connection = None

try:
    from database.postgresql import get_pg, is_pg_available
    _pg = get_pg()
    if is_pg_available():
        _pg_connection = _pg
        logger.info("[REPO] Using PostgreSQL connection")
    else:
        _use_postgresql = False
        logger.error("[REPO] PostgreSQL not available (connection check failed). Ensure .env is readable by the web server user and PG_* vars are set.")
except ImportError as e:
    _use_postgresql = False
    logger.error(f"[REPO] PostgreSQL module not available: {e}")
except Exception as e:
    _use_postgresql = False
    logger.error(f"[REPO] PostgreSQL initialization failed: {e}")

# PostgreSQL is required - no MySQL/MariaDB fallback
if not _use_postgresql:
    error_msg = "PostgreSQL is required but not available. MySQL/MariaDB support has been removed."
    logger.error(f"[REPO] {error_msg}")
    raise ImportError(error_msg)


class BaseRepository:
    """Base repository with common database operations."""
    
    @staticmethod
    @contextmanager
    def get_connection():
        """Get database connection with proper error handling."""
        logger.debug("[REPO] Getting database connection...")
        
        if _use_postgresql and _pg_connection:
            # Use PostgreSQL
            try:
                with _pg_connection.get_cursor(dict_cursor=True) as (cursor, conn):
                    logger.debug("[REPO] ✓ PostgreSQL connection obtained")
                    # Yield the connection object for compatibility
                    # Create a wrapper that provides cursor access
                    yield _PostgreSQLConnectionWrapper(cursor, conn)
            except Exception as e:
                logger.error(f"[REPO] ✗ Failed to get PostgreSQL connection: {e}")
                raise
        else:
            # PostgreSQL is required
            error_msg = "PostgreSQL is required but not available. MySQL/MariaDB support has been removed."
            logger.error(f"[REPO] {error_msg}")
            raise ConnectionError(error_msg)
    
    @staticmethod
    def _run(query: str, params: Tuple = None, *, mode: str = "execute") -> Any:
        """
        Internal helper that runs the query and returns a result based on mode.
        
        Supported modes:
            - "execute": commit and return affected row count (or lastrowid for INSERT)
            - "one": return a single row
            - "all": return all rows
        """
        try:
            logger.debug(f"[REPO] Executing query: {query[:100]}...")
            logger.debug(f"[REPO] Query params: {params}")
            
            if _use_postgresql and _pg_connection:
                # PostgreSQL path
                with _pg_connection.get_cursor(dict_cursor=True) as (cursor, conn):
                    cursor.execute(query, params or ())
                    
                    if mode == "one":
                        result = cursor.fetchone()
                        return dict(result) if result else None
                    if mode == "all":
                        results = cursor.fetchall()
                        return [dict(r) for r in results]
                    
                    # For execute mode
                    conn.commit()
                    
                    # For INSERT with RETURNING, get the returned id
                    if query.strip().upper().startswith("INSERT"):
                        # Check if query has RETURNING clause
                        if "RETURNING" in query.upper():
                            result = cursor.fetchone()
                            if result:
                                # Return the first column (usually id)
                                return list(result.values())[0] if isinstance(result, dict) else result[0]
                        # PostgreSQL doesn't have lastrowid like MySQL
                        # For INSERT without RETURNING, return rowcount
                        return cursor.rowcount
                    
                    return cursor.rowcount
            else:
                # MariaDB path
                with BaseRepository.get_connection() as conn:
                    from database.pool import mysql_connector_available, pymysql_available, _pymysql
                    
                    if mysql_connector_available:
                        cursor = conn.cursor(dictionary=True, buffered=True)
                    elif pymysql_available and _pymysql:
                        cursor = conn.cursor(_pymysql.cursors.DictCursor)
                    else:
                        cursor = conn.cursor()
                    
                    cursor.execute(query, params or ())
                    
                    if mode == "one":
                        result = cursor.fetchone()
                        return result
                    if mode == "all":
                        result = cursor.fetchall()
                        return result
                    
                    conn.commit()
                    
                    if query.strip().upper().startswith("INSERT") and cursor.lastrowid:
                        return cursor.lastrowid
                    
                    return cursor.rowcount
                    
        except Exception as exc:
            logger.error(f"[SQL] Database query FAILED")
            logger.error(f"[SQL] Query: {query}")
            logger.error(f"[SQL] Params: {params}")
            logger.error(f"[SQL] Error: {exc}")
            import traceback
            logger.error(f"[SQL] Traceback: {traceback.format_exc()}")
            raise
    
    @staticmethod
    def execute(query: str, params: Tuple = None) -> int:
        """Execute a mutation query and return affected rows (or ID for INSERT)."""
        # Convert MySQL-style queries to PostgreSQL if needed
        if _use_postgresql:
            query = _convert_mysql_to_postgres(query)
        return BaseRepository._run(query, params, mode="execute")
    
    @staticmethod
    def fetch_one(query: str, params: Tuple = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        if _use_postgresql:
            query = _convert_mysql_to_postgres(query)
        return BaseRepository._run(query, params, mode="one")
    
    @staticmethod
    def fetch_all(query: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        if _use_postgresql:
            query = _convert_mysql_to_postgres(query)
        return BaseRepository._run(query, params, mode="all")


class _PostgreSQLConnectionWrapper:
    """Wrapper to make PostgreSQL connection compatible with MariaDB interface."""
    
    def __init__(self, cursor, conn):
        self._cursor = cursor
        self._conn = conn
    
    def cursor(self, *args, **kwargs):
        """Return the cursor (ignore MySQL-specific arguments)."""
        return self._cursor
    
    def commit(self):
        """Commit the transaction."""
        self._conn.commit()
    
    def rollback(self):
        """Rollback the transaction."""
        self._conn.rollback()


def _convert_mysql_to_postgres(query: str) -> str:
    """
    Convert MySQL-specific syntax to PostgreSQL.
    
    Handles common differences:
    - NOW() works in both
    - DATE() works in both
    - COALESCE() works in both
    - %s placeholders work in both (psycopg2 uses %s)
    """
    # Most queries should work as-is since we use standard SQL
    # Add specific conversions here if needed
    
    # Convert IFNULL to COALESCE (PostgreSQL standard)
    import re
    query = re.sub(r'\bIFNULL\s*\(', 'COALESCE(', query, flags=re.IGNORECASE)
    
    # Convert LIMIT with comma syntax to LIMIT/OFFSET
    # MySQL: LIMIT offset, count -> PostgreSQL: LIMIT count OFFSET offset
    limit_match = re.search(r'\bLIMIT\s+(\d+)\s*,\s*(\d+)', query, flags=re.IGNORECASE)
    if limit_match:
        offset = limit_match.group(1)
        count = limit_match.group(2)
        query = query[:limit_match.start()] + f'LIMIT {count} OFFSET {offset}' + query[limit_match.end():]
    
    return query


def is_using_postgresql() -> bool:
    """Check if repository is using PostgreSQL."""
    return _use_postgresql and _pg_connection is not None
