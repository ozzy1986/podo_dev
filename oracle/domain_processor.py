"""
d.onl Oracle - Domain Verification and Reward Processor
Main oracle loop that runs every 12 hours to:
1. Fetch all mining domains
2. Verify DNS records
3. Calculate rewards based on length
4. Group by wallet and process payouts
"""

import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional
from datetime import datetime

from database.db import get_db
from oracle.verifier import get_verifier
from oracle.reward_processor import create_reward_processor
from tokenomics.weights import get_sld_length
from config import config

logger = logging.getLogger(__name__)


class DomainProcessor:
    """
    Main oracle processor that verifies domains and distributes rewards.
    Implements the workflow described in PROJECT_SUMMARY.md.
    """
    
    def __init__(self):
        """Initialize domain processor"""
        self.db = get_db()
        self.verifier = get_verifier()
        self.reward_processor = create_reward_processor(self.db)
    
    def process_all_domains(self) -> Dict[str, Any]:
        """
        Main processing function: fetch domains, verify, calculate rewards, and pay out.
        
        Returns:
            Dict with processing statistics
        """
        stats = {
            'total_domains': 0,
            'verified_success': 0,
            'verified_failed': 0,
            'rewards_calculated': 0,
            'rewards_processed': 0,
            'errors': []
        }
        
        try:
            logger.info("=" * 60)
            logger.info("Starting Oracle Domain Processing Cycle")
            logger.info("=" * 60)
            
            # Step 1: Fetch all mining domains
            logger.info("Fetching mining domains from database...")
            domains = self.db.get_mining_domains()
            stats['total_domains'] = len(domains)
            
            if not domains:
                logger.info("No mining domains found. Exiting.")
                return stats
            
            logger.info(f"Found {len(domains)} mining domains to process")
            
            # Step 2: Verify each domain and calculate rewards
            verified_domains = []
            user_rewards = defaultdict(lambda: {'user_id': None, 'wallet': None, 'rewards': []})  # user_id -> dict with wallet and rewards
            
            for domain_data in domains:
                domain_id = domain_data['id']
                domain_name = domain_data['domain']
                user_id = domain_data.get('user_id')
                wallet = domain_data.get('wallet')
                expected_nonce = domain_data.get('nonce')
                
                if not wallet:
                    logger.warning(f"Domain {domain_name} has no wallet address, skipping")
                    stats['errors'].append(f"{domain_name}: No wallet address")
                    continue
                
                if not user_id:
                    logger.warning(f"Domain {domain_name} has no user_id, skipping")
                    stats['errors'].append(f"{domain_name}: No user_id")
                    continue
                
                logger.info(f"Processing domain: {domain_name} (ID: {domain_id})")
                
                # Verify DNS record
                try:
                    verification_result = self.verifier.verify_with_retry(
                        domain_name,
                        wallet,
                        expected_nonce
                    )
                    
                    if verification_result:
                        logger.info(f"✓ DNS verification successful for {domain_name}")
                        stats['verified_success'] += 1
                        
                        # Update domain check timestamp
                        self.db.update_domain_check(domain_id, success=True)
                        
                        # Calculate SLD length if not set
                        if domain_data.get('sld_length') is None:
                            sld_length = get_sld_length(domain_name)
                            # Update database with SLD length
                            try:
                                with self.db.get_cursor() as (cursor, conn):
                                    cursor.execute(
                                        "UPDATE domains SET sld_length = %s WHERE id = %s",
                                        (sld_length, domain_id)
                                    )
                                    conn.commit()
                                domain_data['sld_length'] = sld_length
                                logger.info(f"  Calculated SLD length: {sld_length}")
                            except Exception as e:
                                logger.error(f"  Failed to update SLD length: {e}")
                                # Continue anyway, will use fallback (RewardCalculator handles None)
                        
                        # Calculate reward for this domain
                        reward_result = self.reward_processor.calculate_domain_reward(domain_data)
                        
                        if reward_result.get('should_process'):
                            stats['rewards_calculated'] += 1
                            # Group by user_id instead of wallet
                            if user_rewards[user_id]['user_id'] is None:
                                user_rewards[user_id]['user_id'] = user_id
                                user_rewards[user_id]['wallet'] = wallet
                            user_rewards[user_id]['rewards'].append(reward_result)
                            verified_domains.append(domain_data)
                            logger.info(
                                f"  Calculated reward: {reward_result['amount']:.8f} tokens "
                                f"({reward_result['amount_units']} units)"
                            )
                        else:
                            reason = reward_result.get('error', 'Unknown')
                            logger.info(f"  Skipping reward: {reason}")
                    else:
                        logger.warning(f"✗ DNS verification failed for {domain_name}")
                        stats['verified_failed'] += 1
                        
                        # Update domain check with failure
                        self.db.update_domain_check(domain_id, success=False)
                        
                        # Check if we should disable mining after too many failures
                        failed_checks = domain_data.get('failed_checks', 0) + 1
                        if failed_checks >= config.MAX_FAILED_CHECKS:
                            logger.warning(
                                f"  Domain {domain_name} has {failed_checks} failed checks, "
                                f"disabling mining"
                            )
                            self.db.disable_domain_mining(domain_id)
                
                except Exception as e:
                    logger.error(f"Error processing domain {domain_name}: {e}", exc_info=True)
                    stats['errors'].append(f"{domain_name}: {str(e)}")
                    # Update as failed check
                    self.db.update_domain_check(domain_id, success=False)
            
            # Step 3: Accumulate rewards in database (don't send to blockchain yet)
            logger.info("=" * 60)
            logger.info(f"Accumulating rewards for {len(user_rewards)} users")
            logger.info("=" * 60)
            
            for user_id, user_data in user_rewards.items():
                if not user_data['rewards']:
                    continue
                
                wallet = user_data['wallet']
                domains_rewards = user_data['rewards']
                
                logger.info(f"Processing user {user_id}: {wallet} ({len(domains_rewards)} domains)")
                
                try:
                    # Accumulate rewards in database (don't broadcast transaction)
                    result = self.reward_processor.accumulate_rewards(
                        user_id, wallet, domains_rewards
                    )
                    
                    if result.get('success'):
                        stats['rewards_processed'] += 1
                        logger.info(
                            f"✓ Successfully accumulated rewards: "
                            f"{result['total_amount']:.8f} tokens "
                            f"(will be sent on withdrawal request)"
                        )
                    else:
                        error = result.get('error', 'Unknown error')
                        logger.error(f"✗ Failed to accumulate rewards for {wallet}: {error}")
                        stats['errors'].append(f"User {user_id} ({wallet}): {error}")
                
                except Exception as e:
                    logger.error(
                        f"Error accumulating rewards for user {user_id}: {e}",
                        exc_info=True
                    )
                    stats['errors'].append(f"User {user_id} ({wallet}): {str(e)}")
            
            # Final summary
            logger.info("=" * 60)
            logger.info("Oracle Processing Cycle Complete")
            logger.info(f"  Total domains: {stats['total_domains']}")
            logger.info(f"  Verified successfully: {stats['verified_success']}")
            logger.info(f"  Verified failed: {stats['verified_failed']}")
            logger.info(f"  Rewards calculated: {stats['rewards_calculated']}")
            logger.info(f"  Rewards processed: {stats['rewards_processed']}")
            if stats['errors']:
                logger.warning(f"  Errors: {len(stats['errors'])}")
            logger.info("=" * 60)
            
            return stats
        
        except Exception as e:
            logger.error(f"Fatal error in domain processor: {e}", exc_info=True)
            stats['errors'].append(f"Fatal: {str(e)}")
            return stats


def process_domains():
    """
    Entry point for cron/scheduler.
    This is the main oracle function that should run every 12 hours.
    """
    processor = DomainProcessor()
    return processor.process_all_domains()

