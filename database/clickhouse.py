"""
ClickHouse Database Connection Module for d.onl System (LEGACY).
Handles connections to ClickHouse for analytical/log data (rewards_log).

NOTE: This module is used by the oracle and SSL scripts which run as
separate processes. The FastAPI application uses app/db/clickhouse.py
instead. Do NOT add new features here; extend app/db/clickhouse.py.
"""

import os
import sys
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, date
from decimal import Decimal

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
        logger.info(f"[CH] Loaded environment variables from .env file")
except ImportError:
    logger.info("[CH] python-dotenv not installed, using system environment variables")
except Exception as e:
    logger.warning(f"[CH] Failed to load .env file: {e}")

# Import clickhouse_driver
try:
    from clickhouse_driver import Client
    CLICKHOUSE_AVAILABLE = True
    logger.info("[CH] clickhouse_driver imported successfully")
except ImportError as e:
    CLICKHOUSE_AVAILABLE = False
    logger.warning(f"[CH] clickhouse_driver not available: {e}")
    Client = None


class ClickHouseConnection:
    """ClickHouse connection manager."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            import threading
            self._lock = threading.Lock()  # Thread-safety lock for client operations
            self._init_client()
    
    def _init_client(self):
        """Initialize the ClickHouse client."""
        if not CLICKHOUSE_AVAILABLE:
            logger.error("[CH] Cannot initialize client: clickhouse_driver not available")
            return
        
        try:
            # Get connection parameters from environment
            self._config = {
                'host': os.getenv('CH_HOST', 'localhost'),
                'port': int(os.getenv('CH_PORT', '9000')),
                'database': os.getenv('CH_DATABASE', 'default'),
                'user': os.getenv('CH_USER', 'default'),
                'password': os.getenv('CH_PASSWORD', ''),
            }
            
            # Remove empty password if not set
            if not self._config['password']:
                del self._config['password']
            
            self._client = Client(**self._config)
            
            logger.info(f"[CH] Client initialized: {self._config['host']}:{self._config['port']}/{self._config['database']}")
            
        except Exception as e:
            logger.error(f"[CH] Failed to initialize client: {e}")
            self._client = None
    
    def get_client(self) -> Client:
        """Get the ClickHouse client."""
        if self._client is None:
            self._init_client()
        
        if self._client is None:
            raise Exception("ClickHouse client not available")
        
        return self._client
    
    def execute(self, query: str, params: dict = None) -> List[Tuple]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            List of tuples (rows)
        """
        client = self.get_client()
        with self._lock:  # Thread-safe access to client
            return client.execute(query, params or {})
    
    def execute_with_columns(self, query: str, params: dict = None) -> Tuple[List[Dict], List[str]]:
        """
        Execute a query and return results with column names.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            Tuple of (list of rows as dicts, list of column names)
        """
        client = self.get_client()
        with self._lock:  # Thread-safe access to client
            result = client.execute(query, params or {}, with_column_types=True)
        
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
                dict_row[col_name] = value
            dict_rows.append(dict_row)
        
        return dict_rows, column_names
    
    def execute_dict(self, query: str, params: dict = None) -> List[Dict]:
        """
        Execute a query and return results as list of dicts.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            List of rows as dicts
        """
        rows, _ = self.execute_with_columns(query, params)
        return rows
    
    def execute_one(self, query: str, params: dict = None) -> Optional[Dict]:
        """
        Execute a query and return a single result.
        
        Args:
            query: SQL query string
            params: Query parameters as dict
        
        Returns:
            Single row as dict, or None
        """
        rows = self.execute_dict(query, params)
        return rows[0] if rows else None
    
    def insert_rows(self, table: str, rows: List[Dict], columns: List[str] = None):
        """
        Insert multiple rows into a table.
        
        Args:
            table: Table name
            rows: List of dicts with row data
            columns: Optional list of column names (inferred from first row if not provided)
        """
        if not rows:
            return
        
        if columns is None:
            columns = list(rows[0].keys())
        
        # Convert dicts to tuples
        data = [tuple(row.get(col) for col in columns) for row in rows]
        
        client = self.get_client()
        with self._lock:  # Thread-safe access to client
            client.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES",
                data
            )
    
    def is_available(self) -> bool:
        """Check if ClickHouse connection is available."""
        if not CLICKHOUSE_AVAILABLE:
            return False
        
        try:
            client = self.get_client()
            with self._lock:  # Thread-safe access to client
                client.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"[CH] Connection check failed: {e}")
            return False
    
    # ========================================================================
    # REWARDS LOG SPECIFIC METHODS
    # ========================================================================
    
    def get_user_earnings(self, wallet: str, days: int = None) -> Dict[str, float]:
        """
        Get earnings summary for a user by wallet address.
        
        Args:
            wallet: User's wallet address
            days: Optional number of days to look back (None for all time)
        
        Returns:
            Dict with earnings breakdown
        """
        date_filter = ""
        params = {'wallet': wallet}
        
        if days:
            date_filter = "AND created_at >= now() - INTERVAL %(days)s DAY"
            params['days'] = days
        
        query = f"""
            SELECT 
                sumIf(amount, status IN ('confirmed', 'accumulated')) as total_earned,
                sumIf(amount, status = 'accumulated') as pending,
                sumIf(amount, status = 'confirmed') as confirmed,
                count() as total_transactions
            FROM rewards_log
            WHERE wallet = %(wallet)s {date_filter}
        """
        
        result = self.execute_one(query, params)
        return {
            'total_earned': float(result.get('total_earned') or 0),
            'pending': float(result.get('pending') or 0),
            'confirmed': float(result.get('confirmed') or 0),
            'total_transactions': int(result.get('total_transactions') or 0)
        }
    
    def get_domain_earnings(self, domain_id: int) -> float:
        """
        Get total earnings for a specific domain.
        
        Args:
            domain_id: Domain ID
        
        Returns:
            Total earnings amount
        """
        query = """
            SELECT sum(amount) as total
            FROM rewards_log
            WHERE domain_id = %(domain_id)s
              AND status IN ('confirmed', 'accumulated')
        """
        
        result = self.execute_one(query, {'domain_id': domain_id})
        return float(result.get('total') or 0)
    
    def get_earnings_by_period(self, wallet: str, period: str = 'day') -> List[Dict]:
        """
        Get earnings grouped by time period.
        
        Args:
            wallet: User's wallet address
            period: 'hour', 'day', 'week', 'month'
        
        Returns:
            List of dicts with period and amount
        """
        if period == 'hour':
            date_func = "toStartOfHour(created_at)"
            interval = "INTERVAL 24 HOUR"
        elif period == 'day':
            date_func = "toDate(created_at)"
            interval = "INTERVAL 30 DAY"
        elif period == 'week':
            date_func = "toStartOfWeek(created_at)"
            interval = "INTERVAL 12 WEEK"
        else:  # month
            date_func = "toStartOfMonth(created_at)"
            interval = "INTERVAL 12 MONTH"
        
        query = f"""
            SELECT 
                {date_func} as period,
                sum(amount) as amount,
                count() as count
            FROM rewards_log
            WHERE wallet = %(wallet)s
              AND status IN ('confirmed', 'accumulated')
              AND created_at >= now() - {interval}
            GROUP BY period
            ORDER BY period
        """
        
        return self.execute_dict(query, {'wallet': wallet})
    
    def get_recent_rewards(self, wallet: str = None, domain_id: int = None, limit: int = 50) -> List[Dict]:
        """
        Get recent reward transactions.
        
        Args:
            wallet: Optional wallet filter
            domain_id: Optional domain_id filter
            limit: Max number of results
        
        Returns:
            List of reward records
        """
        conditions = []
        params = {'limit': limit}
        
        if wallet:
            conditions.append("wallet = %(wallet)s")
            params['wallet'] = wallet
        
        if domain_id:
            conditions.append("domain_id = %(domain_id)s")
            params['domain_id'] = domain_id
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, domain_id, amount, amount_units, wallet, txid, status, 
                   error_message, created_at, confirmed_at
            FROM rewards_log
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %(limit)s
        """
        
        return self.execute_dict(query, params)
    
    def create_reward_log(self, domain_id: Optional[int], amount: float, amount_units: int,
                          wallet: str, txid: str = None, status: str = 'pending',
                          row_id: Optional[int] = None) -> bool:
        """
        Create a new reward log entry.

        Args:
            domain_id: Domain ID (None for lottery bonuses)
            amount: Reward amount (with decimals)
            amount_units: Reward amount in smallest units
            wallet: Recipient wallet address
            txid: Transaction ID (optional)
            status: Transaction status
            row_id: Optional pre-allocated id (e.g. from PostgreSQL sequence). If None, uses max(id)+1 from CH (expensive).

        Returns:
            True if successful
        """
        try:
            if row_id is None:
                # Fallback: get next ID from ClickHouse (expensive on large tables - prefer passing id from PG sequence)
                client = self.get_client()
                with self._lock:
                    client.execute("SET max_memory_usage = 8589934592")
                    rows = client.execute(
                        "SELECT id FROM rewards_log ORDER BY id DESC LIMIT 1"
                    )
                next_id = (rows[0][0] + 1) if rows and len(rows) > 0 and len(rows[0]) > 0 else 1
            else:
                next_id = row_id

            self.insert_rows('rewards_log', [{
                'id': next_id,
                'domain_id': domain_id,
                'amount': amount,
                'amount_units': amount_units,
                'wallet': wallet,
                'txid': txid,
                'status': status,
                'error_message': None,
                'created_at': datetime.now(),
                'confirmed_at': None
            }])

            return True
        except Exception as e:
            logger.error(f"[CH] Error creating reward log: {e}")
            return False

    def insert_reward_log_rows(self, rows: List[Dict]) -> None:
        """
        Insert multiple reward log rows in one batch (no ID lookup in ClickHouse).
        Caller must provide id for each row (e.g. from PostgreSQL sequence).

        Args:
            rows: List of dicts with keys id, domain_id, amount, amount_units, wallet, txid, status, error_message, created_at, confirmed_at
        """
        if not rows:
            return
        cols = ['id', 'domain_id', 'amount', 'amount_units', 'wallet', 'txid', 'status', 'error_message', 'created_at', 'confirmed_at']
        data = [tuple(r.get(c) for c in cols) for r in rows]
        client = self.get_client()
        with self._lock:
            client.execute(
                f"INSERT INTO rewards_log ({', '.join(cols)}) VALUES",
                data
            )
    
    def get_system_stats(self) -> Dict:
        """
        Get system-wide reward statistics.
        
        Returns:
            Dict with system stats
        """
        query = """
            SELECT 
                count() as total_transactions,
                countIf(status = 'confirmed') as confirmed_transactions,
                countIf(status = 'accumulated') as accumulated_transactions,
                countIf(status = 'failed') as failed_transactions,
                sum(amount) as total_amount,
                sumIf(amount, status = 'confirmed') as confirmed_amount,
                sumIf(amount, status = 'accumulated') as accumulated_amount,
                uniq(wallet) as unique_wallets,
                uniq(domain_id) as unique_domains
            FROM rewards_log
        """
        
        result = self.execute_one(query)
        if result is None:
            logger.error("[CH] get_system_stats() execute_one() returned None")
            result = {}
        return {
            'total_transactions': int(result.get('total_transactions') or 0),
            'confirmed_transactions': int(result.get('confirmed_transactions') or 0),
            'accumulated_transactions': int(result.get('accumulated_transactions') or 0),
            'failed_transactions': int(result.get('failed_transactions') or 0),
            'total_amount': float(result.get('total_amount') or 0),
            'confirmed_amount': float(result.get('confirmed_amount') or 0),
            'accumulated_amount': float(result.get('accumulated_amount') or 0),
            'unique_wallets': int(result.get('unique_wallets') or 0),
            'unique_domains': int(result.get('unique_domains') or 0)
        }
    
    def get_user_earnings_detailed(self, domain_ids: List[int], wallet: str = None) -> Dict:
        """
        Get detailed earnings for a user's domains (optimized for dashboard).
        
        Optimizations:
        - Uses PREWHERE for domain_id filtering (filters before reading all columns)
        - Filters by date first to leverage partitioning
        - Limits memory usage and thread count via SETTINGS
        - Falls back to simplified query on memory errors
        
        Args:
            domain_ids: List of domain IDs belonging to the user
            wallet: User's wallet for lottery bonuses
        
        Returns:
            Dict with daily/weekly earnings, totals, and per-domain breakdown
        """
        if not domain_ids:
            return {
                'daily_earnings': {},
                'weekly_earnings': {},
                'earnings_by_domain': {},
                'total_confirmed': 0.0,
                'total_pending': 0.0,
                'total_failed': 0.0
            }
        
        # Convert domain_ids to tuple for ClickHouse IN clause
        domain_ids_str = ','.join(str(d) for d in domain_ids)
        
        # Memory and thread limits for queries (2GB per query, 4 threads max)
        query_settings = "SETTINGS max_memory_usage = 2000000000, max_threads = 4"
        
        try:
            # Daily earnings (last 30 days)
            # PREWHERE filters domain_id BEFORE reading all columns (saves memory)
            # WHERE filters by date to leverage partitioning
            daily_query = f"""
                SELECT 
                    toDate(created_at) as reward_date,
                    sum(amount) as total
                FROM rewards_log
                PREWHERE domain_id IN ({domain_ids_str})
                WHERE created_at >= today() - 30
                  AND status IN ('confirmed', 'accumulated')
                GROUP BY reward_date
                ORDER BY reward_date
                {query_settings}
            """
            daily_results = self.execute_dict(daily_query)
            daily_earnings = {}
            for row in daily_results:
                date_key = row['reward_date'].isoformat() if hasattr(row['reward_date'], 'isoformat') else str(row['reward_date'])
                daily_earnings[date_key] = float(row['total'])
            
            # Weekly earnings (last 12 weeks)
            weekly_query = f"""
                SELECT 
                    toStartOfWeek(created_at) as week_start,
                    sum(amount) as total
                FROM rewards_log
                PREWHERE domain_id IN ({domain_ids_str})
                WHERE created_at >= today() - 84
                  AND status IN ('confirmed', 'accumulated')
                GROUP BY week_start
                ORDER BY week_start
                {query_settings}
            """
            weekly_results = self.execute_dict(weekly_query)
            weekly_earnings = {}
            for row in weekly_results:
                date_key = row['week_start'].isoformat() if hasattr(row['week_start'], 'isoformat') else str(row['week_start'])
                weekly_earnings[date_key] = float(row['total'])
            
            # Earnings by domain (top 10)
            domain_query = f"""
                SELECT 
                    domain_id,
                    sum(amount) as total
                FROM rewards_log
                PREWHERE domain_id IN ({domain_ids_str})
                WHERE status IN ('confirmed', 'accumulated')
                GROUP BY domain_id
                ORDER BY total DESC
                LIMIT 10
                {query_settings}
            """
            domain_results = self.execute_dict(domain_query)
            earnings_by_domain_id = {row['domain_id']: float(row['total']) for row in domain_results}
            
            # Totals
            totals_query = f"""
                SELECT 
                    sumIf(amount, status IN ('confirmed', 'accumulated')) as confirmed,
                    sumIf(amount, status = 'pending') as pending,
                    sumIf(amount, status = 'failed') as failed
                FROM rewards_log
                PREWHERE domain_id IN ({domain_ids_str})
                {query_settings}
            """
            totals = self.execute_one(totals_query)
            total_confirmed = float(totals.get('confirmed') or 0)
            total_pending = float(totals.get('pending') or 0)
            total_failed = float(totals.get('failed') or 0)
            
            # Add lottery bonuses if wallet provided
            if wallet:
                lottery_query = f"""
                    SELECT 
                        sumIf(amount, status IN ('confirmed', 'accumulated')) as lc,
                        sumIf(amount, status = 'pending') as lp
                    FROM rewards_log
                    WHERE domain_id IS NULL AND wallet = %(wallet)s
                    {query_settings}
                """
                lottery = self.execute_one(lottery_query, {'wallet': wallet})
                if lottery:
                    total_confirmed += float(lottery.get('lc') or 0)
                    total_pending += float(lottery.get('lp') or 0)
            
            return {
                'daily_earnings': daily_earnings,
                'weekly_earnings': weekly_earnings,
                'earnings_by_domain_id': earnings_by_domain_id,
                'total_confirmed': total_confirmed,
                'total_pending': total_pending,
                'total_failed': total_failed
            }
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a memory error (Code 241)
            if 'Code: 241' in error_msg or 'memory limit exceeded' in error_msg.lower():
                logger.warning(f"[CH] Memory limit exceeded for detailed earnings query. Using simplified fallback. Error: {error_msg}")
                # Fallback: simplified query with only totals (no daily/weekly breakdown)
                try:
                    totals_query_simple = f"""
                        SELECT 
                            sumIf(amount, status IN ('confirmed', 'accumulated')) as confirmed,
                            sumIf(amount, status = 'pending') as pending,
                            sumIf(amount, status = 'failed') as failed
                        FROM rewards_log
                        PREWHERE domain_id IN ({domain_ids_str})
                        SETTINGS max_memory_usage = 1000000000, max_threads = 2
                    """
                    totals = self.execute_one(totals_query_simple)
                    total_confirmed = float(totals.get('confirmed') or 0) if totals else 0.0
                    total_pending = float(totals.get('pending') or 0) if totals else 0.0
                    total_failed = float(totals.get('failed') or 0) if totals else 0.0
                    
                    # Add lottery bonuses if wallet provided
                    if wallet:
                        lottery_query_simple = """
                            SELECT 
                                sumIf(amount, status IN ('confirmed', 'accumulated')) as lc,
                                sumIf(amount, status = 'pending') as lp
                            FROM rewards_log
                            WHERE domain_id IS NULL AND wallet = %(wallet)s
                            SETTINGS max_memory_usage = 1000000000, max_threads = 2
                        """
                        lottery = self.execute_one(lottery_query_simple, {'wallet': wallet})
                        if lottery:
                            total_confirmed += float(lottery.get('lc') or 0)
                            total_pending += float(lottery.get('lp') or 0)
                    
                    logger.info(f"[CH] Fallback query succeeded. Returning totals only: confirmed={total_confirmed}, pending={total_pending}, failed={total_failed}")
                    return {
                        'daily_earnings': {},
                        'weekly_earnings': {},
                        'earnings_by_domain_id': {},
                        'total_confirmed': total_confirmed,
                        'total_pending': total_pending,
                        'total_failed': total_failed
                    }
                except Exception as fallback_error:
                    logger.error(f"[CH] Fallback query also failed: {fallback_error}")
                    # Return empty structure
                    return {
                        'daily_earnings': {},
                        'weekly_earnings': {},
                        'earnings_by_domain_id': {},
                        'total_confirmed': 0.0,
                        'total_pending': 0.0,
                        'total_failed': 0.0
                    }
            else:
                # Other errors - re-raise
                logger.error(f"[CH] Error in get_user_earnings_detailed: {e}", exc_info=True)
                raise


# Singleton instance
_ch_connection = None


def get_ch() -> ClickHouseConnection:
    """Get the ClickHouse connection singleton."""
    global _ch_connection
    if _ch_connection is None:
        _ch_connection = ClickHouseConnection()
    return _ch_connection


def is_ch_available() -> bool:
    """Check if ClickHouse is available."""
    if not CLICKHOUSE_AVAILABLE:
        return False
    try:
        return get_ch().is_available()
    except Exception:
        return False
