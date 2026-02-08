"""
PostgreSQL Database Wrapper for d.onl System.
Provides the same interface as the original Database class but uses PostgreSQL.
"""

import os
import re
import sys
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
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
except ImportError:
    pass
except Exception:
    pass

# Import PostgreSQL module
try:
    from database.postgresql import get_pg, is_pg_available, PostgreSQLConnection
    PG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[DB_PG] PostgreSQL module not available: {e}")
    PG_AVAILABLE = False

# Import ClickHouse module for rewards_log queries
try:
    from database.clickhouse import get_ch, is_ch_available
    CH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"[DB_PG] ClickHouse module not available: {e}")
    CH_AVAILABLE = False


class DatabasePG:
    """PostgreSQL Database wrapper with same interface as original Database class."""
    
    def __init__(self):
        """Initialize PostgreSQL connection."""
        self._pg = None
        self._ch = None
        self._init_connections()
    
    def _init_connections(self):
        """Initialize database connections."""
        if PG_AVAILABLE:
            try:
                self._pg = get_pg()
                if self._pg.is_available():
                    logger.info("[DB_PG] PostgreSQL connection initialized")
                else:
                    logger.warning("[DB_PG] PostgreSQL not available")
                    self._pg = None
            except Exception as e:
                logger.error(f"[DB_PG] Failed to initialize PostgreSQL: {e}")
                self._pg = None
        
        if CH_AVAILABLE:
            try:
                self._ch = get_ch()
                if self._ch.is_available():
                    logger.info("[DB_PG] ClickHouse connection initialized")
                else:
                    logger.warning("[DB_PG] ClickHouse not available")
                    self._ch = None
            except Exception as e:
                logger.error(f"[DB_PG] Failed to initialize ClickHouse: {e}")
                self._ch = None
    
    def is_available(self) -> bool:
        """Check if PostgreSQL is available."""
        return self._pg is not None and self._pg.is_available()
    
    @contextmanager
    def get_cursor(self, dictionary=True, buffered=True):
        """Context manager for database cursor - compatible with original interface."""
        if not self._pg:
            raise Exception("PostgreSQL not available")
        
        with self._pg.get_cursor(dict_cursor=dictionary) as (cursor, conn):
            yield cursor, conn

    @staticmethod
    def _slugify(name: str) -> str:
        """Normalize name to slug: lowercase, alphanumeric and hyphens only."""
        if not name or not isinstance(name, str):
            return "unknown"
        s = name.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s or "unknown"

    def _get_or_create_registrar(self, cursor, conn, name: str) -> Optional[int]:
        """Get or create registrar by name; return registrar id or None."""
        if not name or not name.strip():
            return None
        slug = self._slugify(name)
        cursor.execute("SELECT id FROM registrars WHERE slug = %s", (slug,))
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO registrars (name, slug) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING RETURNING id",
            (name.strip()[:255], slug)
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute("SELECT id FROM registrars WHERE slug = %s", (slug,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def _get_or_create_hoster(self, cursor, conn, name: str) -> Optional[int]:
        """Get or create hoster by name (from NS hostname); return hoster id or None."""
        if not name or not name.strip():
            return None
        slug = self._slugify(name)
        cursor.execute("SELECT id FROM hosters WHERE slug = %s", (slug,))
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO hosters (name, slug) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING RETURNING id",
            (name.strip()[:255], slug)
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute("SELECT id FROM hosters WHERE slug = %s", (slug,))
        row = cursor.fetchone()
        return row["id"] if row else None

    # ========================================================================
    # USER OPERATIONS
    # ========================================================================
    
    def create_user(self, telegram_id: Optional[int] = None, username: Optional[str] = None,
                   password_hash: Optional[str] = None, email: Optional[str] = None) -> Optional[int]:
        """Create a new user or return existing user ID."""
        try:
            with self.get_cursor() as (cursor, conn):
                if telegram_id:
                    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                    result = cursor.fetchone()
                    if result:
                        return result['id']
                
                if username:
                    cursor.execute("SELECT id FROM users WHERE username = %s AND telegram_id IS NULL", (username,))
                    result = cursor.fetchone()
                    if result:
                        return None
                
                if email:
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    result = cursor.fetchone()
                    if result:
                        return None
                
                cursor.execute(
                    "INSERT INTO users (telegram_id, username, password_hash, email) VALUES (%s, %s, %s, %s) RETURNING id",
                    (telegram_id, username, password_hash, email)
                )
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by user ID."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by Telegram ID."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM users WHERE username = %s AND telegram_id IS NULL", (username,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        try:
            email_normalized = email.strip().lower() if email else None
            if not email_normalized:
                return None
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM users WHERE LOWER(TRIM(email)) = %s", (email_normalized,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    def get_user_by_wallet(self, wallet: str) -> Optional[Dict[str, Any]]:
        """Get user by Waves wallet address."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM users WHERE wallet = %s", (wallet.strip(),))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user by wallet: {e}")
            return None
    
    def update_user_wallet(self, telegram_id: int, wallet: str) -> bool:
        """Update user's Waves wallet address."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE users SET wallet = %s WHERE telegram_id = %s",
                    (wallet, telegram_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating wallet: {e}")
            return False
    
    def update_user_wallet_by_id(self, user_id: int, wallet: str) -> bool:
        """Update user's Waves wallet address by user ID."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE users SET wallet = %s WHERE id = %s",
                    (wallet, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating wallet by ID: {e}")
            return False
    
    # ========================================================================
    # DOMAIN OPERATIONS
    # ========================================================================
    
    def add_domain(self, user_id: int, domain: str, nonce: str) -> Optional[int]:
        """Add a new domain for a user."""
        try:
            sld_length = None
            try:
                from tokenomics.weights import get_sld_length
                sld_length = get_sld_length(domain)
            except Exception as e:
                logger.warning(f"Failed to calculate sld_length for {domain}: {e}")
            
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT id FROM domains WHERE domain = %s", (domain,))
                if cursor.fetchone():
                    logger.warning(f"Domain {domain} already exists")
                    return None
                
                if sld_length is not None:
                    cursor.execute(
                        """INSERT INTO domains (user_id, domain, nonce, verified, is_mining, failed_checks, sld_length)
                           VALUES (%s, %s, %s, FALSE, FALSE, 0, %s) RETURNING id""",
                        (user_id, domain, nonce, sld_length)
                    )
                else:
                    cursor.execute(
                        """INSERT INTO domains (user_id, domain, nonce, verified, is_mining, failed_checks)
                           VALUES (%s, %s, %s, FALSE, FALSE, 0) RETURNING id""",
                        (user_id, domain, nonce)
                    )
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
                
        except Exception as e:
            logger.error(f"Error adding domain: {e}")
            return None
    
    def get_domain_by_name(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get domain by name."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM domains WHERE domain = %s", (domain,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting domain: {e}")
            return None
    
    def get_domain_by_id(self, domain_id: int) -> Optional[Dict[str, Any]]:
        """Get domain by ID."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT * FROM domains WHERE id = %s", (domain_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting domain by ID: {e}")
            return None
    
    def get_user_domains(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all domains for a user."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "SELECT * FROM domains WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                results = cursor.fetchall()
                return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error getting user domains: {e}")
            return []
    
    def get_mining_domains(self) -> List[Dict[str, Any]]:
        """Get all domains that are currently mining."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT d.*, u.wallet 
                    FROM domains d 
                    JOIN users u ON d.user_id = u.id 
                    WHERE d.is_mining = TRUE AND d.verified = TRUE
                """)
                results = cursor.fetchall()
                return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error getting mining domains: {e}")
            return []
    
    def verify_domain(self, domain_id: int, domain_expires_at: Optional[datetime] = None) -> bool:
        """
        Mark domain as verified and start mining.
        Calculates and sets age_r factor based on domain age.
        Note: sld_length should already be set when domain was added.
        
        Args:
            domain_id: Domain ID
            domain_expires_at: Domain expiry date from WHOIS
        
        Returns:
            True if successful
        """
        try:
            # Get domain data to calculate age_r
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT domain, creation_date, verification_time, sld_length FROM domains WHERE id = %s", (domain_id,))
                domain_data = cursor.fetchone()
                
                if not domain_data:
                    logger.error(f"Domain {domain_id} not found")
                    return False
                
                domain_name = domain_data['domain']
                creation_date = domain_data.get('creation_date')
                verification_time = domain_data.get('verification_time')
                sld_length = domain_data.get('sld_length')
                
                # Warn if sld_length is missing (should have been set when domain was added)
                if sld_length is None:
                    logger.warning(f"Domain {domain_name} (ID: {domain_id}) is missing sld_length. It should have been set when domain was added.")
                    # Try to calculate it now as fallback
                    try:
                        from tokenomics.weights import get_sld_length
                        sld_length = get_sld_length(domain_name)
                        logger.info(f"Calculated sld_length={sld_length} for domain {domain_name} (fallback)")
                    except Exception as e:
                        logger.error(f"Failed to calculate sld_length for {domain_name}: {e}")
                
                # Fetch creation date, registrar and NS from WHOIS
                domain_creation_date = creation_date
                registrar_id = None
                hoster_id = None
                try:
                    from oracle.whois_service import get_domain_whois_extra, get_domain_creation_date
                    extra_date, registrar_name, name_servers = get_domain_whois_extra(domain_name)
                    if not domain_creation_date and extra_date:
                        domain_creation_date = extra_date
                        logger.info(f"Fetched creation date for {domain_name}: {domain_creation_date.date()}")
                    elif not domain_creation_date:
                        domain_creation_date = get_domain_creation_date(domain_name)
                        if domain_creation_date:
                            logger.info(f"Fetched creation date for {domain_name}: {domain_creation_date.date()}")
                    try:
                        if registrar_name:
                            registrar_id = self._get_or_create_registrar(cursor, conn, registrar_name)
                        if name_servers:
                            from oracle.whois_service import _normalize_hoster_from_ns
                            hoster_name = _normalize_hoster_from_ns(name_servers[0])
                            if hoster_name:
                                hoster_id = self._get_or_create_hoster(cursor, conn, hoster_name)
                    except Exception as reg_host_err:
                        logger.debug(f"Registrar/hoster resolution skipped for {domain_name}: {reg_host_err}")
                except Exception as e:
                    logger.warning(f"Error fetching WHOIS extra for {domain_name}: {e}", exc_info=True)
                    if not domain_creation_date:
                        try:
                            from oracle.whois_service import get_domain_creation_date
                            domain_creation_date = get_domain_creation_date(domain_name)
                        except Exception:
                            pass
                
                # Calculate age_r factor
                age_r = 1.0  # Default value
                try:
                    from tokenomics.weights import calculate_age_factor
                    from oracle.whois_service import get_domain_age_years
                    
                    age_years = get_domain_age_years(domain_name, fallback_to_zero=True)
                    
                    # Fallback to verification time if WHOIS fails
                    if age_years == 0.0 and verification_time:
                        if isinstance(verification_time, datetime):
                            delta = datetime.now() - verification_time
                            age_years = delta.total_seconds() / (365.25 * 24 * 3600)
                        elif isinstance(verification_time, str):
                            # Parse string datetime
                            try:
                                vtime = datetime.fromisoformat(str(verification_time).replace('Z', '+00:00'))
                                delta = datetime.now() - vtime
                                age_years = delta.total_seconds() / (365.25 * 24 * 3600)
                            except:
                                pass
                    
                    age_r = calculate_age_factor(age_years)
                    logger.info(f"Calculated age_r={age_r:.6f} (age={age_years:.2f} years) for domain {domain_name}")
                    
                except Exception as e:
                    logger.error(f"Error calculating age_r for domain {domain_name}: {e}", exc_info=True)
                    # Use default age_r (1.0) as fallback
                    age_r = 1.0
                    logger.warning(f"Using default age_r=1.0 for domain {domain_name}")
                
                # Calculate weight if we have both sld_length and age_r
                # age_r should always have a value (default 1.0), so we only need to check sld_length
                weight = None
                if sld_length is not None:
                    try:
                        from tokenomics.constants import W_LEN, B_FACTOR
                        if 1 <= sld_length <= 63:
                            w_len = W_LEN[sld_length]
                            w_age = 1.0 + B_FACTOR * (1.0 - age_r)
                            weight = w_len * w_age
                            logger.info(f"Calculated weight={weight:.2f} for domain {domain_name} (sld_length={sld_length}, age_r={age_r:.6f})")
                        else:
                            weight = 1.0
                            logger.warning(f"Invalid sld_length={sld_length} for domain {domain_name}, using default weight=1.0")
                    except Exception as e:
                        logger.error(f"Error calculating weight for domain {domain_name}: {e}", exc_info=True)
                        weight = 1.0  # Fallback to default weight
                
                # Update domain with verification status and calculated values
                # Include creation_date if we fetched it
                # We always have age_r (default 1.0), so we check sld_length
                extra_params = (registrar_id, hoster_id)
                if sld_length is not None:
                    if weight is not None:
                        if domain_creation_date:
                            cursor.execute(
                                """UPDATE domains 
                                   SET verified = TRUE, 
                                       is_mining = TRUE, 
                                       verification_time = CURRENT_TIMESTAMP,
                                       last_check = CURRENT_TIMESTAMP,
                                       last_reward = CURRENT_TIMESTAMP,
                                       failed_checks = 0,
                                       domain_expires_at = %s,
                                       whois_last_check = CURRENT_DATE,
                                       creation_date = %s,
                                       sld_length = %s,
                                       age_r = %s,
                                       weight = %s,
                                       registrar_id = %s,
                                       hoster_id = %s
                                   WHERE id = %s""",
                                (domain_expires_at, domain_creation_date, sld_length, age_r, weight) + extra_params + (domain_id,)
                            )
                        else:
                            cursor.execute(
                                """UPDATE domains 
                                   SET verified = TRUE, 
                                       is_mining = TRUE, 
                                       verification_time = CURRENT_TIMESTAMP,
                                       last_check = CURRENT_TIMESTAMP,
                                       last_reward = CURRENT_TIMESTAMP,
                                       failed_checks = 0,
                                       domain_expires_at = %s,
                                       whois_last_check = CURRENT_DATE,
                                       sld_length = %s,
                                       age_r = %s,
                                       weight = %s,
                                       registrar_id = %s,
                                       hoster_id = %s
                                   WHERE id = %s""",
                                (domain_expires_at, sld_length, age_r, weight) + extra_params + (domain_id,)
                            )
                    else:
                        # Weight calculation failed, but we still have sld_length and age_r
                        if domain_creation_date:
                            cursor.execute(
                                """UPDATE domains 
                                   SET verified = TRUE, 
                                       is_mining = TRUE, 
                                       verification_time = CURRENT_TIMESTAMP,
                                       last_check = CURRENT_TIMESTAMP,
                                       last_reward = CURRENT_TIMESTAMP,
                                       failed_checks = 0,
                                       domain_expires_at = %s,
                                       whois_last_check = CURRENT_DATE,
                                       creation_date = %s,
                                       sld_length = %s,
                                       age_r = %s,
                                       registrar_id = %s,
                                       hoster_id = %s
                                   WHERE id = %s""",
                                (domain_expires_at, domain_creation_date, sld_length, age_r) + extra_params + (domain_id,)
                            )
                        else:
                            cursor.execute(
                                """UPDATE domains 
                                   SET verified = TRUE, 
                                       is_mining = TRUE, 
                                       verification_time = CURRENT_TIMESTAMP,
                                       last_check = CURRENT_TIMESTAMP,
                                       last_reward = CURRENT_TIMESTAMP,
                                       failed_checks = 0,
                                       domain_expires_at = %s,
                                       whois_last_check = CURRENT_DATE,
                                       sld_length = %s,
                                       age_r = %s,
                                       registrar_id = %s,
                                       hoster_id = %s
                                   WHERE id = %s""",
                                (domain_expires_at, sld_length, age_r) + extra_params + (domain_id,)
                            )
                else:
                    # Missing sld_length - do basic update but still set age_r and creation_date if available
                    if domain_creation_date:
                        cursor.execute(
                            """UPDATE domains 
                               SET verified = TRUE, 
                                   is_mining = TRUE, 
                                   verification_time = CURRENT_TIMESTAMP,
                                   last_check = CURRENT_TIMESTAMP,
                                   last_reward = CURRENT_TIMESTAMP,
                                   failed_checks = 0,
                                   domain_expires_at = %s,
                                   whois_last_check = CURRENT_DATE,
                                   creation_date = %s,
                                   age_r = %s,
                                   registrar_id = %s,
                                   hoster_id = %s
                               WHERE id = %s""",
                            (domain_expires_at, domain_creation_date, age_r) + extra_params + (domain_id,)
                        )
                    else:
                        cursor.execute(
                            """UPDATE domains 
                               SET verified = TRUE, 
                                   is_mining = TRUE, 
                                   verification_time = CURRENT_TIMESTAMP,
                                   last_check = CURRENT_TIMESTAMP,
                                   last_reward = CURRENT_TIMESTAMP,
                                   failed_checks = 0,
                                   domain_expires_at = %s,
                                   whois_last_check = CURRENT_DATE,
                                   age_r = %s,
                                   registrar_id = %s,
                                   hoster_id = %s
                               WHERE id = %s""",
                            (domain_expires_at, age_r) + extra_params + (domain_id,)
                        )
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error verifying domain: {e}", exc_info=True)
            return False
    
    def remove_domain(self, user_id: int, domain: str) -> bool:
        """Remove a domain."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "DELETE FROM domains WHERE user_id = %s AND domain = %s",
                    (user_id, domain)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing domain: {e}")
            return False
    
    def update_domain_clickable(self, domain_id: int, is_clickable: bool, user_id: int = None) -> bool:
        """Update domain clickable status."""
        try:
            with self.get_cursor() as (cursor, conn):
                if user_id:
                    cursor.execute(
                        "UPDATE domains SET is_clickable = %s WHERE id = %s AND user_id = %s",
                        (is_clickable, domain_id, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE domains SET is_clickable = %s WHERE id = %s",
                        (is_clickable, domain_id)
                    )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating domain clickable: {e}")
            return False
    
    def update_a_record_status(self, domain_id: int, points_to_us: bool) -> bool:
        """Update A-record status for a domain.
        
        Args:
            domain_id: Domain ID
            points_to_us: True if A-record points to our server IP, False otherwise
            
        Returns:
            True if successful
        """
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE domains SET a_record_points_to_us = %s WHERE id = %s",
                    (points_to_us, domain_id)
                )
                conn.commit()
                logger.debug(f"Updated A-record status for domain {domain_id}: points_to_us={points_to_us}")
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating A-record status for domain {domain_id}: {e}")
            return False
    
    def update_domain_description(self, domain: str, description: Optional[str], user_id: int, content_theme: Optional[str] = None) -> bool:
        """Update domain description.
        
        Args:
            domain: Domain name
            description: Description text (max 500 characters, can be None or empty to clear)
            user_id: User ID (for ownership verification)
            content_theme: Theme (light/dark) author had when editing; used for display isolation.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate description length
            if description and len(description) > 500:
                logger.warning(f"Description too long for domain {domain}: {len(description)} characters")
                return False
            
            # Normalize: None or empty string becomes NULL in database
            description_value = description.strip() if description and description.strip() else None
            
            content_theme_val = (content_theme or 'light').strip().lower() if content_theme else 'light'
            if content_theme_val not in ('light', 'dark'):
                content_theme_val = 'light'
            with self.get_cursor() as (cursor, conn):
                # Update description and content_theme (theme author had when editing)
                cursor.execute(
                    """UPDATE domains 
                       SET description = %s, content_theme = %s, updated_at = CURRENT_TIMESTAMP 
                       WHERE domain = %s AND user_id = %s""",
                    (description_value, content_theme_val, domain.lower(), user_id)
                )
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Updated description for domain {domain} (user_id={user_id})")
                    return True
                else:
                    logger.warning(f"Domain {domain} not found or not owned by user {user_id}")
                    return False
        except Exception as e:
            logger.error(f"Error updating domain description for {domain}: {e}")
            return False
    
    def update_domain_parking_mode(self, domain: str, parking_mode: str, user_id: int) -> bool:
        """Update domain parking mode (redirect | non_redirect).
        
        Super parking (non_redirect) requires A-record to point to our IP.
        Args:
            domain: Domain name
            parking_mode: 'redirect' or 'non_redirect'
            user_id: User ID (ownership verification)
        Returns:
            True if successful
        """
        if parking_mode not in ('redirect', 'non_redirect'):
            logger.warning(f"Invalid parking_mode: {parking_mode}")
            return False
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """UPDATE domains 
                       SET parking_mode = %s, updated_at = CURRENT_TIMESTAMP 
                       WHERE domain = %s AND user_id = %s""",
                    (parking_mode, domain.lower(), user_id)
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Updated parking_mode to {parking_mode} for domain {domain}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating parking_mode for {domain}: {e}")
            return False

    def update_domain_parking_content(self, domain: str, parking_content: Optional[str], user_id: int, content_theme: Optional[str] = None) -> bool:
        """Update domain parking content (HTML for super parking landing page).
        
        Args:
            domain: Domain name
            parking_content: HTML content, max 20000 chars. None or empty to clear.
            user_id: User ID (ownership verification)
            content_theme: Theme (light/dark) author had when editing; used for display isolation.
        Returns:
            True if successful
        """
        try:
            if parking_content and len(parking_content) > 20000:
                logger.warning(f"Parking content too long for {domain}: {len(parking_content)} chars")
                return False
            content_value = parking_content.strip() if parking_content and parking_content.strip() else None
            content_theme_val = (content_theme or 'light').strip().lower() if content_theme else 'light'
            if content_theme_val not in ('light', 'dark'):
                content_theme_val = 'light'
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """UPDATE domains 
                       SET parking_content = %s, content_theme = %s, updated_at = CURRENT_TIMESTAMP 
                       WHERE domain = %s AND user_id = %s""",
                    (content_value, content_theme_val, domain.lower(), user_id)
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.debug(f"Updated parking_content for domain {domain}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating parking_content for {domain}: {e}")
            return False

    def get_domain_for_parking_by_host(self, host: str) -> Optional[Dict[str, Any]]:
        """Get domain data for parking handler by Host header.
        
        Returns domain with owner wallet, parking_mode, parking_content.
        Tries: normalized host, then host without leading "www.", then Punycode for IDN.
        """
        from config.domain_utils import normalize_domain_for_lookup
        import unicodedata
        try:
            host_clean = host.strip().lower().split(':')[0]  # strip port if present
            normalized = unicodedata.normalize('NFC', normalize_domain_for_lookup(host_clean))
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT d.id, d.domain, d.parking_mode, d.parking_content, d.a_record_points_to_us,
                           u.wallet as owner_wallet
                    FROM domains d
                    JOIN users u ON d.user_id = u.id
                    WHERE d.domain = %s AND d.is_mining = TRUE
                """, (normalized,))
                row = cursor.fetchone()
                if not row and normalized.startswith('www.'):
                    cursor.execute("""
                        SELECT d.id, d.domain, d.parking_mode, d.parking_content, d.a_record_points_to_us,
                               u.wallet as owner_wallet
                        FROM domains d
                        JOIN users u ON d.user_id = u.id
                        WHERE d.domain = %s AND d.is_mining = TRUE
                    """, (normalized[4:],))
                    row = cursor.fetchone()
                if not row and normalized != host_clean:
                    cursor.execute("""
                        SELECT d.id, d.domain, d.parking_mode, d.parking_content, d.a_record_points_to_us,
                               u.wallet as owner_wallet
                        FROM domains d
                        JOIN users u ON d.user_id = u.id
                        WHERE d.domain = %s AND d.is_mining = TRUE
                    """, (host_clean,))
                    row = cursor.fetchone()
                if not row and 'xn--' not in normalized:
                    try:
                        import idna
                        punycode = idna.encode(normalized).decode('ascii')
                        cursor.execute("""
                            SELECT d.id, d.domain, d.parking_mode, d.parking_content, d.a_record_points_to_us,
                                   u.wallet as owner_wallet
                            FROM domains d
                            JOIN users u ON d.user_id = u.id
                            WHERE d.domain = %s AND d.is_mining = TRUE
                        """, (punycode,))
                        row = cursor.fetchone()
                    except Exception:
                        pass
                if row:
                    result = {
                        'id': row.get('id'),
                        'domain': row.get('domain'),
                        'parking_mode': row.get('parking_mode') or 'redirect',
                        'parking_content': row.get('parking_content'),
                        'a_record_points_to_us': row.get('a_record_points_to_us'),
                        'owner_wallet': row.get('owner_wallet'),
                    }
                    if result.get('parking_content') is None and result.get('id'):
                        cursor.execute("SELECT parking_content FROM domains WHERE id = %s", (result['id'],))
                        extra = cursor.fetchone()
                        if extra and extra.get('parking_content'):
                            result['parking_content'] = extra.get('parking_content')
                    return result
                return None
        except Exception as e:
            logger.error(f"Error getting domain for parking by host {host}: {e}")
            return None

    def get_domain_a_record_status(self, domain_id: int) -> Optional[bool]:
        """Get current A-record status for a domain.
        
        Args:
            domain_id: Domain ID
            
        Returns:
            True if A-record points to our server IP, False if not, None if not checked yet
        """
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "SELECT a_record_points_to_us FROM domains WHERE id = %s",
                    (domain_id,)
                )
                result = cursor.fetchone()
                if result:
                    return result.get('a_record_points_to_us') if isinstance(result, dict) else result[0]
                return None
        except Exception as e:
            logger.error(f"Error getting A-record status for domain {domain_id}: {e}")
            return None
    
    # ========================================================================
    # REWARDS LOG OPERATIONS (Using ClickHouse)
    # ========================================================================
    
    def get_user_earnings(self, wallet: str) -> Dict[str, float]:
        """Get earnings summary for a user by wallet address using ClickHouse."""
        if self._ch:
            try:
                return self._ch.get_user_earnings(wallet)
            except Exception as e:
                logger.error(f"Error getting user earnings from ClickHouse: {e}")
        
        # Fallback to default values
        return {
            'total_earned': 0.0,
            'pending': 0.0,
            'confirmed': 0.0,
            'total_transactions': 0
        }
    
    def get_domain_earnings(self, domain_id: int) -> float:
        """Get total earnings for a specific domain using ClickHouse."""
        if self._ch:
            try:
                return self._ch.get_domain_earnings(domain_id)
            except Exception as e:
                logger.error(f"Error getting domain earnings from ClickHouse: {e}")
        return 0.0
    
    def get_recent_rewards(self, wallet: str = None, domain_id: int = None, limit: int = 50) -> List[Dict]:
        """Get recent reward transactions using ClickHouse."""
        if self._ch:
            try:
                return self._ch.get_recent_rewards(wallet=wallet, domain_id=domain_id, limit=limit)
            except Exception as e:
                logger.error(f"Error getting recent rewards from ClickHouse: {e}")
        return []
    
    def _next_rewards_log_ids(self, count: int) -> List[int]:
        """Get next count IDs from PostgreSQL sequence (avoids expensive max(id) in ClickHouse)."""
        if not self._pg or count <= 0:
            return []
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "SELECT nextval('rewards_log_id_seq') FROM generate_series(1, %s)",
                    (count,)
                )
                rows = cursor.fetchall()
                if rows:
                    return [r['nextval'] if isinstance(r, dict) else r[0] for r in rows]
        except Exception as e:
            logger.debug(f"rewards_log_id_seq not available, using ClickHouse id fallback: {e}")
        return []

    def create_reward_log(self, domain_id: Optional[int], amount: float, amount_units: int,
                         wallet: str, txid: str = None, status: str = 'pending') -> Optional[int]:
        """Create a new reward log entry in ClickHouse. domain_id can be None for lottery bonuses."""
        if self._ch:
            try:
                row_id = None
                ids = self._next_rewards_log_ids(1)
                if ids:
                    row_id = ids[0]
                success = self._ch.create_reward_log(
                    domain_id, amount, amount_units, wallet, txid, status, row_id=row_id
                )
                if success:
                    # Update cached total_earnings in PostgreSQL domains table
                    # Only update if status is confirmed or accumulated (not pending/failed)
                    if domain_id and status in ('confirmed', 'accumulated'):
                        try:
                            with self.get_cursor() as (cursor, conn):
                                cursor.execute("""
                                    UPDATE domains 
                                    SET total_earnings = COALESCE(total_earnings, 0) + %s
                                    WHERE id = %s
                                """, (amount, domain_id))
                                conn.commit()
                                logger.debug(f"Updated total_earnings for domain {domain_id}: +{amount}")
                        except Exception as e:
                            logger.warning(f"Failed to update total_earnings for domain {domain_id}: {e}")
                    
                    # Also update user's total_earned cache
                    if status in ('confirmed', 'accumulated'):
                        try:
                            with self.get_cursor() as (cursor, conn):
                                # Find user by wallet
                                cursor.execute("SELECT id FROM users WHERE wallet = %s", (wallet,))
                                user_data = cursor.fetchone()
                                if user_data:
                                    user_id = user_data['id'] if isinstance(user_data, dict) else user_data[0]
                                    cursor.execute("""
                                        UPDATE users 
                                        SET total_earned = COALESCE(total_earned, 0) + %s
                                        WHERE id = %s
                                    """, (amount, user_id))
                                    conn.commit()
                                    logger.debug(f"Updated total_earned for user {user_id}: +{amount}")
                        except Exception as e:
                            logger.warning(f"Failed to update total_earned for wallet {wallet}: {e}")
                    
                    return 1
                return None
            except Exception as e:
                logger.error(f"Error creating reward log in ClickHouse: {e}")
        return None

    def create_reward_log_batch(self, domains_rewards: List[Dict], wallet: str,
                                status: str = 'accumulated') -> int:
        """
        Create multiple reward log entries in one ClickHouse insert (avoids N max(id) scans).
        Updates PostgreSQL domains.total_earnings and users.total_earned in batch.

        Args:
            domains_rewards: List of dicts with domain_id, amount, amount_units (and optionally domain)
            wallet: Recipient wallet address
            status: Transaction status (e.g. 'accumulated')

        Returns:
            Number of rows created, or 0 on failure
        """
        if not self._ch or not domains_rewards:
            return 0
        n = len(domains_rewards)
        ids = self._next_rewards_log_ids(n)
        if not ids or len(ids) != n:
            logger.error("[DB_PG] create_reward_log_batch: failed to get sequence ids")
            return 0
        now = datetime.now()
        rows = []
        for i, dr in enumerate(domains_rewards):
            rows.append({
                'id': ids[i],
                'domain_id': dr.get('domain_id'),
                'amount': float(dr.get('amount', 0)),
                'amount_units': int(dr.get('amount_units', 0)),
                'wallet': wallet,
                'txid': None,
                'status': status,
                'error_message': None,
                'created_at': now,
                'confirmed_at': None
            })
        try:
            self._ch.insert_reward_log_rows(rows)
        except Exception as e:
            logger.error(f"Error creating reward log batch in ClickHouse: {e}")
            return 0
        if status in ('confirmed', 'accumulated'):
            try:
                with self.get_cursor() as (cursor, conn):
                    for dr in domains_rewards:
                        domain_id = dr.get('domain_id')
                        amount = float(dr.get('amount', 0))
                        if domain_id and amount:
                            cursor.execute(
                                "UPDATE domains SET total_earnings = COALESCE(total_earnings, 0) + %s WHERE id = %s",
                                (amount, domain_id)
                            )
                    total_amount = sum(float(dr.get('amount', 0)) for dr in domains_rewards)
                    cursor.execute("SELECT id FROM users WHERE wallet = %s", (wallet,))
                    user_row = cursor.fetchone()
                    if user_row:
                        user_id = user_row['id'] if isinstance(user_row, dict) else user_row[0]
                        cursor.execute(
                            "UPDATE users SET total_earned = COALESCE(total_earned, 0) + %s WHERE id = %s",
                            (total_amount, user_id)
                        )
                    conn.commit()
            except Exception as e:
                logger.warning(f"Failed to update domain/user totals after reward log batch: {e}")
        return n

    # ========================================================================
    # PAYOUT OPERATIONS
    # ========================================================================
    
    def create_payout_request(self, user_id: int, wallet: str, amount: float, 
                              amount_units: int, triggered_by: str = 'manual') -> Optional[int]:
        """Create a new payout request."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """INSERT INTO payout_requests 
                       (user_id, wallet, amount, amount_units, status, triggered_by)
                       VALUES (%s, %s, %s, %s, 'pending', %s) RETURNING id""",
                    (user_id, wallet, amount, amount_units, triggered_by)
                )
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
        except Exception as e:
            logger.error(f"Error creating payout request: {e}")
            return None
    
    def get_user_payouts(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get payout history for a user."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT * FROM payout_requests 
                       WHERE user_id = %s 
                       ORDER BY created_at DESC 
                       LIMIT %s""",
                    (user_id, limit)
                )
                results = cursor.fetchall()
                return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error getting user payouts: {e}")
            return []
    
    # ========================================================================
    # SUBSCRIPTION OPERATIONS
    # ========================================================================
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for a user."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT ps.*, d.domain 
                       FROM promotion_subscriptions ps
                       JOIN domains d ON ps.domain_id = d.id
                       WHERE ps.user_id = %s
                       ORDER BY ps.created_at DESC""",
                    (user_id,)
                )
                results = cursor.fetchall()
                return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Error getting user subscriptions: {e}")
            return []
    
    def create_promotion_subscription(self, domain_id: int, user_id: int, 
                                      subscription_type: str, price_per_period: float,
                                      next_renewal_at: datetime) -> Optional[int]:
        """Create a new promotion subscription."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """INSERT INTO promotion_subscriptions 
                       (domain_id, user_id, subscription_type, price_per_period, next_renewal_at, status)
                       VALUES (%s, %s, %s, %s, %s, 'active') RETURNING id""",
                    (domain_id, user_id, subscription_type, price_per_period, next_renewal_at)
                )
                result = cursor.fetchone()
                conn.commit()
                return result['id'] if result else None
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return None
    
    def cancel_promotion_subscription(self, subscription_id: int, user_id: int = None) -> bool:
        """Cancel a promotion subscription."""
        try:
            with self.get_cursor() as (cursor, conn):
                if user_id:
                    cursor.execute(
                        """UPDATE promotion_subscriptions 
                           SET status = 'cancelled', cancelled_at = NOW()
                           WHERE id = %s AND user_id = %s""",
                        (subscription_id, user_id)
                    )
                else:
                    cursor.execute(
                        """UPDATE promotion_subscriptions 
                           SET status = 'cancelled', cancelled_at = NOW()
                           WHERE id = %s""",
                        (subscription_id,)
                    )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False
    
    def create_subscription(self, user_id: int, domain_id: int, frequency: str = '1hour') -> Dict[str, Any]:
        """
        Create a promotion subscription for a domain.
        Subscription costs 1 DOMAIN token per renewal and auto-renews.
        
        Args:
            user_id: User ID requesting the subscription
            domain_id: Domain ID to subscribe
            frequency: Renewal frequency (e.g., '5min', '1hour', '1week')
            
        Returns:
            Dict with 'success' (bool), 'message' (str), and optional 'subscription_id' (int)
        """
        try:
            from config.config import TOKEN_DECIMALS
            from config.subscription_config import (
                is_valid_frequency, 
                get_price_for_frequency,
                calculate_next_renewal,
                DEFAULT_FREQUENCY
            )
            from datetime import datetime
            
            # Validate frequency
            if not is_valid_frequency(frequency):
                frequency = DEFAULT_FREQUENCY
            
            # Get price for this frequency
            subscription_cost = get_price_for_frequency(frequency)
            subscription_cost_units = int(subscription_cost * (10 ** TOKEN_DECIMALS))
            
            with self.get_cursor() as (cursor, conn):
                # 1. Verify domain exists and belongs to user
                cursor.execute(
                    """SELECT d.id, d.domain, d.user_id, d.is_mining
                       FROM domains d
                       WHERE d.id = %s""",
                    (domain_id,)
                )
                domain = cursor.fetchone()
                
                if not domain:
                    return {'success': False, 'message': 'Domain not found'}
                
                if domain['user_id'] != user_id:
                    return {'success': False, 'message': 'You do not own this domain'}
                
                if not domain['is_mining']:
                    return {'success': False, 'message': 'Domain must be actively mining to subscribe'}
                
                # 2. Check if already subscribed
                cursor.execute(
                    """SELECT id FROM promotion_subscriptions
                       WHERE domain_id = %s AND status = 'active'""",
                    (domain_id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    return {'success': False, 'message': 'Domain already has an active subscription'}
                
                # 3. Check user balance for initial promotion
                cursor.execute(
                    """SELECT accumulated_balance, accumulated_units
                       FROM users
                       WHERE id = %s""",
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return {'success': False, 'message': 'User not found'}
                
                current_balance = float(user['accumulated_balance'] or 0)
                current_units = int(user['accumulated_units'] or 0)
                
                if current_balance < subscription_cost or current_units < subscription_cost_units:
                    return {
                        'success': False,
                        'message': f'Insufficient balance. You need at least {subscription_cost} DOMAIN tokens. Current balance: {current_balance:.2f}'
                    }
                
                # 4. Deduct balance for initial promotion
                new_balance = current_balance - subscription_cost
                new_units = current_units - subscription_cost_units
                
                cursor.execute(
                    """UPDATE users
                       SET accumulated_balance = %s,
                           accumulated_units = %s
                       WHERE id = %s""",
                    (new_balance, new_units, user_id)
                )
                
                # 5. Create subscription record
                now = datetime.now()
                next_renewal = calculate_next_renewal(now, frequency)
                
                cursor.execute(
                    """INSERT INTO promotion_subscriptions 
                       (domain_id, user_id, subscription_type, price_per_period, 
                        auto_renew, next_renewal_at, status)
                       VALUES (%s, %s, %s, %s, TRUE, %s, 'active')
                       RETURNING id""",
                    (domain_id, user_id, frequency, subscription_cost, next_renewal)
                )
                result = cursor.fetchone()
                subscription_id = result['id'] if result else None
                
                if not subscription_id:
                    conn.rollback()
                    return {'success': False, 'message': 'Failed to create subscription record'}
                
                # 6. Create initial promotion record
                cursor.execute(
                    """INSERT INTO domain_promotions 
                       (domain_id, user_id, amount, amount_units, promoted_at, subscription_id, status)
                       VALUES (%s, %s, %s, %s, %s, %s, 'active')
                       RETURNING id""",
                    (domain_id, user_id, subscription_cost, subscription_cost_units, now, subscription_id)
                )
                promotion_result = cursor.fetchone()
                promotion_id = promotion_result['id'] if promotion_result else None
                
                # 7. Update domain's promoted_at timestamp
                cursor.execute(
                    """UPDATE domains
                       SET promoted_at = %s
                       WHERE id = %s""",
                    (now, domain_id)
                )
                
                conn.commit()
                
                logger.info(f"Subscription created for domain {domain['domain']} (ID: {domain_id}) by user {user_id}. "
                           f"Frequency: {frequency}, Cost: {subscription_cost} tokens. New balance: {new_balance:.2f}")
                
                return {
                    'success': True,
                    'message': 'Subscription created successfully',
                    'subscription_id': subscription_id,
                    'promotion_id': promotion_id,
                    'frequency': frequency,
                    'next_renewal_at': next_renewal.isoformat(),
                    'new_balance': new_balance
                }
                
        except Exception as e:
            logger.error(f"Error creating subscription: {e}", exc_info=True)
            return {'success': False, 'message': f'Database error: {str(e)}'}
    
    def promote_domain(self, user_id: int, domain_id: int) -> Dict[str, Any]:
        """
        Promote a domain to the top of ratings by paying 1 DOMAIN token.
        
        Args:
            user_id: User ID requesting the promotion
            domain_id: Domain ID to promote
            
        Returns:
            Dict with 'success' (bool), 'message' (str), and optional 'promotion_id' (int)
        """
        try:
            from config.config import TOKEN_DECIMALS
            from datetime import datetime
            
            # Calculate amount in units (1 DOMAIN token)
            promotion_cost = 1.0
            promotion_cost_units = int(promotion_cost * (10 ** TOKEN_DECIMALS))
            
            with self.get_cursor() as (cursor, conn):
                # 1. Verify domain exists and belongs to user
                cursor.execute(
                    """SELECT d.id, d.domain, d.user_id, d.is_mining
                       FROM domains d
                       WHERE d.id = %s""",
                    (domain_id,)
                )
                domain = cursor.fetchone()
                
                if not domain:
                    return {'success': False, 'message': 'Domain not found'}
                
                if domain['user_id'] != user_id:
                    return {'success': False, 'message': 'You do not own this domain'}
                
                if not domain['is_mining']:
                    return {'success': False, 'message': 'Domain must be actively mining to be promoted'}
                
                # 2. Check user balance
                cursor.execute(
                    """SELECT accumulated_balance, accumulated_units
                       FROM users
                       WHERE id = %s""",
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return {'success': False, 'message': 'User not found'}
                
                current_balance = float(user['accumulated_balance'] or 0)
                current_units = int(user['accumulated_units'] or 0)
                
                if current_balance < promotion_cost or current_units < promotion_cost_units:
                    return {
                        'success': False,
                        'message': f'Insufficient balance. You need at least {promotion_cost} DOMAIN tokens. Current balance: {current_balance:.2f}'
                    }
                
                # 3. Deduct balance from user
                new_balance = current_balance - promotion_cost
                new_units = current_units - promotion_cost_units
                
                cursor.execute(
                    """UPDATE users
                       SET accumulated_balance = %s,
                           accumulated_units = %s
                       WHERE id = %s""",
                    (new_balance, new_units, user_id)
                )
                
                # 4. Insert promotion record
                promoted_at = datetime.now()
                
                cursor.execute(
                    """INSERT INTO domain_promotions 
                       (domain_id, user_id, amount, amount_units, promoted_at, status)
                       VALUES (%s, %s, %s, %s, %s, 'active')
                       RETURNING id""",
                    (domain_id, user_id, promotion_cost, promotion_cost_units, promoted_at)
                )
                result = cursor.fetchone()
                promotion_id = result['id'] if result else None
                
                if not promotion_id:
                    conn.rollback()
                    return {'success': False, 'message': 'Failed to create promotion record'}
                
                # 5. Update domain's promoted_at timestamp
                cursor.execute(
                    """UPDATE domains
                       SET promoted_at = %s
                       WHERE id = %s""",
                    (promoted_at, domain_id)
                )
                
                conn.commit()
                
                logger.info(f"Domain {domain['domain']} (ID: {domain_id}) promoted by user {user_id}. "
                           f"Cost: {promotion_cost} tokens. New balance: {new_balance:.2f}")
                
                return {
                    'success': True,
                    'message': 'Domain promoted successfully',
                    'promotion_id': promotion_id,
                    'promoted_at': promoted_at.isoformat(),
                    'new_balance': new_balance
                }
                
        except Exception as e:
            logger.error(f"Error promoting domain: {e}", exc_info=True)
            return {'success': False, 'message': f'Database error: {str(e)}'}
    
    def cancel_subscription(self, subscription_id: int, user_id: int) -> Dict[str, Any]:
        """
        Cancel a promotion subscription.
        
        Args:
            subscription_id: Subscription ID to cancel
            user_id: User ID requesting the cancellation (for authorization)
            
        Returns:
            Dict with 'success' (bool) and 'message' (str)
        """
        try:
            from datetime import datetime
            
            with self.get_cursor() as (cursor, conn):
                # Verify subscription exists and belongs to user
                cursor.execute(
                    """SELECT ps.id, ps.domain_id, ps.user_id, ps.status, d.domain
                       FROM promotion_subscriptions ps
                       JOIN domains d ON ps.domain_id = d.id
                       WHERE ps.id = %s""",
                    (subscription_id,)
                )
                subscription = cursor.fetchone()
                
                if not subscription:
                    return {'success': False, 'message': 'Subscription not found'}
                
                if subscription['user_id'] != user_id:
                    return {'success': False, 'message': 'You do not own this subscription'}
                
                if subscription['status'] != 'active':
                    return {'success': False, 'message': f'Subscription is already {subscription["status"]}'}
                
                # Cancel subscription
                now = datetime.now()
                cursor.execute(
                    """UPDATE promotion_subscriptions
                       SET status = 'cancelled',
                           auto_renew = FALSE,
                           cancelled_at = %s,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = %s""",
                    (now, subscription_id)
                )
                
                conn.commit()
                
                logger.info(f"Subscription {subscription_id} cancelled for domain {subscription['domain']} by user {user_id}")
                
                return {
                    'success': True,
                    'message': 'Subscription cancelled successfully'
                }
                
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}", exc_info=True)
            return {'success': False, 'message': f'Database error: {str(e)}'}
    
    # ========================================================================
    # RATING OPERATIONS
    # ========================================================================
    
    def get_domains_rating(self, page: int = 1, per_page: int = 100, 
                          sort_by: str = 'rating', sort_order: str = 'desc',
                          wallet: str = None,
                          sld_length: Optional[int] = 18,
                          registrar_id: Optional[int] = None,
                          hoster_id: Optional[int] = None,
                          zone: Optional[str] = None) -> Dict:
        """
        Get domains rating with pagination.
        
        Args:
            page: Page number (1-based)
            per_page: Items per page (max 100)
            sort_by: Field to sort by ('weight', 'rating', 'age', 'length')
            sort_order: Sort order ('asc' or 'desc')
            wallet: Optional wallet address to filter domains by
            sld_length: Length filter: 18 = 18+ (default), 1-17 = exact length. None = no filter.
            registrar_id: Optional filter by registrar id (for "domains by registrar" link)
            hoster_id: Optional filter by hoster id (for "domains by hoster" link)
            zone: Optional filter by zone/TLD (e.g. 'com', 'ru' for "domains by zone" link)
        """
        try:
            # Enforce limits
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            
            # Validate sort_by
            valid_sort_fields = ['weight', 'rating', 'age', 'length', 'newest', 'creation_date']
            if sort_by not in valid_sort_fields:
                sort_by = 'rating'
            
            # Validate sort_order
            sort_order = sort_order.lower()
            if sort_order not in ['asc', 'desc']:
                sort_order = 'desc'
            
            order = sort_order.upper()
            
            with self.get_cursor() as (cursor, conn):
                # Build base filters
                extra_where = []
                params_count = []
                if wallet:
                    extra_where.append("u.wallet = %s")
                    params_count.append(wallet)
                if sld_length is not None:
                    if sld_length >= 18:
                        extra_where.append("d.sld_length >= %s")
                        params_count.append(18)
                    else:
                        extra_where.append("d.sld_length = %s")
                        params_count.append(sld_length)
                if registrar_id is not None:
                    extra_where.append("d.registrar_id = %s")
                    params_count.append(registrar_id)
                if hoster_id is not None:
                    extra_where.append("d.hoster_id = %s")
                    params_count.append(hoster_id)
                if zone:
                    extra_where.append("LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', '')) = %s")
                    params_count.append(zone.lower())
                where_suffix = " AND " + " AND ".join(extra_where) if extra_where else ""
                
                # Get total count
                cursor.execute(
                    """SELECT COUNT(*) as total 
                       FROM domains d
                       JOIN users u ON d.user_id = u.id
                       WHERE d.is_mining = TRUE""" + where_suffix,
                    tuple(params_count)
                )
                total_result = cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                if total == 0:
                    return {
                        'domains': [],
                        'total': 0,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': 0
                    }
                
                # Build ORDER BY clause based on sort_by
                # For 'newest': single order by "bump to top" date (promoted + new mixed by recency)
                if sort_by == 'newest':
                    order_by_clause = (
                        f"COALESCE(d.promoted_at, d.verification_time, d.creation_date) {order} NULLS LAST, d.domain ASC"
                    )
                else:
                    if sort_by == 'weight':
                        regular_order_by = f"COALESCE(d.weight, 0) {order}, d.domain ASC"
                    elif sort_by == 'rating':
                        regular_order_by = f"COALESCE(d.total_earnings, 0) {order}, d.domain ASC"
                    elif sort_by == 'age':
                        # Sort by registration age only; domains without creation_date go last (NULLS LAST)
                        age_calc = "EXTRACT(EPOCH FROM (NOW() - d.creation_date)) / 31557600.0"
                        regular_order_by = f"{age_calc} {order} NULLS LAST, d.domain ASC"
                    elif sort_by == 'creation_date':
                        # Sort by registration date (creation_date); oldest/newest first
                        regular_order_by = f"d.creation_date {order} NULLS LAST, d.domain ASC"
                    elif sort_by == 'length':
                        regular_order_by = f"d.sld_length {order}, d.domain ASC"
                    else:
                        regular_order_by = "COALESCE(d.total_earnings, 0) DESC, d.domain ASC"
                    order_by_clause = (
                        "CASE WHEN d.promoted_at IS NOT NULL THEN 0 ELSE 1 END ASC, "
                        "d.promoted_at DESC NULLS LAST, "
                        f"{regular_order_by}"
                    )
                
                # Get paginated results
                params = list(params_count) + [per_page, offset]
                query = f"""
                    SELECT d.id, d.domain, d.description, d.sld_length, d.total_earnings, d.weight,
                           d.is_clickable, d.a_record_points_to_us, d.promoted_at, d.user_id, u.wallet,
                           d.creation_date, d.verification_time
                    FROM domains d
                    JOIN users u ON d.user_id = u.id
                    WHERE d.is_mining = TRUE {where_suffix}
                    ORDER BY {order_by_clause}
                    LIMIT %s OFFSET %s
                """
                cursor.execute(query, tuple(params))
                
                results = cursor.fetchall()
                domains = []
                for r in results:
                    row = dict(r)
                    # Transform to match frontend expected format
                    domain_data = {
                        'id': row['id'],
                        'domain': row['domain'],
                        'description': row.get('description'),
                        'user_id': row['user_id'],
                        'length': row.get('sld_length') or 0,
                        'rating': float(row.get('total_earnings') or 0),
                        'weight': float(row.get('weight') or 0),
                        'is_clickable': bool(row.get('is_clickable', False)),
                        'a_record_points_to_us': bool(row.get('a_record_points_to_us', False)) if row.get('a_record_points_to_us') is not None else False,
                        'is_promoted': row.get('promoted_at') is not None,
                        'promoted_at': row['promoted_at'].isoformat() if row.get('promoted_at') else None,
                        'has_subscription': False,  # TODO: Add subscription join if needed
                        'subscription_id': None,
                        'creation_date': row['creation_date'].isoformat() if row.get('creation_date') else None,
                        'creation_date_ru': self._format_creation_date_ru(row.get('creation_date')),
                        'wallet': row.get('wallet'),
                    }
                    
                    # Calculate human-readable age
                    domain_data['age'] = self._format_age_human_readable(
                        row.get('creation_date'),
                        row.get('verification_time')
                    )
                    
                    domains.append(domain_data)
                
                return {
                    'domains': domains,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page
                }
        except Exception as e:
            logger.error(f"Error getting domains rating: {e}", exc_info=True)
            return {'domains': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    def _format_age_human_readable(self, creation_date, verification_time) -> str:
        """
        Format domain registration age in human-readable format.
        Uses only creation_date (WHOIS registration date). Does not use verification_time,
        so AGE always means "domain registration age" for transparency.
        
        Returns:
            Human-readable age string like "2y 3m", "5m", "10d", "<1d", or "N/A" if no creation_date.
        """
        from datetime import datetime
        
        # Use only registration date; do not fall back to verification_time (time added to mining)
        ref_date = creation_date
        
        if not ref_date:
            return "N/A"
        
        # Handle string dates
        if isinstance(ref_date, str):
            try:
                ref_date = datetime.fromisoformat(ref_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return "N/A"
        
        # Calculate age
        now = datetime.now()
        if ref_date > now:
            return "<1d"
        
        delta = now - ref_date
        total_days = delta.days
        
        if total_days < 1:
            return "<1d"
        
        years = total_days // 365
        remaining_days = total_days % 365
        months = remaining_days // 30
        days = remaining_days % 30
        
        parts = []
        if years > 0:
            parts.append(f"{years}y")
        if months > 0:
            parts.append(f"{months}m")
        if years == 0 and months == 0 and days > 0:
            parts.append(f"{days}d")
        
        return " ".join(parts) if parts else "<1d"

    @staticmethod
    def _format_creation_date_ru(creation_date) -> Optional[str]:
        """Format creation_date as DD.MM.YYYY (Russian format). Returns None if no date."""
        if not creation_date:
            return None
        if isinstance(creation_date, str):
            try:
                creation_date = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        try:
            return creation_date.strftime("%d.%m.%Y")
        except (AttributeError, TypeError):
            return None

    def get_domains_rating_by_registration_date(self, page: int = 1, per_page: int = 100,
                                                 sort_order: str = 'asc', wallet: str = None) -> Dict:
        """
        Get verified domains sorted by registration date (creation_date).
        sort_order: 'asc' = oldest first, 'desc' = newest first.
        Returns creation_date in Russian format (DD.MM.YYYY) as creation_date_ru.
        """
        try:
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            order = 'ASC' if sort_order.lower() == 'asc' else 'DESC'
            with self.get_cursor() as (cursor, conn):
                where_parts = ["d.verified = TRUE", "d.is_mining = TRUE"]
                params = []
                if wallet:
                    where_parts.append("u.wallet = %s")
                    params.append(wallet)
                where_sql = " AND ".join(where_parts)
                cursor.execute(
                    f"""SELECT COUNT(*) as total FROM domains d
                        JOIN users u ON d.user_id = u.id
                        WHERE {where_sql}""",
                    tuple(params)
                )
                total = cursor.fetchone()['total'] or 0
                if total == 0:
                    return {'domains': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}
                cursor.execute(
                    f"""SELECT d.id, d.domain, d.description, d.sld_length, d.total_earnings, d.weight,
                               d.is_clickable, d.a_record_points_to_us, d.promoted_at, d.user_id, u.wallet,
                               d.creation_date, d.verification_time
                        FROM domains d
                        JOIN users u ON d.user_id = u.id
                        WHERE {where_sql}
                        ORDER BY d.creation_date {order} NULLS LAST, d.domain ASC
                        LIMIT %s OFFSET %s""",
                    tuple(params) + (per_page, offset)
                )
                results = cursor.fetchall()
                domains = []
                for r in results:
                    row = dict(r)
                    domain_data = {
                        'id': row['id'],
                        'domain': row['domain'],
                        'description': row.get('description'),
                        'user_id': row['user_id'],
                        'length': row.get('sld_length') or 0,
                        'rating': float(row.get('total_earnings') or 0),
                        'weight': float(row.get('weight') or 0),
                        'is_clickable': bool(row.get('is_clickable', False)),
                        'a_record_points_to_us': bool(row.get('a_record_points_to_us', False)) if row.get('a_record_points_to_us') is not None else False,
                        'is_promoted': row.get('promoted_at') is not None,
                        'promoted_at': row['promoted_at'].isoformat() if row.get('promoted_at') else None,
                        'has_subscription': False,
                        'subscription_id': None,
                        'creation_date': row['creation_date'].isoformat() if row.get('creation_date') else None,
                        'creation_date_ru': self._format_creation_date_ru(row.get('creation_date')),
                        'wallet': row.get('wallet'),
                    }
                    domain_data['age'] = self._format_age_human_readable(row.get('creation_date'), row.get('verification_time'))
                    domains.append(domain_data)
                return {
                    'domains': domains,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page
                }
        except Exception as e:
            logger.error(f"Error getting domains rating by registration date: {e}", exc_info=True)
            return {'domains': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

    def get_registrars_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get registrars rating by sum of domain total_earnings. Includes slug for link to domain rating by registrar."""
        try:
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT r.id, r.name, r.slug,
                           COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) as total_earnings,
                           COUNT(d.id) as domains_count
                    FROM registrars r
                    LEFT JOIN domains d ON d.registrar_id = r.id AND d.is_mining = TRUE
                    GROUP BY r.id, r.name, r.slug
                    HAVING COUNT(d.id) > 0
                    ORDER BY total_earnings DESC, r.name ASC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                rows = cursor.fetchall()
                cursor.execute("""
                    SELECT COUNT(DISTINCT r.id) as total FROM registrars r
                    JOIN domains d ON d.registrar_id = r.id AND d.is_mining = TRUE
                """)
                total = cursor.fetchone()['total'] or 0
                items = [{'id': r['id'], 'name': r['name'], 'slug': r['slug'], 'total_earnings': float(r['total_earnings']), 'domains_count': r['domains_count']} for r in rows]
                return {'registrars': items, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page if total else 0}
        except Exception as e:
            logger.error(f"Error getting registrars rating: {e}", exc_info=True)
            return {'registrars': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

    def get_hosters_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get hosters rating by sum of domain total_earnings."""
        try:
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    SELECT h.id, h.name, h.slug,
                           COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) as total_earnings,
                           COUNT(d.id) as domains_count
                    FROM hosters h
                    LEFT JOIN domains d ON d.hoster_id = h.id AND d.is_mining = TRUE
                    GROUP BY h.id, h.name, h.slug
                    HAVING COUNT(d.id) > 0
                    ORDER BY total_earnings DESC, h.name ASC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                rows = cursor.fetchall()
                cursor.execute("""
                    SELECT COUNT(DISTINCT h.id) as total FROM hosters h
                    JOIN domains d ON d.hoster_id = h.id AND d.is_mining = TRUE
                """)
                total = cursor.fetchone()['total'] or 0
                items = [{'id': h['id'], 'name': h['name'], 'slug': h['slug'], 'total_earnings': float(h['total_earnings']), 'domains_count': h['domains_count']} for h in rows]
                return {'hosters': items, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page if total else 0}
        except Exception as e:
            logger.error(f"Error getting hosters rating: {e}", exc_info=True)
            return {'hosters': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

    def get_domain_zones_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get domain zones (TLD) rating by sum of domain total_earnings. Zone = part after last dot (e.g. com, ru)."""
        try:
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            with self.get_cursor() as (cursor, conn):
                # NOTE: Use %% to escape % in LIKE - psycopg2 treats % as placeholder
                cursor.execute("""
                    SELECT LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', '')) AS zone,
                           COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) AS total_earnings,
                           COUNT(d.id) AS domains_count
                    FROM domains d
                    WHERE d.is_mining = TRUE AND d.domain LIKE '%%.%%'
                    GROUP BY LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', ''))
                    ORDER BY total_earnings DESC, zone ASC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                rows = cursor.fetchall()
                cursor.execute("""
                    SELECT COUNT(DISTINCT LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', ''))) AS total
                    FROM domains d
                    WHERE d.is_mining = TRUE AND d.domain LIKE '%%.%%'
                """)
                total = cursor.fetchone()['total'] or 0
                items = [{'zone': r['zone'], 'total_earnings': float(r['total_earnings']), 'domains_count': r['domains_count']} for r in rows]
                return {'zones': items, 'total': total, 'page': page, 'per_page': per_page, 'total_pages': (total + per_page - 1) // per_page if total else 0}
        except Exception as e:
            logger.error(f"Error getting domain zones rating: {e}", exc_info=True)
            return {'zones': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

    def get_wallets_rating(self, page: int = 1, per_page: int = 100,
                          sort_by: str = 'rating', sort_order: str = 'desc') -> Dict:
        """Get wallets rating with pagination."""
        try:
            # Enforce limits
            per_page = min(max(1, per_page), 100)
            page = max(1, page)
            offset = (page - 1) * per_page
            
            # Validate sort_by - map frontend names to database columns
            sort_column_map = {
                'rating': 'total_earnings',
                'domains_count': 'domain_count'
            }
            db_sort_column = sort_column_map.get(sort_by, 'total_earnings')
            
            order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
            
            with self.get_cursor() as (cursor, conn):
                # Get total count of unique wallets with mining domains
                cursor.execute("""
                    SELECT COUNT(DISTINCT u.wallet) as count 
                    FROM users u 
                    JOIN domains d ON u.id = d.user_id 
                    WHERE d.is_mining = TRUE AND u.wallet IS NOT NULL
                """)
                total_result = cursor.fetchone()
                total = total_result['count'] if total_result else 0
                
                if total == 0:
                    return {
                        'wallets': [],
                        'total': 0,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': 0
                    }
                
                # Get paginated results
                cursor.execute(f"""
                    SELECT u.wallet, 
                           COUNT(d.id) as domain_count,
                           COALESCE(SUM(d.total_earnings), 0) as total_earnings,
                           COALESCE(SUM(d.weight), 0) as total_weight
                    FROM users u
                    JOIN domains d ON u.id = d.user_id
                    WHERE d.is_mining = TRUE AND u.wallet IS NOT NULL
                    GROUP BY u.wallet
                    ORDER BY {db_sort_column} {order} NULLS LAST
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                
                results = cursor.fetchall()
                wallets = []
                for r in results:
                    row = dict(r)
                    # Transform to match frontend expected format
                    wallet_data = {
                        'wallet': row['wallet'],
                        'domains_count': int(row.get('domain_count') or 0),
                        'rating': float(row.get('total_earnings') or 0),
                        'weight': float(row.get('total_weight') or 0),
                    }
                    wallets.append(wallet_data)
                
                return {
                    'wallets': wallets,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page
                }
        except Exception as e:
            logger.error(f"Error getting wallets rating: {e}", exc_info=True)
            return {'wallets': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    # ========================================================================
    # STATS OPERATIONS
    # ========================================================================
    
    def get_system_stats(self) -> Dict:
        """Get system-wide statistics."""
        stats = {
            'total_users': 0,
            'total_domains': 0,
            'mining_domains': 0,
            'total_rewards': 0.0
        }
        
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT COUNT(*) as count FROM users")
                result = cursor.fetchone()
                stats['total_users'] = result['count'] if result else 0
                
                cursor.execute("SELECT COUNT(*) as count FROM domains")
                result = cursor.fetchone()
                stats['total_domains'] = result['count'] if result else 0
                
                cursor.execute("SELECT COUNT(*) as count FROM domains WHERE is_mining = TRUE")
                result = cursor.fetchone()
                stats['mining_domains'] = result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting PostgreSQL stats: {e}")
        
        # Get rewards stats from ClickHouse
        if self._ch:
            try:
                ch_stats = self._ch.get_system_stats()
                stats['total_rewards'] = ch_stats.get('total_amount', 0.0)
                stats['total_transactions'] = ch_stats.get('total_transactions', 0)
            except Exception as e:
                logger.error(f"Error getting ClickHouse stats: {e}")
        
        return stats
    
    def get_stats(self) -> Dict:
        """Get public system-wide statistics (alias for compatibility)."""
        stats = self.get_system_stats()
        
        # Get additional stats from ClickHouse
        ch_stats = {}
        if self._ch:
            try:
                ch_stats = self._ch.get_system_stats()
                if not ch_stats:
                    logger.warning(f"ClickHouse get_system_stats() returned empty dict")
            except Exception as e:
                logger.error(f"Error getting ClickHouse stats: {e}", exc_info=True)
                import traceback
                logger.error(f"ClickHouse stats traceback: {traceback.format_exc()}")
        
        return {
            'total_domains': stats.get('total_domains', 0),
            'active_domains': stats.get('mining_domains', 0),
            'verified_domains': stats.get('mining_domains', 0),  # Approximation
            'total_users': stats.get('total_users', 0),
            'total_rewards_distributed': ch_stats.get('confirmed_amount', 0.0) + ch_stats.get('accumulated_amount', 0.0),
            'successful_transactions': ch_stats.get('confirmed_transactions', 0) + ch_stats.get('accumulated_transactions', 0),
            'failed_transactions': ch_stats.get('failed_transactions', 0)
        }
    
    # ========================================================================
    # USER REWARDS OPERATIONS (Using ClickHouse)
    # ========================================================================
    
    def get_user_rewards(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get recent rewards for a user (from ClickHouse)."""
        try:
            # First get user's domains to find their domain_ids
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "SELECT id, domain FROM domains WHERE user_id = %s",
                    (user_id,)
                )
                domains = cursor.fetchall()
                domain_map = {d['id']: d['domain'] for d in domains}
                domain_ids = list(domain_map.keys())
                
                # Also get user's wallet for lottery bonuses
                cursor.execute("SELECT wallet FROM users WHERE id = %s", (user_id,))
                user_result = cursor.fetchone()
                wallet = user_result['wallet'] if user_result else None
            
            if not domain_ids and not wallet:
                return []
            
            # Query ClickHouse for rewards
            if self._ch:
                rewards = []
                
                # Get domain rewards
                if domain_ids:
                    domain_ids_str = ','.join(str(d) for d in domain_ids)
                    domain_rewards = self._ch.execute_dict(f"""
                        SELECT id, domain_id, amount, amount_units, wallet, txid, status, 
                               error_message, created_at, confirmed_at
                        FROM rewards_log
                        WHERE domain_id IN ({domain_ids_str})
                        ORDER BY created_at DESC
                        LIMIT {limit}
                    """)
                    
                    for r in domain_rewards:
                        r['domain'] = domain_map.get(r.get('domain_id'), 'Unknown')
                        rewards.append(r)
                
                # Get lottery bonuses (domain_id IS NULL)
                if wallet:
                    lottery_rewards = self._ch.execute_dict(f"""
                        SELECT id, domain_id, amount, amount_units, wallet, txid, status,
                               error_message, created_at, confirmed_at
                        FROM rewards_log
                        WHERE domain_id IS NULL AND wallet = %(wallet)s
                        ORDER BY created_at DESC
                        LIMIT {limit}
                    """, {'wallet': wallet})
                    
                    for r in lottery_rewards:
                        r['domain'] = 'LOTTERY_BONUS'
                        rewards.append(r)
                
                # Sort combined results by created_at
                rewards.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
                return rewards[:limit]
            
            return []
        except Exception as e:
            logger.error(f"Error getting user rewards: {e}")
            return []
    
    def update_user_total_earned(self, user_id: int, total_earned: float) -> bool:
        """Update user's total_earned cache."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE users SET total_earned = %s WHERE id = %s",
                    (total_earned, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user total_earned: {e}")
            return False
    
    # ========================================================================
    # SYSTEM STATE OPERATIONS
    # ========================================================================
    
    def get_system_state(self, key: str) -> Optional[int]:
        """Get system state integer value"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT value_int FROM system_state WHERE key_name = %s", (key,))
                res = cursor.fetchone()
                return res['value_int'] if res else None
        except Exception as e:
            logger.error(f"Error getting system state {key}: {e}")
            return None

    def set_system_state(self, key: str, value: int):
        """Set system state integer value"""
        try:
            with self.get_cursor() as (cursor, conn):
                # PostgreSQL uses ON CONFLICT instead of ON DUPLICATE KEY
                cursor.execute(
                    """INSERT INTO system_state (key_name, value_int) 
                       VALUES (%s, %s) 
                       ON CONFLICT (key_name) DO UPDATE SET value_int = %s""",
                    (key, value, value)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error setting system state {key}: {e}")
    
    # ========================================================================
    # POOL STATE OPERATIONS
    # ========================================================================
    
    def fetch_pool_state(self) -> List[Dict[str, Any]]:
        """Fetch global pool state (aggregates by length)"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT length_bucket, domain_count, r_sum FROM pool_state")
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error fetching pool state: {e}")
            return []

    def save_pool_state(self, n_l: List[int], r_l: List[float]):
        """Save pool aggregates to database."""
        try:
            data = []
            for l in range(1, 64):
                data.append((int(n_l[l]), float(r_l[l]), l))
            
            with self.get_cursor() as (cursor, conn):
                cursor.executemany(
                    """UPDATE pool_state 
                       SET domain_count = %s, r_sum = %s 
                       WHERE length_bucket = %s""",
                    data
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving pool state: {e}")
    
    def tick_domains_age(self, decay_factor: float):
        """Apply age decay to all active mining domains."""
        try:
            from tokenomics.constants import W_LEN, B_FACTOR
            
            with self.get_cursor() as (cursor, conn):
                W_BASE = 610.0 * 6  # ALPHA = 6
                PHI_VAL = 1.6180339887
                
                # PostgreSQL syntax
                cursor.execute(
                    f"""UPDATE domains 
                       SET age_r = age_r * %s,
                           weight = GREATEST(1.0, {W_BASE} * POWER({PHI_VAL}, -(GREATEST(1, COALESCE(sld_length, 63)) - 1))) 
                                   * (1.0 + {B_FACTOR} * (1.0 - (age_r * %s)))
                       WHERE is_mining = TRUE 
                         AND sld_length IS NOT NULL 
                         AND age_r IS NOT NULL""",
                    (decay_factor, decay_factor)
                )
                conn.commit()
                logger.debug(f"Applied age decay (factor={decay_factor}) and recalculated weights")
        except Exception as e:
            logger.error(f"Error applying age decay: {e}")

    def get_active_miners(self) -> List[Dict[str, Any]]:
        """Get all active mining domains for hourly calculation"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT d.id, d.user_id, d.sld_length, d.age_r, 
                              COALESCE(d.is_clickable, FALSE) as is_clickable,
                              d.a_record_points_to_us,
                              COALESCE(d.parking_mode, 'redirect') as parking_mode
                       FROM domains d
                       WHERE d.is_mining = TRUE"""
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting active miners: {e}")
            return []
    
    def batch_update_user_balances(self, updates: List[Tuple[float, int, int]]):
        """Update accumulated balances for users."""
        if not updates:
            logger.warning("batch_update_user_balances called with empty updates list")
            return
            
        try:
            with self.get_cursor() as (cursor, conn):
                for reward_amount, reward_units, user_id in updates:
                    logger.info(f"Updating balance for user {user_id}: +{reward_amount} tokens ({reward_units} units)")
                
                rows_affected = cursor.executemany(
                    """UPDATE users 
                       SET accumulated_balance = accumulated_balance + %s,
                           accumulated_units = accumulated_units + %s
                       WHERE id = %s""",
                    updates
                )
                conn.commit()
                logger.info(f"batch_update_user_balances: Updated {rows_affected} rows, committed transaction")
        except Exception as e:
            logger.error(f"Error in batch_update_user_balances: {e}")
            raise
    
    # ========================================================================
    # PAYOUT OPERATIONS (Additional)
    # ========================================================================
    
    def get_pending_payouts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending payout requests (including processing status that may have failed)"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT * FROM payout_requests 
                       WHERE status IN ('pending', 'processing') 
                       ORDER BY 
                         CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                         created_at ASC 
                       LIMIT %s""",
                    (limit,)
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting pending payouts: {e}")
            return []
    
    def update_payout_status(self, request_id: int, status: str, 
                            txid: Optional[str] = None, error: Optional[str] = None):
        """Update payout request status"""
        try:
            with self.get_cursor() as (cursor, conn):
                update_sql = """UPDATE payout_requests SET status = %s"""
                params = [status]
                
                if txid:
                    update_sql += ", tx_id = %s"
                    params.append(txid)
                
                if error:
                    update_sql += ", error_message = %s"
                    params.append(error)
                
                if status == 'completed':
                    update_sql += ", processed_at = NOW()"
                elif status == 'pending':
                    # Clear error message and tx_id when resetting to pending
                    update_sql += ", error_message = NULL, tx_id = NULL"
                
                update_sql += " WHERE id = %s"
                params.append(request_id)
                
                cursor.execute(update_sql, tuple(params))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating payout status: {e}")
    
    def deduct_user_balance(self, user_id: int, amount: float, amount_units: int):
        """Deduct paid amount from user accumulated balance"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """UPDATE users 
                       SET accumulated_balance = accumulated_balance - %s,
                           accumulated_units = accumulated_units - %s,
                           last_payout_at = NOW()
                       WHERE id = %s""",
                    (amount, amount_units, user_id)
                )
                conn.commit()
                logger.info(f"Successfully deducted {amount} tokens ({amount_units} units) from user {user_id}")
        except Exception as e:
            logger.error(f"Error deducting user balance: {e}")
            raise
    
    def mark_accumulated_rewards_as_confirmed(self, user_id: int, amount: float, 
                                             txid: str) -> int:
        """
        Mark accumulated rewards as confirmed (FIFO - oldest first).
        Updates reward_log entries from 'accumulated' to 'confirmed' up to the payout amount.
        Uses ClickHouse for rewards_log table.
        
        Args:
            user_id: User ID
            amount: Total amount to mark as confirmed
            txid: Transaction ID
            
        Returns:
            Number of reward log entries updated
        """
        if not self._ch:
            logger.error("ClickHouse not available, cannot mark rewards as confirmed")
            return 0
        
        try:
            # Get user's wallet address
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT wallet FROM users WHERE id = %s", (user_id,))
                user_data = cursor.fetchone()
                user_wallet = user_data['wallet'] if user_data and user_data.get('wallet') else None
            
            if not user_wallet:
                logger.warning(f"User {user_id} has no wallet address")
                return 0
            
            # Get user's domain IDs for filtering
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT id FROM domains WHERE user_id = %s", (user_id,))
                domains = cursor.fetchall()
                domain_ids = [d['id'] for d in domains] if domains else []
            
            # Build ClickHouse query to get accumulated rewards (FIFO order)
            # Match by: (1) domain belongs to user, or (2) domain_id is NULL but wallet matches
            conditions = ["status = 'accumulated'"]
            params = {}
            
            if domain_ids:
                domain_ids_str = ','.join(str(d) for d in domain_ids)
                conditions.append(f"(domain_id IN ({domain_ids_str}) OR (domain_id IS NULL AND wallet = %(wallet)s))")
            else:
                conditions.append("domain_id IS NULL AND wallet = %(wallet)s")
            
            params['wallet'] = user_wallet
            where_clause = " AND ".join(conditions)
            
            # Get accumulated rewards ordered by created_at (FIFO)
            query = f"""
                SELECT id, amount, amount_units
                FROM rewards_log
                WHERE {where_clause}
                ORDER BY created_at ASC, id ASC
            """
            
            accumulated_rewards = self._ch.execute_dict(query, params)
            
            if not accumulated_rewards:
                logger.warning(f"No accumulated rewards found for user {user_id}")
                return 0
            
            # Mark rewards as confirmed up to the payout amount (FIFO)
            remaining = amount
            updated_count = 0
            log_ids_to_update = []
            
            for reward in accumulated_rewards:
                if remaining <= 0:
                    break
                
                reward_amount = float(reward['amount'])
                if reward_amount <= remaining:
                    # Mark entire reward as confirmed
                    log_ids_to_update.append(reward['id'])
                    remaining -= reward_amount
                    updated_count += 1
                else:
                    # This reward is partially included - mark it anyway (don't split)
                    if remaining > 0:
                        log_ids_to_update.append(reward['id'])
                        updated_count += 1
                    break
            
            if log_ids_to_update:
                # Update rewards in ClickHouse using ALTER TABLE UPDATE
                # ClickHouse uses ALTER TABLE UPDATE syntax (asynchronous mutation)
                # Build WHERE clause with all IDs
                log_ids_str = ','.join(str(id) for id in log_ids_to_update)
                
                # ClickHouse ALTER TABLE UPDATE syntax
                # Make mutation synchronous to ensure it completes
                # Escape txid to prevent SQL injection
                txid_escaped = txid.replace("'", "''")
                
                # Set mutations_sync to wait for completion
                self._ch.execute("SET mutations_sync = 2")
                
                update_query = f"""
                    ALTER TABLE rewards_log 
                    UPDATE 
                        status = 'confirmed',
                        txid = '{txid_escaped}',
                        confirmed_at = now()
                    WHERE id IN ({log_ids_str})
                """
                
                self._ch.execute(update_query)
                logger.info(f"Marked {updated_count} reward log entries as confirmed for user {user_id}, tx {txid}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error marking accumulated rewards as confirmed: {e}", exc_info=True)
            return 0
    
    def get_users_for_auto_payout(self) -> List[Dict[str, Any]]:
        """Get users who reached their payout threshold"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT id, wallet, accumulated_balance, accumulated_units
                       FROM users 
                       WHERE payout_mode = 'auto' 
                         AND payout_threshold IS NOT NULL 
                         AND accumulated_balance >= payout_threshold
                         AND accumulated_balance > 0"""
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting auto-payout users: {e}")
            return []
    
    def get_random_users_with_active_domains(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get random users who have at least 1 active mining domain. Used for hourly lottery distribution."""
        try:
            with self.get_cursor() as (cursor, conn):
                # PostgreSQL uses RANDOM() instead of RAND()
                cursor.execute(
                    """SELECT u.id, u.wallet, COUNT(d.id) as domain_count
                       FROM users u
                       INNER JOIN domains d ON d.user_id = u.id
                       WHERE d.is_mining = TRUE
                         AND u.wallet IS NOT NULL
                       GROUP BY u.id, u.wallet
                       HAVING COUNT(d.id) >= 1
                       ORDER BY RANDOM()
                       LIMIT %s""",
                    (count,)
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting random users with active domains: {e}")
            return []

    def count_users_with_active_domains(self) -> int:
        """Count total number of users who have at least 1 active mining domain. Used to check if lottery can be run."""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    """SELECT COUNT(DISTINCT u.id)
                       FROM users u
                       INNER JOIN domains d ON d.user_id = u.id
                       WHERE d.is_mining = TRUE
                         AND u.wallet IS NOT NULL"""
                )
                result = cursor.fetchone()
                if result:
                    # Handle dict format
                    if isinstance(result, dict):
                        return result.get('count', 0)
                    else:
                        return result[0] if result[0] is not None else 0
                return 0
        except Exception as e:
            logger.error(f"Error counting users with active domains: {e}")
            return 0
    
    def update_domain_check(self, domain_id: int, success: bool) -> bool:
        """Update domain check timestamp and status"""
        try:
            with self.get_cursor() as (cursor, conn):
                if success:
                    cursor.execute(
                        """UPDATE domains 
                           SET last_check = NOW(), failed_checks = 0 
                           WHERE id = %s""",
                        (domain_id,)
                    )
                else:
                    cursor.execute(
                        """UPDATE domains 
                           SET last_check = NOW(), failed_checks = failed_checks + 1 
                           WHERE id = %s""",
                        (domain_id,)
                    )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating domain check: {e}")
            return False
    
    def disable_domain_mining(self, domain_id: int) -> bool:
        """Disable mining for a domain"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE domains SET is_mining = FALSE WHERE id = %s",
                    (domain_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error disabling domain mining: {e}")
            return False
    
    def update_last_reward(self, domain_id: int) -> bool:
        """Update last_reward timestamp for a domain"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "UPDATE domains SET last_reward = CURRENT_TIMESTAMP WHERE id = %s",
                    (domain_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating last reward: {e}")
            return False
    
    def check_nonce_exists(self, nonce: str) -> bool:
        """Check if a nonce already exists in the database"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT id FROM domains WHERE nonce = %s LIMIT 1", (nonce,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking nonce: {e}")
            return False
    
    def update_domain_weight(self, domain_id: int) -> bool:
        """
        Recalculate and update cached weight for a domain.
        Weight = W_len[L] * (1 + B_FACTOR * (1 - age_r))
        
        Args:
            domain_id: Domain ID
            
        Returns:
            True if successful
        """
        try:
            from tokenomics.constants import W_LEN, B_FACTOR
            
            with self.get_cursor() as (cursor, conn):
                # Get domain's sld_length and age_r
                cursor.execute(
                    "SELECT sld_length, age_r FROM domains WHERE id = %s",
                    (domain_id,)
                )
                domain_data = cursor.fetchone()
                
                if not domain_data:
                    logger.warning(f"Domain {domain_id} not found for weight update")
                    return False
                
                sld_length = domain_data.get('sld_length')
                age_r = domain_data.get('age_r')
                
                if sld_length is None or age_r is None:
                    logger.debug(f"Domain {domain_id} missing sld_length or age_r, skipping weight update")
                    return False
                
                # Calculate weight
                if 1 <= sld_length <= 63:
                    w_len = W_LEN[sld_length]
                    w_age = 1.0 + B_FACTOR * (1.0 - float(age_r))
                    weight = w_len * w_age
                else:
                    weight = 1.0
                
                # Update cached weight
                cursor.execute(
                    "UPDATE domains SET weight = %s WHERE id = %s",
                    (weight, domain_id)
                )
                conn.commit()
                logger.debug(f"Updated weight to {weight:.2f} for domain {domain_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating domain weight: {e}")
            return False
    
    def update_domain_metadata(self, domain_id: int) -> bool:
        """
        Update domain metadata (creation_date, age_r, weight) for a domain.
        Fetches creation_date from WHOIS if missing, calculates age_r and weight.
        
        Args:
            domain_id: Domain ID
            
        Returns:
            True if successful
        """
        try:
            with self.get_cursor() as (cursor, conn):
                # Get domain data
                cursor.execute(
                    "SELECT domain, creation_date, verification_time, sld_length, age_r FROM domains WHERE id = %s",
                    (domain_id,)
                )
                domain_data = cursor.fetchone()
                
                if not domain_data:
                    logger.error(f"Domain {domain_id} not found")
                    return False
                
                domain_name = domain_data['domain']
                creation_date = domain_data.get('creation_date')
                verification_time = domain_data.get('verification_time')
                sld_length = domain_data.get('sld_length')
                current_age_r = domain_data.get('age_r')
                
                # Fetch creation date, registrar and NS from WHOIS if not already stored
                domain_creation_date = creation_date
                registrar_id = None
                hoster_id = None
                try:
                    from oracle.whois_service import get_domain_whois_extra, get_domain_creation_date
                    extra_date, registrar_name, name_servers = get_domain_whois_extra(domain_name)
                    if not domain_creation_date and extra_date:
                        domain_creation_date = extra_date
                        logger.info(f"Fetched creation date for {domain_name}: {domain_creation_date.date()}")
                    elif not domain_creation_date:
                        domain_creation_date = get_domain_creation_date(domain_name)
                    try:
                        if registrar_name:
                            registrar_id = self._get_or_create_registrar(cursor, conn, registrar_name)
                        if name_servers:
                            from oracle.whois_service import _normalize_hoster_from_ns
                            hoster_name = _normalize_hoster_from_ns(name_servers[0])
                            if hoster_name:
                                hoster_id = self._get_or_create_hoster(cursor, conn, hoster_name)
                    except Exception as reg_host_err:
                        logger.debug(f"Registrar/hoster resolution skipped for {domain_name}: {reg_host_err}")
                except Exception as e:
                    logger.warning(f"Error fetching WHOIS for {domain_name}: {e}")
                    if not domain_creation_date:
                        try:
                            from oracle.whois_service import get_domain_creation_date
                            domain_creation_date = get_domain_creation_date(domain_name)
                        except Exception:
                            pass
                
                # Calculate age_r factor
                age_r = None
                try:
                    from tokenomics.weights import calculate_age_factor
                    from oracle.whois_service import get_domain_age_years
                    
                    age_years = get_domain_age_years(domain_name, fallback_to_zero=True)
                    
                    # Fallback to verification time if WHOIS fails
                    if age_years == 0.0 and verification_time:
                        if isinstance(verification_time, datetime):
                            delta = datetime.now() - verification_time
                            age_years = delta.total_seconds() / (365.25 * 24 * 3600)
                        elif isinstance(verification_time, str):
                            try:
                                vtime = datetime.fromisoformat(str(verification_time).replace('Z', '+00:00'))
                                delta = datetime.now() - vtime
                                age_years = delta.total_seconds() / (365.25 * 24 * 3600)
                            except:
                                pass
                    
                    age_r = calculate_age_factor(age_years)
                    logger.info(f"Calculated age_r={age_r:.6f} (age={age_years:.2f} years) for domain {domain_name}")
                    
                except Exception as e:
                    logger.error(f"Error calculating age_r for domain {domain_name}: {e}")
                    age_r = current_age_r  # Keep existing value if calculation fails
                
                # Calculate weight if we have both sld_length and age_r
                weight = None
                if sld_length is not None and age_r is not None:
                    try:
                        from tokenomics.constants import W_LEN, B_FACTOR
                        if 1 <= sld_length <= 63:
                            w_len = W_LEN[sld_length]
                            w_age = 1.0 + B_FACTOR * (1.0 - age_r)
                            weight = w_len * w_age
                        else:
                            weight = 1.0
                    except Exception as e:
                        logger.warning(f"Error calculating weight for domain {domain_name}: {e}")
                
                # Update domain with calculated values
                update_fields = []
                update_values = []
                
                if domain_creation_date and not creation_date:
                    update_fields.append("creation_date = %s")
                    update_values.append(domain_creation_date)
                    update_fields.append("whois_last_check = CURRENT_DATE")
                
                if age_r is not None:
                    update_fields.append("age_r = %s")
                    update_values.append(age_r)
                
                if weight is not None:
                    update_fields.append("weight = %s")
                    update_values.append(weight)
                
                if registrar_id is not None:
                    update_fields.append("registrar_id = %s")
                    update_values.append(registrar_id)
                if hoster_id is not None:
                    update_fields.append("hoster_id = %s")
                    update_values.append(hoster_id)
                
                if update_fields:
                    update_values.append(domain_id)
                    update_query = f"""
                        UPDATE domains 
                        SET {', '.join(update_fields)}
                        WHERE id = %s
                    """
                    cursor.execute(update_query, update_values)
                    conn.commit()
                    logger.info(f"Updated metadata for domain {domain_name} (ID: {domain_id})")
                    return True
                else:
                    logger.info(f"No metadata updates needed for domain {domain_name} (ID: {domain_id})")
                    return True
                
        except Exception as e:
            logger.error(f"Error updating domain metadata: {e}", exc_info=True)
            return False

    def update_domain_registrar_hoster(self, domain_id: int) -> bool:
        """
        Fetch WHOIS registrar and name servers for a domain and set registrar_id, hoster_id.
        Does not change creation_date, age_r, weight. Used for backfilling.
        """
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT id, domain FROM domains WHERE id = %s", (domain_id,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Domain id={domain_id} not found")
                    return False
                domain_name = row['domain']
                try:
                    from oracle.whois_service import get_domain_whois_extra, _normalize_hoster_from_ns
                    creation_date, registrar_name, name_servers = get_domain_whois_extra(domain_name)
                except Exception as e:
                    logger.warning(f"WHOIS extra failed for {domain_name}: {e}")
                    return False
                registrar_id = None
                hoster_id = None
                try:
                    if registrar_name:
                        registrar_id = self._get_or_create_registrar(cursor, conn, registrar_name)
                    if name_servers:
                        hoster_name = _normalize_hoster_from_ns(name_servers[0])
                        if hoster_name:
                            hoster_id = self._get_or_create_hoster(cursor, conn, hoster_name)
                except Exception as e:
                    logger.debug(f"Registrar/hoster resolution for {domain_name}: {e}")
                cursor.execute(
                    "UPDATE domains SET registrar_id = %s, hoster_id = %s WHERE id = %s",
                    (registrar_id, hoster_id, domain_id)
                )
                conn.commit()
                logger.debug(f"Updated registrar_id={registrar_id}, hoster_id={hoster_id} for {domain_name}")
                return True
        except Exception as e:
            logger.error(f"Error updating registrar/hoster for domain {domain_id}: {e}", exc_info=True)
            return False

    def create_payout_request_with_auto_split(self, user_id: int, wallet: str,
                                             amount: float, amount_units: int,
                                             trigger: str) -> List[int]:
        """
        Create payout request(s) with automatic splitting for large amounts.
        
        If amount > 500k tokens, automatically splits into multiple requests
        of ~500k tokens each to avoid circuit breaker issues.
        
        Returns list of request IDs (single ID for small amounts, multiple for large).
        """
        logger.info("=" * 80)
        logger.info(f"CREATE PAYOUT REQUEST WITH AUTO-SPLIT")
        logger.info("=" * 80)
        logger.info(f"  User ID: {user_id}")
        logger.info(f"  Wallet: {wallet}")
        logger.info(f"  Amount: {amount} tokens ({amount_units} units)")
        logger.info(f"  Trigger: {trigger}")
        
        # Circuit breaker baseline: 1M tokens (MIN_ANOMALY_BASELINE v2.15)
        # Circuit breaker threshold: 5M tokens/hour (baseline * 5x multiplier)
        # We use 500k tokens per chunk to allow ~10 batches/hour (5M total) while staying safe
        MAX_CHUNK_SIZE = 500000.0  # 500k tokens per chunk (aggressive but safe with v2.15 limits)
        MAX_CHUNK_UNITS = int(MAX_CHUNK_SIZE * 100000000)  # Convert to units
        
        logger.info(f"  MAX_CHUNK_SIZE: {MAX_CHUNK_SIZE} tokens ({MAX_CHUNK_UNITS} units)")
        logger.info(f"  Smart contract limits:")
        logger.info(f"    - Individual max: 5M tokens (default, configurable 10K-50M)")
        logger.info(f"    - Batch max: 5M tokens (default, configurable 10K-50M)")
        logger.info(f"    - Hourly max: 5M tokens (default, configurable 100K-50M)")
        logger.info(f"    - Daily max: 50M tokens (default, configurable 1M-500M)")
        
        if amount <= MAX_CHUNK_SIZE:
            # Small withdrawal - create single request
            logger.info(f"  Amount ({amount} tokens) <= MAX_CHUNK_SIZE ({MAX_CHUNK_SIZE} tokens)")
            logger.info(f"  Creating single payout request (no split needed)")
            # Map 'trigger' to 'triggered_by' for DatabasePG
            request_id = self.create_payout_request(user_id, wallet, amount, amount_units, triggered_by=trigger)
            if request_id:
                logger.info(f"  ✓ Created payout request {request_id}")
                logger.info("=" * 80)
                return [request_id]
            else:
                logger.error(f"  ✗ Failed to create payout request")
                logger.info("=" * 80)
                return []
        
        # Large withdrawal - split into chunks
        logger.info(f"  ⚠️  Large withdrawal detected: {amount} tokens > MAX_CHUNK_SIZE ({MAX_CHUNK_SIZE} tokens)")
        logger.info(f"  Auto-splitting into chunks of {MAX_CHUNK_SIZE} tokens")
        
        # Calculate number of chunks needed
        num_chunks = int((amount + MAX_CHUNK_SIZE - 1) // MAX_CHUNK_SIZE)  # Ceiling division
        logger.info(f"  Estimated chunks needed: {num_chunks}")
        
        request_ids = []
        remaining = amount
        remaining_units = amount_units
        chunk_num = 1
        total_created = 0.0
        total_units_created = 0
        
        while remaining > 0:
            logger.info(f"  Processing chunk {chunk_num}...")
            logger.info(f"    Remaining: {remaining} tokens ({remaining_units} units)")
            
            # Calculate chunk size
            chunk_amount = min(remaining, MAX_CHUNK_SIZE)
            chunk_units = int(chunk_amount * 100000000)  # Convert to units
            
            # Ensure we don't have rounding issues on the last chunk
            if remaining <= MAX_CHUNK_SIZE:
                chunk_amount = remaining
                chunk_units = remaining_units
                logger.info(f"    Last chunk - using exact remaining: {chunk_amount} tokens ({chunk_units} units)")
            else:
                logger.info(f"    Regular chunk - using MAX_CHUNK_SIZE: {chunk_amount} tokens ({chunk_units} units)")
            
            # Validate chunk size
            if chunk_amount <= 0:
                logger.error(f"    ✗ Invalid chunk amount: {chunk_amount}")
                break
            if chunk_units <= 0:
                logger.error(f"    ✗ Invalid chunk units: {chunk_units}")
                break
            if chunk_amount > MAX_CHUNK_SIZE:
                logger.warning(f"    ⚠️  Chunk amount ({chunk_amount}) exceeds MAX_CHUNK_SIZE ({MAX_CHUNK_SIZE})")
            
            # Create payout request for this chunk
            # Map 'trigger' to 'triggered_by' for DatabasePG
            logger.info(f"    Creating payout request: amount={chunk_amount}, units={chunk_units}, trigger={trigger}, chunk={chunk_num}")
            
            request_id = self.create_payout_request(
                user_id=user_id,
                wallet=wallet,
                amount=chunk_amount,
                amount_units=chunk_units,
                triggered_by=trigger  # Map trigger to triggered_by
            )
            
            if request_id:
                request_ids.append(request_id)
                total_created += chunk_amount
                total_units_created += chunk_units
                logger.info(f"    ✓ Created payout request {request_id} for chunk {chunk_num}")
                logger.info(f"      Amount: {chunk_amount} tokens ({chunk_units} units)")
            else:
                logger.error(f"    ✗ Failed to create payout request for chunk {chunk_num}")
                logger.error(f"      Amount: {chunk_amount} tokens ({chunk_units} units)")
                # Continue with other chunks even if one fails
            
            remaining -= chunk_amount
            remaining_units -= chunk_units
            chunk_num += 1
            
            # Safety check to prevent infinite loop
            if chunk_num > 1000:
                logger.error(f"    ✗ Safety limit reached: {chunk_num} chunks. Stopping split.")
                break
        
        logger.info(f"  Auto-split complete:")
        logger.info(f"    Original amount: {amount} tokens ({amount_units} units)")
        logger.info(f"    Created requests: {len(request_ids)}")
        logger.info(f"    Total created: {total_created} tokens ({total_units_created} units)")
        logger.info(f"    Remaining: {remaining} tokens ({remaining_units} units)")
        
        if abs(total_created - amount) > 0.01:
            logger.warning(f"    ⚠️  Amount mismatch! Created {total_created} but requested {amount} (diff: {abs(total_created - amount)})")
        
        if len(request_ids) == 0:
            logger.error(f"    ✗ No payout requests were created successfully!")
        
        logger.info("=" * 80)
        return request_ids


# Singleton instance
_db_pg_instance = None


def get_db_pg() -> DatabasePG:
    """Get the PostgreSQL database singleton."""
    global _db_pg_instance
    if _db_pg_instance is None:
        _db_pg_instance = DatabasePG()
    return _db_pg_instance


def is_db_pg_available() -> bool:
    """Check if PostgreSQL database is available."""
    try:
        db = get_db_pg()
        return db.is_available()
    except Exception:
        return False
