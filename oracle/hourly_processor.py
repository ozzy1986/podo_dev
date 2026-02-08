"""
d.onl Oracle - Hourly Reward Processor (v2.0)
Calculates mining rewards every hour and accumulates user balances.
Includes lottery system: 10% of total rewards distributed to 10 random users.
"""

import time
import logging
from collections import defaultdict
from tokenomics.pool import PoolState
from tokenomics.emission import calculate_hourly_emission
from tokenomics.weights import calculate_domain_weight
from tokenomics.constants import TOKEN_UNIT
from database.db import get_db
from oracle.reward_processor import RewardProcessor
from oracle.email_helper import send_warning_email

logger = logging.getLogger(__name__)

# Lottery configuration
LOTTERY_PERCENTAGE = 0.10  # 10% of total rewards
LOTTERY_WINNERS_COUNT = 10  # Number of random users to receive lottery bonus
MIN_USERS_FOR_LOTTERY = 10  # Minimum users required to run lottery

class HourlyProcessor:
    def __init__(self):
        self.db = get_db()
        self.pool = PoolState(self.db)
        self.reward_processor = RewardProcessor(self.db)
        
    def get_current_hour_index(self, force_recheck=False) -> int:
        """
        Calculate current hour index relative to genesis timestamp stored in DB.
        Returns None when we are not yet past genesis or the current hour was already processed.
        
        Args:
            force_recheck: If True, check if pool_state is empty/out of sync and allow reprocessing
        """
        genesis_ts = self.db.get_system_state('genesis_timestamp')
        if genesis_ts is None:
            raise RuntimeError("Genesis timestamp not set! Run deploy_v2.py or set_system_state first.")
        
        now_ms = int(time.time() * 1000)
        elapsed_ms = now_ms - genesis_ts
        
        if elapsed_ms < 0:
            # Before genesis: nothing to process yet
            logger.info(f"Before genesis: now_ms={now_ms}, genesis_ts={genesis_ts}, elapsed={elapsed_ms}")
            return None
        
        current_hour = elapsed_ms // 3600000  # Hours since genesis
        last_processed = self.db.get_system_state('last_processed_hour')
        
        logger.info(f"Hour calculation: now_ms={now_ms}, genesis_ts={genesis_ts}, elapsed_ms={elapsed_ms}, "
                   f"current_hour={current_hour}, last_processed={last_processed}")
        
        # Normalize last_processed
        if last_processed is None:
            last_processed = -1
        
        # Process hour N when current_hour > last_processed
        # This means we've moved into a new hour and should process it
        if current_hour > last_processed:
            logger.info(f"Will process hour {current_hour} (last_processed was {last_processed})")
            return current_hour
        
        # If we're in the same hour (current_hour == last_processed), check if we should reprocess
        # This handles edge cases where the hour was processed but we need to run again
        if current_hour == last_processed:
            if force_recheck:
                # Check if pool_state is empty or out of sync - if so, allow reprocessing
                try:
                    pool_rows = self.db.fetch_pool_state()
                    total_domains = sum(row.get('domain_count', 0) for row in pool_rows)
                    if total_domains == 0:
                        logger.warning(f"Pool state is empty. Allowing reprocess of hour {current_hour}")
                        return current_hour
                except Exception as e:
                    logger.warning(f"Could not check pool state: {e}. Allowing reprocess of hour {current_hour}")
                    return current_hour
            logger.info(f"Hour {current_hour} already processed (last_processed={last_processed})")
            return None
        
        return None

    def run(self, force_recheck=False):
        """
        Main processing loop for hourly rewards.
        Should be called periodically (e.g. every 10 mins).
        
        Args:
            force_recheck: If True, allow reprocessing current hour if pool_state is empty
        """
        target_hour = None
        try:
            logger.info("[HOURLY_PROCESSOR] ========== Starting hourly reward run ==========")
            logger.info(f"[HOURLY_PROCESSOR] Run started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"[HOURLY_PROCESSOR] Force recheck mode: {force_recheck}")
            
            # 1. Determine target hour
            target_hour = self.get_current_hour_index(force_recheck=force_recheck)
            if target_hour is None:
                logger.info("[HOURLY_PROCESSOR] No new hour to process (before genesis or already processed).")
                logger.info("[HOURLY_PROCESSOR] ========== Run skipped (no hour to process) ==========")
                return
            
            logger.info(f"[HOURLY_PROCESSOR] Target hour to process: {target_hour}")
            
            # Check if it's time to process this hour
            # Ideally compare timestamp with genesis + hour * 3600
            # Simplified logic: ensure we don't double process
            # Real implementation needs proper timestamp sync
            
            logger.info(f"Starting reward calculation for hour {target_hour}")
            
            # 2. Sync pool state from domains (ensures we have accurate counts)
            # This handles cases where pool_state might be out of sync
            self.pool.sync_from_domains()
            
            # 3. Update Pool State (Age Tick)
            # R_L *= k for all lengths
            self.pool.tick_hour()
            
            # 4. Calculate W_total
            w_total = self.pool.calculate_total_weight()
            if w_total <= 0:
                logger.warning("Total pool weight is 0. Skipping rewards.")
                self._mark_hour_complete(target_hour)
                return

            # 4. Calculate Emission E(h)
            emission = calculate_hourly_emission(target_hour)
            
            logger.info(f"Hour {target_hour}: Emission {emission:.2f}, W_total {w_total:.2f}")
            
            # 5. Distribute Rewards (Calculate per-domain rewards, then group by user)
            domain_rewards = []  # List of domain reward dicts
            
            # Fetch active miners (returns: id, user_id, sld_length, age_r)
            miners = self.db.get_active_miners()
            
            # Calculate reward per domain
            for miner in miners:
                # Domain weight: W_len(L) * w_age(r)
                # Note: miner['age_r'] is already updated by tick_hour()
                # We calculate weight using current r_factor
                
                # Reconstruct weight: W_len[L] * (1 + B*(1-r))
                from tokenomics.constants import W_LEN, B_FACTOR
                
                l = miner['sld_length']
                if not (1 <= l <= 63):
                    continue
                    
                w_len = W_LEN[l]
                r_factor = miner['age_r']
                w_age = 1.0 + B_FACTOR * (1.0 - r_factor)
                weight = w_len * w_age
                
                # Reward share
                share = weight / w_total
                reward = emission * share
                reward_units = int(reward * TOKEN_UNIT)
                
                # Get domain name for logging
                domain_data = self.db.get_domain_by_id(miner['id'])
                domain_name = domain_data.get('domain', '') if domain_data else ''
                
                # Check if domain is clickable
                is_clickable = bool(miner.get('is_clickable', False))
                
                domain_rewards.append({
                    'domain_id': miner['id'],
                    'domain': domain_name,
                    'user_id': miner['user_id'],
                    'amount': reward,
                    'amount_units': reward_units,
                    'is_clickable': is_clickable,
                    'a_record_points_to_us': miner.get('a_record_points_to_us'),
                    'parking_mode': miner.get('parking_mode') or 'redirect'
                })
            
            # 5.5. Apply lottery deduction (reduce all rewards by 10%)
            logger.info("[HOURLY_PROCESSOR] Calculating lottery pool...")
            lottery_reduction_factor = 1.0 - LOTTERY_PERCENTAGE
            total_lottery_pool = emission * LOTTERY_PERCENTAGE
            total_lottery_pool_units = int(total_lottery_pool * TOKEN_UNIT)
            
            logger.info("=" * 80)
            logger.info(f"[LOTTERY] Lottery pool calculated: {total_lottery_pool:.2f} tokens")
            logger.info(f"[LOTTERY] This is {LOTTERY_PERCENTAGE*100}% of total emission ({emission:.2f} tokens)")
            logger.info(f"[LOTTERY] Will be distributed to {LOTTERY_WINNERS_COUNT} random users")
            logger.info("=" * 80)
            
            # Reduce each domain reward by 10% (lottery)
            logger.info(f"[HOURLY_PROCESSOR] Applying {LOTTERY_PERCENTAGE*100}% lottery deduction to {len(domain_rewards)} domain rewards...")
            for dr in domain_rewards:
                dr['amount'] = dr['amount'] * lottery_reduction_factor
                dr['amount_units'] = int(dr['amount_units'] * lottery_reduction_factor)
            logger.info(f"[HOURLY_PROCESSOR] Lottery deduction applied to all domain rewards")
            
            # 5.6. Apply mutually exclusive bonus/penalty: clickability OR A-record
            logger.info("[HOURLY_PROCESSOR] Applying mutually exclusive clickability/A-record bonuses...")
            from oracle.verifier import get_verifier
            verifier = get_verifier()
            
            A_RECORD_BONUS_FACTOR = 1.05  # +5% bonus
            CLICKABLE_PENALTY_FACTOR = 0.95  # -5% penalty
            SUPER_PARKING_FACTOR = 0.50  # -50% for super parking (non_redirect)
            
            for dr in domain_rewards:
                is_clickable = dr.get('is_clickable', False)
                a_record_points_to_us = dr.get('a_record_points_to_us')
                parking_mode = dr.get('parking_mode') or 'redirect'
                domain_name = dr['domain']
                
                # Conflict detection: both should not be true (mutually exclusive)
                if is_clickable and a_record_points_to_us:
                    logger.warning(f"Conflict detected for domain {domain_name}: both clickable and A-record points to us. Auto-fixing...")
                    # Auto-fix: disable clickability, keep A-record bonus (A-record is more valuable)
                    self.db.update_domain_clickable(dr['domain_id'], False)
                    is_clickable = False
                    logger.info(f"Auto-fixed: disabled clickability for domain {domain_name}, keeping A-record bonus")
                
                # Mutually exclusive reward calculation
                if is_clickable:
                    # Option 1: Clickable domain → -5% penalty
                    dr['amount'] = dr['amount'] * CLICKABLE_PENALTY_FACTOR
                    dr['amount_units'] = int(dr['amount_units'] * CLICKABLE_PENALTY_FACTOR)
                    logger.debug(f"Applied -5% penalty to clickable domain {domain_name}: {dr['amount']:.8f} tokens")
                else:
                    # Option 2: Check A-record for non-clickable domains
                    # Verify A-record if status is unknown or needs recheck
                    if a_record_points_to_us is None:
                        try:
                            points_to_us, resolved_ip = verifier.dns_verifier.verify_a_record_with_consensus(domain_name)
                            if resolved_ip is not None:
                                self.db.update_a_record_status(dr['domain_id'], points_to_us)
                                a_record_points_to_us = points_to_us
                        except Exception as e:
                            logger.error(f"Error verifying A-record for domain {domain_name}: {e}", exc_info=True)
                            a_record_points_to_us = False
                            self.db.update_a_record_status(dr['domain_id'], False)
                    
                    if a_record_points_to_us:
                        if parking_mode == 'non_redirect':
                            # Super parking: -50% (page served on user's domain)
                            dr['amount'] = dr['amount'] * SUPER_PARKING_FACTOR
                            dr['amount_units'] = int(dr['amount_units'] * SUPER_PARKING_FACTOR)
                            logger.info(f"Applied -50% for super parking to domain {domain_name}: {dr['amount']:.8f} tokens")
                        else:
                            # Regular A-record parking: +5% bonus
                            dr['amount'] = dr['amount'] * A_RECORD_BONUS_FACTOR
                            dr['amount_units'] = int(dr['amount_units'] * A_RECORD_BONUS_FACTOR)
                            logger.info(f"Applied +5% bonus to domain {domain_name} (A-record points to our IP): {dr['amount']:.8f} tokens")
                    # If not clickable and A-record doesn't point to us → base rewards (no change)
            
            # 6. Group rewards by user and accumulate using RewardProcessor
            # This will create reward_log entries with status 'accumulated'
            user_domains = defaultdict(list)
            for dr in domain_rewards:
                user_domains[dr['user_id']].append(dr)
            
            processed_users = 0
            for user_id, domains_list in user_domains.items():
                if not domains_list:
                    continue
                
                # Fetch user to get wallet
                user = self.db.get_user_by_id(user_id)
                if not user or not user.get('wallet'):
                    logger.warning(f"User {user_id} has no wallet, skipping rewards")
                    continue
                wallet = user['wallet']
                
                # Use RewardProcessor to accumulate rewards (creates reward_log entries)
                result = self.reward_processor.accumulate_rewards(
                    user_id=user_id,
                    wallet=wallet,
                    domains_rewards=domains_list
                )
                
                if result.get('success'):
                    processed_users += 1
                    total_amt = result.get('total_amount', 0)
                    logger.info(f"[HOURLY_REWARD] User {user_id} ({wallet}): {total_amt:.2f} tokens from {len(domains_list)} domains - SUCCESS")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"[HOURLY_REWARD] User {user_id} ({wallet}): Failed to accumulate rewards - ERROR: {error_msg}")
            
            if processed_users > 0:
                logger.info("=" * 80)
                logger.info(f"[HOURLY_REWARD] Hour {target_hour} reward distribution complete")
                logger.info(f"  Processed users: {processed_users}/{len(user_domains)}")
                logger.info(f"  Domains processed: {len(domain_rewards)}")
                logger.info(f"  Total emission: {emission:.2f} tokens")
                logger.info("=" * 80)
            else:
                logger.warning(f"[HOURLY_REWARD] Hour {target_hour}: No users processed (all failed or no wallets)")
            
            # 6.5. Lottery Distribution: Give 10% pool to 10 random users (1% each)
            logger.info("=" * 80)
            logger.info("[HOURLY_PROCESSOR] Starting lottery distribution phase...")
            logger.info("=" * 80)
            self._distribute_lottery(total_lottery_pool, total_lottery_pool_units)
            logger.info("[HOURLY_PROCESSOR] Lottery distribution phase completed")
            
            # 7. Check Auto-Payout Thresholds
            self._check_auto_payouts()
            
            # 8. Finalize
            self._mark_hour_complete(target_hour)
            logger.info("=" * 80)
            logger.info(f"[HOURLY_PROCESSOR] ✅ Hour {target_hour} processing complete - SUCCESS")
            logger.info(f"[HOURLY_PROCESSOR]   Emission: {emission:.2f} tokens")
            logger.info(f"[HOURLY_PROCESSOR]   Total weight: {w_total:.2f}")
            logger.info(f"[HOURLY_PROCESSOR]   Domains processed: {len(domain_rewards)}")
            logger.info(f"[HOURLY_PROCESSOR]   Users processed: {processed_users}")
            logger.info(f"[HOURLY_PROCESSOR]   Lottery pool: {total_lottery_pool:.2f} tokens")
            logger.info("=" * 80)
            logger.info("[HOURLY_PROCESSOR] ========== Hourly reward run completed successfully ==========")
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"[HOURLY_PROCESSOR] ❌ Hour {target_hour if target_hour is not None else 'UNKNOWN'} processing FAILED")
            logger.error(f"[HOURLY_PROCESSOR]   Error: {e}")
            logger.error(f"[HOURLY_PROCESSOR]   Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.error("=" * 80)
            logger.error("[HOURLY_PROCESSOR] Full error details:", exc_info=True)

    def _distribute_lottery(self, total_pool: float, total_pool_units: int):
        """
        Distribute lottery pool to random users.
        10% of total emission is split equally among 10 random users (1% each).
        
        Args:
            total_pool: Total lottery pool amount (tokens)
            total_pool_units: Total lottery pool amount (smallest units)
        """
        try:
            logger.info("[LOTTERY] ========== Starting lottery distribution ==========")
            logger.info(f"[LOTTERY] Total pool: {total_pool:.2f} tokens ({total_pool_units} units)")
            logger.info(f"[LOTTERY] Expected winners: {LOTTERY_WINNERS_COUNT}")
            logger.info(f"[LOTTERY] Minimum users required: {MIN_USERS_FOR_LOTTERY}")
            
            # Check if we have enough eligible users
            logger.info("[LOTTERY] Checking eligible users with active domains...")
            eligible_count = self.db.count_users_with_active_domains()
            logger.info(f"[LOTTERY] Found {eligible_count} eligible users")
            
            if eligible_count < MIN_USERS_FOR_LOTTERY:
                warning_msg = (
                    f"Lottery skipped: Only {eligible_count} eligible users found.\n"
                    f"Minimum required: {MIN_USERS_FOR_LOTTERY}\n"
                    f"Lottery pool of {total_pool:.2f} tokens was not distributed.\n"
                    f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.warning("=" * 80)
                logger.warning("[LOTTERY] ❌ LOTTERY SKIPPED - NOT ENOUGH ELIGIBLE USERS")
                logger.warning(f"[LOTTERY] {warning_msg}")
                logger.warning("=" * 80)
                
                # Send warning email to admin
                try:
                    send_warning_email(
                        subject="Lottery Distribution Skipped",
                        message=warning_msg
                    )
                    logger.info("[LOTTERY] Warning email sent to admin")
                except Exception as e:
                    logger.error(f"[LOTTERY] Failed to send warning email: {e}")
                return
            
            # Select random winners
            logger.info(f"[LOTTERY] Selecting {LOTTERY_WINNERS_COUNT} random winners...")
            winners = self.db.get_random_users_with_active_domains(LOTTERY_WINNERS_COUNT)
            
            if not winners:
                logger.error("=" * 80)
                logger.error("[LOTTERY] ❌ FAILED TO SELECT LOTTERY WINNERS")
                logger.error("[LOTTERY] get_random_users_with_active_domains returned empty list")
                logger.error("=" * 80)
                return
            
            if len(winners) < LOTTERY_WINNERS_COUNT:
                logger.warning(f"[LOTTERY] Only {len(winners)} winners selected (expected {LOTTERY_WINNERS_COUNT})")
            
            logger.info(f"[LOTTERY] Selected {len(winners)} winners:")
            for i, winner in enumerate(winners, 1):
                logger.info(f"[LOTTERY]   {i}. User ID: {winner.get('id')}, Wallet: {winner.get('wallet')}")
            
            # Calculate reward per winner (1% of total emission each)
            reward_per_winner = total_pool / LOTTERY_WINNERS_COUNT
            reward_per_winner_units = total_pool_units // LOTTERY_WINNERS_COUNT
            
            logger.info("=" * 80)
            logger.info(f"[LOTTERY] Distributing {total_pool:.2f} tokens to {len(winners)} winners")
            logger.info(f"[LOTTERY] Reward per winner: {reward_per_winner:.2f} tokens ({reward_per_winner_units} units)")
            logger.info("=" * 80)
            
            # Distribute to each winner
            logger.info("[LOTTERY] Starting distribution to winners...")
            lottery_winners_processed = 0
            lottery_winners_failed = 0
            
            for idx, winner in enumerate(winners, 1):
                user_id = winner['id']
                wallet = winner['wallet']
                
                logger.info(f"[LOTTERY] Processing winner {idx}/{len(winners)}: User {user_id} ({wallet})")
                
                if not wallet:
                    logger.warning(f"[LOTTERY] ⚠️  Winner user {user_id} has no wallet, skipping")
                    lottery_winners_failed += 1
                    continue
                
                # Create a special lottery reward entry
                # We use NULL domain_id to indicate lottery reward (not tied to any domain)
                try:
                    logger.debug(f"[LOTTERY] Creating reward log for user {user_id}...")
                    log_id = self.db.create_reward_log(
                        domain_id=None,  # NULL = lottery bonus (not tied to any specific domain)
                        amount=reward_per_winner,
                        amount_units=reward_per_winner_units,
                        wallet=wallet,
                        status='accumulated'
                    )
                    
                    if log_id:
                        logger.debug(f"[LOTTERY] Updating balance for user {user_id}...")
                        # Update user's accumulated balance
                        self.db.batch_update_user_balances([(reward_per_winner, reward_per_winner_units, user_id)])
                        lottery_winners_processed += 1
                        logger.info(f"[LOTTERY] ✅ Winner {idx}: User {user_id} ({wallet[:10]}...) - {reward_per_winner:.2f} tokens - SUCCESS (log_id={log_id})")
                    else:
                        logger.error(f"[LOTTERY] ❌ Winner {idx}: User {user_id} ({wallet[:10]}...) - Failed to create reward log - FAILED")
                        lottery_winners_failed += 1
                        
                except Exception as e:
                    logger.error(f"[LOTTERY] ❌ Winner {idx}: User {user_id} ({wallet[:10] if wallet else 'NO_WALLET'}...) - Error: {e}")
                    logger.error(f"[LOTTERY] Full error details:", exc_info=True)
                    lottery_winners_failed += 1
            
            logger.info("=" * 80)
            if lottery_winners_processed > 0:
                logger.info(f"[LOTTERY] ✅ Lottery distribution completed - SUCCESS")
                logger.info(f"[LOTTERY]   Total pool: {total_pool:.2f} tokens")
                logger.info(f"[LOTTERY]   Winners processed: {lottery_winners_processed}/{len(winners)}")
                if lottery_winners_failed > 0:
                    logger.warning(f"[LOTTERY]   Winners failed: {lottery_winners_failed}")
                logger.info(f"[LOTTERY]   Reward per winner: {reward_per_winner:.2f} tokens")
                logger.info(f"[LOTTERY]   Total distributed: {lottery_winners_processed * reward_per_winner:.2f} tokens")
            else:
                logger.error(f"[LOTTERY] ❌ Lottery distribution FAILED - NO WINNERS PROCESSED")
                logger.error(f"[LOTTERY]   Total pool: {total_pool:.2f} tokens")
                logger.error(f"[LOTTERY]   Winners attempted: {len(winners)}")
                logger.error(f"[LOTTERY]   Winners processed: {lottery_winners_processed}")
                logger.error(f"[LOTTERY]   Winners failed: {lottery_winners_failed}")
            logger.info("=" * 80)
            logger.info("[LOTTERY] ========== Lottery distribution finished ==========")
                
        except Exception as e:
            logger.error("=" * 80)
            logger.error("[LOTTERY] ❌ FATAL ERROR in lottery distribution")
            logger.error(f"[LOTTERY] Error: {e}")
            logger.error("=" * 80)
            logger.error(f"[LOTTERY] Full error details:", exc_info=True)

    def _check_auto_payouts(self):
        """Check if any users reached their auto-payout threshold"""
        try:
            users = self.db.get_users_for_auto_payout()
            for user in users:
                self.db.create_payout_request(
                    user_id=user['id'],
                    wallet=user['wallet'],
                    amount=user['accumulated_balance'],
                    amount_units=user['accumulated_units'],
                    trigger='auto_threshold'
                )
            if users:
                logger.info(f"Created {len(users)} auto-payout requests")
        except Exception as e:
            logger.error(f"Error checking auto payouts: {e}")

    def _mark_hour_complete(self, hour: int):
        """Update system state"""
        self.db.set_system_state('last_processed_hour', hour)

def process_hourly_rewards(force_recheck=False):
    """
    Entry point for cron/scheduler
    
    Args:
        force_recheck: If True, check if pool_state is empty and allow reprocessing
    """
    logger.info("=" * 80)
    logger.info("[HOURLY_PROCESSOR] Starting hourly rewards processor")
    logger.info(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Force recheck: {force_recheck}")
    logger.info("=" * 80)
    
    try:
        processor = HourlyProcessor()
        processor.run(force_recheck=force_recheck)
        
        logger.info("=" * 80)
        logger.info("[HOURLY_PROCESSOR] Hourly rewards processor finished")
        logger.info(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
    except Exception as e:
        logger.error("=" * 80)
        logger.error("[HOURLY_PROCESSOR] Fatal error in hourly rewards processor")
        logger.error(f"  Error: {e}")
        logger.error(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.error("=" * 80)
        raise

