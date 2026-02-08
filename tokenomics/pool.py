"""
PoDO Tokenomics v2.0 - Pool State
Manages the global state of all domains (N_L, R_L aggregation).
"""

import logging
from typing import List, Dict, Any
from tokenomics.constants import (
    K_DECAY, W_LEN, B_FACTOR, 
    MIN_SLD_LENGTH, MAX_SLD_LENGTH
)

logger = logging.getLogger(__name__)

class PoolState:
    """
    Manages the global state of the mining pool.
    Optimized for 100M+ domains using length-based grouping.
    """
    
    def __init__(self, db):
        """
        Initialize pool state.
        
        Args:
            db: Database connection instance
        """
        self.db = db
        
        # Aggregates by Length (index = Length)
        # N_L: Count of domains with length L
        self.n_l = [0] * 64
        # R_L: Sum of r_i (age factors) for domains with length L
        self.r_l = [0.0] * 64
        
        # Load state from DB
        self._load_state()
        
    def _load_state(self):
        """Load aggregates from database."""
        try:
            # Assuming table pool_state(length_bucket, domain_count, r_sum)
            # If table doesn't exist yet, we start with 0s (will be populated later)
            # In real implementation, migration runs before this
            try:
                rows = self.db.fetch_pool_state()
                for row in rows:
                    l = row['length_bucket']
                    if 1 <= l <= 63:
                        self.n_l[l] = row['domain_count']
                        self.r_l[l] = row['r_sum']
            except Exception:
                # Fallback if DB method not ready yet (dev phase)
                logger.warning("Could not load pool state from DB (table might be missing)")
                
        except Exception as e:
            logger.error(f"Error loading pool state: {e}")

    def save_state(self):
        """Save aggregates to database."""
        try:
            # Batch update or separate updates
            # Ideally db.update_pool_state(self.n_l, self.r_l)
            self.db.save_pool_state(self.n_l, self.r_l)
        except Exception as e:
            logger.error(f"Error saving pool state: {e}")

    def tick_hour(self):
        """
        Advance pool state by one hour.
        Updates age factors for all domains globally (O(1)).
        """
        # R_L *= k for all L
        for l in range(1, 64):
            self.r_l[l] *= K_DECAY
            
        # Update DB immediately
        self.save_state()
        
        # Update individual domains in DB (SQL batch update)
        # UPDATE domains SET age_r = age_r * K
        try:
            self.db.tick_domains_age(K_DECAY)
        except Exception as e:
            logger.error(f"Error processing tick for domains: {e}")

    def add_domain(self, length: int, r_factor: float):
        """
        Register a new domain in the pool.
        
        Args:
            length: SLD length
            r_factor: Initial age factor (phi^-age)
        """
        l = max(MIN_SLD_LENGTH, min(MAX_SLD_LENGTH, int(length)))
        self.n_l[l] += 1
        self.r_l[l] += r_factor
        
        # Note: Caller is responsible for adding to `domains` table

    def remove_domain(self, length: int, r_factor: float):
        """
        Remove a domain from the pool.
        
        Args:
            length: SLD length
            r_factor: Current age factor
        """
        l = max(MIN_SLD_LENGTH, min(MAX_SLD_LENGTH, int(length)))
        if self.n_l[l] > 0:
            self.n_l[l] -= 1
            self.r_l[l] -= r_factor
            
            # Prevent precision drift causing negative R_L
            if self.r_l[l] < 0:
                self.r_l[l] = 0.0

    def sync_from_domains(self):
        """
        Recalculate pool state aggregates from actual domains in database.
        This ensures pool_state is in sync with the domains table.
        """
        try:
            # Ensure pool_state buckets exist (initialize if needed)
            self._ensure_pool_state_buckets()
            
            # Reset aggregates
            self.n_l = [0] * 64
            self.r_l = [0.0] * 64
            
            # Get all active mining domains
            miners = self.db.get_active_miners()
            
            # Recalculate aggregates
            for miner in miners:
                length = miner.get('sld_length')
                age_r = miner.get('age_r', 1.0)
                
                if length is None:
                    logger.warning(f"Domain {miner.get('id')} has no sld_length, skipping")
                    continue
                
                if not (1 <= length <= 63):
                    logger.warning(f"Domain {miner.get('id')} has invalid length {length}, skipping")
                    continue
                
                self.n_l[length] += 1
                self.r_l[length] += float(age_r)
            
            # Save to database
            self.save_state()
            
            total_domains = sum(self.n_l)
            logger.info(f"Synced pool state: {total_domains} active domains across {sum(1 for n in self.n_l if n > 0)} length buckets")
            
        except Exception as e:
            logger.error(f"Error syncing pool state from domains: {e}", exc_info=True)
    
    def _ensure_pool_state_buckets(self):
        """Ensure all pool_state buckets (1-63) exist in the database"""
        try:
            with self.db.get_cursor() as (cursor, conn):
                # Check if any buckets exist
                cursor.execute("SELECT COUNT(*) as cnt FROM pool_state")
                result = cursor.fetchone()
                count = result['cnt'] if isinstance(result, dict) else result[0]
                
                if count == 0:
                    # Initialize all buckets
                    logger.info("Initializing pool_state buckets (1-63)...")
                    values = ','.join([f'({i})' for i in range(1, 64)])
                    cursor.execute(f"INSERT IGNORE INTO pool_state (length_bucket) VALUES {values}")
                    conn.commit()
                    logger.info("Pool state buckets initialized")
        except Exception as e:
            logger.warning(f"Could not ensure pool_state buckets exist: {e}")
            # Continue anyway - save_state will handle it

    def calculate_total_weight(self) -> float:
        """
        Calculate total pool weight W_tot.
        W_tot = Sum( W_len(L) * (N_L * (1+B) - B * R_L) )
        
        Returns:
            Total weight of all domains
        """
        total_weight = 0.0
        
        for l in range(1, 64):
            if self.n_l[l] == 0:
                continue
                
            # Group weight logic:
            # Sum(w_i) = Sum( W_len * (1 + B*(1-r_i)) )
            #          = W_len * [ Sum(1) + B*Sum(1) - B*Sum(r_i) ]
            #          = W_len * [ N_L + B*N_L - B*R_L ]
            #          = W_len * [ N_L*(1+B) - B*R_L ]
            
            group_weight = W_LEN[l] * (self.n_l[l] * (1.0 + B_FACTOR) - B_FACTOR * self.r_l[l])
            
            # Sanity check (weight shouldn't be negative)
            if group_weight < 0:
                group_weight = 0
                
            total_weight += group_weight
            
        return total_weight

