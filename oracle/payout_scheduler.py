"""
d.onl Oracle - Payout Scheduler
Processes pending payout requests and broadcasts transactions.
"""

import time
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from database.db import get_db
from oracle.reward_processor import WavesTransactionHandler
from oracle.contract_query_helper import ContractQueryHelper
from tokenomics.constants import MAX_PAYOUT_BATCH_SIZE

logger = logging.getLogger(__name__)

# Admin email for critical alerts
ADMIN_EMAIL = "ozeritski@gmail.com"

class PayoutScheduler:
    def __init__(self):
        self.db = get_db()
        self.tx_handler = WavesTransactionHandler()
        self.query_helper = ContractQueryHelper()
        self._last_alert_times = {}  # Track last alert time for each alert type
        
    def run(self):
        """
        Process pending payout queue.
        Should be called periodically (e.g. every minute).
        """
        try:
            logger.info("=" * 80)
            logger.info("PAYOUT SCHEDULER START")
            logger.info("=" * 80)
            logger.info(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 0. Check system health before processing
            self._check_system_health()
            
            # 0.5. Check hourly distribution capacity before processing
            # This prevents processing hundreds of payouts that would all fail
            rate_limit_status = self.query_helper.get_rate_limit_status()
            if rate_limit_status:
                hourly_remaining = rate_limit_status.get('hourly_remaining', 0) / 100000000  # Convert from units to tokens
                hourly_used = rate_limit_status.get('hourly_used', 0) / 100000000
                CIRCUIT_BREAKER_SAFE_LIMIT = 4000000.0  # 4M tokens (below 5M threshold, with 1M baseline * 5x multiplier)
                
                logger.info(f"Current hourly distribution: {hourly_used:.2f} tokens used, {hourly_remaining:.2f} tokens remaining")
                
                if hourly_remaining <= 0:
                    logger.warning(f"⚠️  Hourly distribution limit reached ({hourly_used:.2f} tokens used). Skipping payouts until next hour.")
                    logger.info("=" * 80)
                    return
                
                # Use the lower of: hourly_remaining or circuit breaker safe limit
                available_capacity = min(hourly_remaining, CIRCUIT_BREAKER_SAFE_LIMIT - hourly_used)
                if available_capacity <= 0:
                    logger.warning(f"⚠️  Circuit breaker safe limit reached. Remaining capacity: {available_capacity:.2f} tokens. Skipping payouts.")
                    logger.info("=" * 80)
                    return
                
                logger.info(f"Available processing capacity this hour: {available_capacity:.2f} tokens (circuit breaker safe limit: {CIRCUIT_BREAKER_SAFE_LIMIT - hourly_used:.2f})")
            else:
                logger.warning("⚠️  Could not query rate limit status. Proceeding with caution...")
                available_capacity = None  # Will process normally but with circuit breaker checks
            
            # 1. Fetch pending payouts
            pending = self.db.get_pending_payouts(limit=100)
            if not pending:
                logger.info("No pending payouts found")
                logger.info("=" * 80)
                return

            logger.info(f"Found {len(pending)} pending payouts")
            total_amount = sum(float(p.get('amount', 0) or 0) for p in pending)
            logger.info(f"Total amount to process: {total_amount:.8f} tokens")
            
            # Filter payouts to fit within available capacity
            if available_capacity is not None and total_amount > available_capacity:
                logger.warning(f"⚠️  Total pending amount ({total_amount:.2f} tokens) exceeds available capacity ({available_capacity:.2f} tokens)")
                logger.info(f"Filtering payouts to fit within hourly capacity...")
                
                filtered_pending = []
                accumulated = 0.0
                skipped_count = 0
                skipped_amount = 0.0
                
                for p in pending:
                    amount = float(p.get('amount', 0) or 0)
                    if accumulated + amount <= available_capacity:
                        filtered_pending.append(p)
                        accumulated += amount
                    else:
                        skipped_count += 1
                        skipped_amount += amount
                        logger.info(f"  ⏸️  Deferring payout ID {p['id']}: {amount:.2f} tokens (would exceed capacity)")
                
                if skipped_count > 0:
                    logger.warning(f"Deferred {skipped_count} payouts ({skipped_amount:.2f} tokens) to next hour due to capacity limits")
                    logger.info(f"Processing {len(filtered_pending)} payouts ({accumulated:.2f} tokens) that fit within capacity")
                
                pending = filtered_pending
                if not pending:
                    logger.info("No payouts can be processed within current hourly capacity. Waiting for next hour.")
                    logger.info("=" * 80)
                    return
            
            for p in pending:
                logger.info(f"  - Payout ID {p['id']}: User {p['user_id']}, Amount: {p['amount']} tokens, Status: {p.get('status', 'unknown')}, Created: {p.get('created_at', 'unknown')}")

            # 2. Process in batches
            for batch in self._chunk_list(pending, MAX_PAYOUT_BATCH_SIZE):
                self._process_batch(batch)
                
                # Wait between batches to respect contract rate limits
                # Contract v2.14 enforces 60s interval
                time.sleep(65)

        except Exception as e:
            logger.error(f"Error in payout scheduler: {e}", exc_info=True)

    def _process_batch(self, batch: List[Dict]):
        """Process a single batch of payouts"""
        try:
            # Mark as processing
            batch_ids = [p['id'] for p in batch]
            for pid in batch_ids:
                self.db.update_payout_status(pid, 'processing')
            
            # Use single or batch payout depending on size
            if len(batch) == 1:
                # Single payout - use payoutSingle
                self._process_single_payout(batch[0])
            else:
                # Multiple payouts - use payoutBatch
                self._process_batch_payout(batch)
                
        except Exception as e:
            logger.error(f"Error processing batch: {e}", exc_info=True)
            self._fail_batch([p['id'] for p in batch], str(e))
    
    def _process_single_payout(self, payout: Dict):
        """Process a single payout using payoutSingle"""
        payout_id = None
        tx_id = None
        
        try:
            # STEP 1: Extract and validate input data
            wallet = payout['wallet']
            from decimal import Decimal
            amount = payout['amount']
            if isinstance(amount, Decimal):
                amount = float(amount)
            amount_units = payout['amount_units']
            payout_id = payout['id']
            user_id = payout['user_id']
            
            logger.info("=" * 80)
            logger.info(f"PROCESSING SINGLE PAYOUT - ID: {payout_id}")
            logger.info("=" * 80)
            logger.info(f"  User ID: {user_id}")
            logger.info(f"  Wallet: {wallet}")
            logger.info(f"  Amount: {amount} tokens ({amount_units} units)")
            logger.info(f"  Status: {payout.get('status', 'unknown')}")
            
            # STEP 2: Validate everything BEFORE executing transaction
            logger.info("  [STEP 1] Validating payout request...")
            
            # Validate user exists and get balance
            user = self.db.get_user_by_id(user_id)
            if not user:
                error_msg = f"User {user_id} not found"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            # Validate wallet
            if not wallet or not wallet.startswith('3P'):
                error_msg = f"Invalid wallet address: {wallet}"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            # Validate amount
            if amount <= 0 or amount_units <= 0:
                error_msg = f"Invalid amount: {amount} tokens ({amount_units} units)"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            # Get and validate balance
            current_balance = float(user.get('accumulated_balance', 0) or 0)
            current_units = int(user.get('accumulated_units', 0) or 0)
            
            logger.info(f"  Current balance: {current_balance} tokens ({current_units} units)")
            logger.info(f"  Requested amount: {amount} tokens ({amount_units} units)")
            
            if current_balance < amount or current_units < amount_units:
                error_msg = f"Insufficient balance: have {current_balance}, need {amount}"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            expected_balance_after = current_balance - amount
            expected_units_after = current_units - amount_units
            
            logger.info(f"  Expected balance after: {expected_balance_after} tokens ({expected_units_after} units)")
            logger.info(f"  ✓ Validation passed")
            
            # STEP 3: Log the payout attempt BEFORE executing transaction
            logger.info("  [STEP 2] Logging payout attempt...")
            logger.info(f"  Attempting to send {amount} tokens ({amount_units} units) to {wallet}")
            logger.info(f"  User balance before: {current_balance} tokens ({current_units} units)")
            logger.info(f"  ✓ Attempt logged")
            
            # STEP 4: Generate batch identifier
            from datetime import datetime
            batch_id_str = datetime.now().strftime('%Y%m%d_%H%M%S') + f"_withdrawal_{payout_id}"
            logger.info(f"  Batch ID: {batch_id_str}")
            
            # STEP 5: Check contract limits and validate amount
            logger.info("  [STEP 2.5] Checking contract limits and amount validation...")
            
            # Query contract limits
            try:
                contract_limits = self.query_helper.get_rate_limit_status()
                if contract_limits:
                    daily_remaining = contract_limits.get('daily_remaining', 0) / 100000000
                    hourly_remaining = contract_limits.get('hourly_remaining', 0) / 100000000
                    daily_used = contract_limits.get('daily_used', 0) / 100000000
                    hourly_used = contract_limits.get('hourly_used', 0) / 100000000
                    can_payout_now = contract_limits.get('can_payout_now', False)
                    interval_wait_ms = contract_limits.get('interval_wait_ms', 0)
                    
                    logger.info(f"  Contract rate limit status:")
                    logger.info(f"    Daily: {daily_used:.2f}M used, {daily_remaining:.2f}M remaining")
                    logger.info(f"    Hourly: {hourly_used:.2f}M used, {hourly_remaining:.2f}M remaining")
                    logger.info(f"    Can payout now: {can_payout_now}")
                    if not can_payout_now:
                        wait_seconds = interval_wait_ms / 1000.0
                        error_msg = f"Payout interval limit not met. Must wait {wait_seconds:.1f} seconds before next payout"
                        logger.warning(f"    ⚠️  {error_msg}")
                        logger.warning(f"    ⚠️  Skipping this payout - will retry on next scheduler run")
                        self._fail_batch([payout_id], error_msg)
                        raise Exception(error_msg)
                    
                    # Check if amount fits within limits
                    if amount > daily_remaining:
                        error_msg = f"Amount ({amount} tokens) exceeds daily remaining limit ({daily_remaining:.2f}M tokens)"
                        logger.error(f"  ✗ {error_msg}")
                        self._fail_batch([payout_id], error_msg)
                        raise Exception(error_msg)
                    
                    if amount > hourly_remaining:
                        error_msg = f"Amount ({amount} tokens) exceeds hourly remaining limit ({hourly_remaining:.2f}M tokens)"
                        logger.error(f"  ✗ {error_msg}")
                        self._fail_batch([payout_id], error_msg)
                        raise Exception(error_msg)
                    
                    logger.info(f"  ✓ Amount fits within contract limits")
                else:
                    logger.warning(f"  ⚠️  Could not query contract limits, proceeding with caution")
            except Exception as e:
                logger.warning(f"  ⚠️  Error querying contract limits: {e}")
                logger.warning(f"  Proceeding anyway, but transaction may fail")
            
            # Note about automatic splitting
            # Large withdrawals are now automatically split when created (max 500k per chunk)
            # So if we see a large amount here, it means splitting didn't happen or this is a legacy request
            # We'll process it anyway and let the contract handle it
            MAX_SAFE_WITHDRAWAL = 500000.0  # 500k tokens per transaction (aggressive but safe with v2.15 limits)
            
            logger.info(f"  Code limits:")
            logger.info(f"    MAX_SAFE_WITHDRAWAL: {MAX_SAFE_WITHDRAWAL} tokens")
            logger.info(f"    Smart contract individual max: 5M tokens (default)")
            logger.info(f"    Smart contract batch max: 5M tokens (default)")
            
            if amount > MAX_SAFE_WITHDRAWAL:
                logger.warning(f"  ⚠️  Large withdrawal detected: {amount} tokens (max safe: {MAX_SAFE_WITHDRAWAL})")
                logger.warning(f"  Note: Large withdrawals should be auto-split when created")
                logger.warning(f"  This may trigger circuit breaker - processing anyway")
                logger.warning(f"  Contract will enforce its own limits (5M individual, 5M batch)")
            else:
                logger.info(f"  ✓ Amount ({amount} tokens) <= MAX_SAFE_WITHDRAWAL ({MAX_SAFE_WITHDRAWAL} tokens)")
            
            # STEP 6: Build transaction
            logger.info("  [STEP 3] Building transaction...")
            logger.info(f"  Checking prerequisites...")
            
            # Pre-flight checks
            if not self.tx_handler.oracle_seed:
                error_msg = "ORACLE_SEED not configured in environment"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            else:
                logger.info(f"  ✓ ORACLE_SEED configured")
            
            if not self.tx_handler.dapp_address or self.tx_handler.dapp_address.startswith("3P_DUMMY"):
                error_msg = f"DAPP_ADDRESS not configured (current: {self.tx_handler.dapp_address})"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            else:
                logger.info(f"  ✓ DAPP_ADDRESS configured: {self.tx_handler.dapp_address}")
            
            logger.info(f"  ✓ Prerequisites check passed")
            logger.info(f"  Building transaction:")
            logger.info(f"    Wallet: {wallet}")
            logger.info(f"    Amount: {amount} tokens ({amount_units} units)")
            logger.info(f"    Batch ID: {batch_id_str}")
            logger.info(f"    Oracle address: {self.tx_handler.oracle_address}")
            logger.info(f"    Node URL: {self.tx_handler.node_url}")
            
            tx = self.tx_handler.build_invoke_script_tx(wallet, batch_id_str, amount_units)
            
            if not tx:
                # Try to get more detailed error information
                error_msg = "Transaction build failed - check logs for details. Common causes: insufficient WAVES for fees, invalid DAPP_ADDRESS, or network connectivity issues"
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Oracle address: {self.tx_handler.oracle_address}")
                logger.error(f"  DApp address: {self.tx_handler.dapp_address}")
                logger.error(f"  Node URL: {self.tx_handler.node_url}")
                
                # Check oracle balance for more context
                try:
                    balance = self._check_oracle_balance()
                    if balance is not None:
                        logger.error(f"  Oracle wallet balance: {balance} WAVES")
                        if balance < 0.01:
                            error_msg += f" (Oracle wallet has insufficient WAVES: {balance} WAVES)"
                            # Send email alert for insufficient WAVES
                            self._send_insufficient_waves_alert(balance, 0.01)
                except:
                    pass
                
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            # Check if tx is an error response
            if isinstance(tx, dict) and 'error' in tx:
                error_code = tx.get('error', 'unknown')
                error_message = tx.get('message', 'Unknown error')
                error_details = tx.get('details', '')
                error_msg = f"Transaction build failed: {error_code} - {error_message}"
                if error_details:
                    error_msg += f" | {error_details}"
                
                # Check for insufficient WAVES balance error (error 112: negative waves balance)
                if error_code == 112 or (isinstance(error_message, str) and 'negative waves balance' in error_message.lower()):
                    logger.error(f"  ✗ INSUFFICIENT WAVES BALANCE ERROR DETECTED")
                    logger.error(f"  Error: {error_message}")
                    # Check current balance and send email alert
                    try:
                        balance = self._check_oracle_balance()
                        if balance is not None:
                            logger.error(f"  Oracle wallet balance: {balance} WAVES")
                            self._send_insufficient_waves_alert(balance, 0.01)
                    except:
                        pass
                
                # Check for circuit breaker error specifically
                if 'Circuit breaker' in error_message or 'circuit breaker' in error_message.lower():
                    CIRCUIT_BREAKER_BASELINE = 1000000.0  # 1M tokens baseline (v2.15)
                    logger.error(f"  ✗ CIRCUIT BREAKER TRIGGERED")
                    logger.error(f"  Error: {error_message}")
                    logger.error(f"  This withdrawal ({amount} tokens) exceeded the circuit breaker threshold")
                    logger.error(f"  Circuit breaker baseline: {CIRCUIT_BREAKER_BASELINE} tokens")
                    logger.error(f"  Maximum safe withdrawal per hour: ~{MAX_SAFE_WITHDRAWAL} tokens")
                    logger.error(f"  Solution: User should split this withdrawal into smaller chunks")
                    logger.error(f"  Recommended: Create multiple withdrawal requests of {MAX_SAFE_WITHDRAWAL} tokens or less")
                    error_msg = f"Circuit breaker triggered: {error_message}. Please split this withdrawal into smaller chunks (recommended: {MAX_SAFE_WITHDRAWAL} tokens or less per request)."
                
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Full error response: {tx}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            logger.info(f"  ✓ Transaction built successfully")
            
            # STEP 7: Broadcast transaction and log tx_id IMMEDIATELY
            logger.info("  [STEP 4] Broadcasting transaction...")
            
            # Check if tx is already an error response
            if isinstance(tx, dict) and 'error' in tx:
                error_code = tx.get('error', 'unknown')
                error_message = tx.get('message', 'Unknown error')
                error_msg = f"Transaction rejected by node: {error_code} - {error_message}"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            tx_id = self.tx_handler.broadcast_transaction(tx)
            
            if not tx_id:
                # Get more context about the failure
                error_msg = "Transaction broadcast failed - check logs for details. Common causes: network timeout, node rejection, or transaction validation failure"
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Transaction object type: {type(tx)}")
                if isinstance(tx, dict):
                    logger.error(f"  Transaction keys: {list(tx.keys())}")
                    if 'error' in tx:
                        error_code = tx.get('error', 'unknown')
                        error_message = tx.get('message', 'No message')
                        error_details = tx.get('details', '')
                        logger.error(f"  Error in transaction: {error_code} - {error_message}")
                        if error_details:
                            logger.error(f"  Error details: {error_details}")
                        error_msg = f"Transaction broadcast failed: {error_code} - {error_message}"
                        if error_details:
                            error_msg += f" | {error_details}"
                    else:
                        # Log full transaction for debugging
                        logger.error(f"  Full transaction response: {tx}")
                
                # Check oracle balance for more context
                try:
                    balance = self._check_oracle_balance()
                    if balance is not None:
                        logger.error(f"  Oracle wallet balance: {balance} WAVES")
                        if balance < 0.01:
                            error_msg += f" (Oracle wallet has insufficient WAVES: {balance} WAVES)"
                            # Send email alert for insufficient WAVES
                            self._send_insufficient_waves_alert(balance, 0.01)
                except:
                    pass
                
                self._fail_batch([payout_id], error_msg)
                raise Exception(error_msg)
            
            # Log transaction ID immediately after broadcast
            logger.info(f"  ✓ Transaction broadcast successful")
            logger.info(f"  TX ID: {tx_id}")
            logger.info(f"  Amount: {amount} tokens ({amount_units} units)")
            logger.info(f"  Recipient: {wallet}")
            logger.info(f"  Timestamp: {datetime.now().isoformat()}")
            
            # Update payout status with tx_id immediately (even before confirmation)
            # This ensures we have a record of the transaction attempt
            self.db.update_payout_status(payout_id, 'processing', tx_id, None)
            logger.info(f"  ✓ Payout status updated to 'processing' with TX ID")
            
            # STEP 8: Wait for confirmation
            logger.info("  [STEP 5] Waiting for transaction confirmation...")
            confirmed = self.tx_handler.wait_for_confirmation(tx_id)
            
            if not confirmed:
                error_msg = f"Transaction confirmation timeout: {tx_id}"
                logger.error(f"  ✗ {error_msg}")
                self.db.update_payout_status(payout_id, 'failed', tx_id, 'Confirmation timeout')
                raise Exception(error_msg)
            
            logger.info(f"  ✓ Transaction confirmed on blockchain")
            
            # STEP 9: Only NOW deduct balance (after successful confirmation)
            logger.info("  [STEP 6] Deducting balance from user account...")
            logger.info(f"  Balance before: {current_balance} tokens ({current_units} units)")
            
            self.db.deduct_user_balance(user_id, amount, amount_units)
            
            # Verify deduction
            user_after = self.db.get_user_by_id(user_id)
            balance_after = float(user_after.get('accumulated_balance', 0) or 0) if user_after else 0
            units_after = int(user_after.get('accumulated_units', 0) or 0) if user_after else 0
            
            logger.info(f"  Balance after: {balance_after} tokens ({units_after} units)")
            
            if abs(balance_after - expected_balance_after) > 0.00000001:
                logger.error(f"  ⚠️  BALANCE MISMATCH! Expected {expected_balance_after}, got {balance_after}")
            else:
                logger.info(f"  ✓ Balance deduction verified")
            
            # STEP 10: Mark accumulated rewards as confirmed
            logger.info("  [STEP 7] Marking accumulated rewards as confirmed...")
            updated_count = self.db.mark_accumulated_rewards_as_confirmed(user_id, amount, tx_id)
            logger.info(f"  ✓ Updated {updated_count} reward log entries to 'confirmed' status")
            
            # STEP 11: Mark payout as completed
            self.db.update_payout_status(payout_id, 'completed', tx_id, None)
            
            logger.info("=" * 80)
            logger.info(f"WITHDRAWAL SUCCESS - Payout ID: {payout_id}")
            logger.info("=" * 80)
            logger.info(f"  User ID: {user_id}")
            logger.info(f"  Wallet: {wallet}")
            logger.info(f"  Amount: {amount} tokens ({amount_units} units)")
            logger.info(f"  TX ID: {tx_id}")
            logger.info(f"  Status: completed")
            logger.info(f"  Balance before: {current_balance} tokens ({current_units} units)")
            logger.info(f"  Balance after: {balance_after} tokens ({units_after} units)")
            logger.info(f"  Timestamp: {datetime.now().isoformat()}")
            logger.info("=" * 80)
                
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"WITHDRAWAL FAILED - Payout ID: {payout_id or 'unknown'}")
            logger.error("=" * 80)
            logger.error(f"  User ID: {user_id if 'user_id' in locals() else 'unknown'}")
            logger.error(f"  Wallet: {wallet if 'wallet' in locals() else 'unknown'}")
            logger.error(f"  Amount: {amount if 'amount' in locals() else 'unknown'} tokens")
            logger.error(f"  TX ID: {tx_id if tx_id else 'not created'}")
            logger.error(f"  Error: {e}")
            logger.error(f"  Timestamp: {datetime.now().isoformat()}")
            logger.error("=" * 80)
            logger.error(f"Full error details:", exc_info=True)
            
            error_msg = str(e)
            # If we have a tx_id, include it in the error
            if tx_id:
                self.db.update_payout_status(payout_id, 'failed', tx_id, error_msg)
            else:
                self._fail_batch([payout_id], error_msg)
            # Re-raise the exception so caller can catch it
            raise
    
    def _process_batch_payout(self, batch: List[Dict]):
        """Process multiple payouts using payoutBatch"""
        tx_id = None
        batch_ids = []
        
        try:
            from decimal import Decimal
            from datetime import datetime
            
            # STEP 1: Extract and validate input data
            logger.info("=" * 80)
            logger.info(f"PROCESSING BATCH PAYOUT - {len(batch)} recipients")
            logger.info("=" * 80)
            
            # Convert amounts to float and validate
            recipients = []
            amounts = []
            batch_ids = []
            validated_payouts = []
            
            logger.info("  [STEP 1] Validating batch payouts...")
            for p in batch:
                payout_id = p['id']
                user_id = p['user_id']
                wallet = p['wallet']
                amount = p['amount']
                if isinstance(amount, Decimal):
                    amount = float(amount)
                amount_units = p['amount_units']
                
                # Validate each payout
                user = self.db.get_user_by_id(user_id)
                if not user:
                    logger.error(f"  ✗ Payout {payout_id}: User {user_id} not found")
                    self._fail_batch([payout_id], f"User {user_id} not found")
                    continue
                
                if not wallet or not wallet.startswith('3P'):
                    logger.error(f"  ✗ Payout {payout_id}: Invalid wallet {wallet}")
                    self._fail_batch([payout_id], f"Invalid wallet address")
                    continue
                
                current_balance = float(user.get('accumulated_balance', 0) or 0)
                if current_balance < amount:
                    logger.error(f"  ✗ Payout {payout_id}: Insufficient balance (have {current_balance}, need {amount})")
                    self._fail_batch([payout_id], f"Insufficient balance")
                    continue
                
                recipients.append(wallet)
                amounts.append(amount_units)
                batch_ids.append(payout_id)
                validated_payouts.append({
                    'id': payout_id,
                    'user_id': user_id,
                    'wallet': wallet,
                    'amount': amount,
                    'amount_units': amount_units,
                    'balance_before': current_balance
                })
                logger.info(f"  ✓ Payout {payout_id}: {amount} tokens to {wallet}")
            
            if not validated_payouts:
                logger.error("  ✗ No valid payouts in batch")
                return
            
            logger.info(f"  ✓ Validated {len(validated_payouts)} payouts")
            
            # STEP 1.5: Check if batch total exceeds circuit breaker threshold
            logger.info("  [STEP 1.5] Checking batch total against limits...")
            
            # Circuit breaker baseline is 1M tokens (v2.15), so we have much more headroom
            # The circuit breaker triggers if: current_hour_total > (baseline * 5)
            # With 1M baseline and 5x multiplier, threshold = 5M tokens per hour
            # This aligns with the hourly limit, providing protection without being too restrictive
            CIRCUIT_BREAKER_BASELINE = 1000000.0  # 1M tokens (MIN_ANOMALY_BASELINE from contract v2.15)
            CIRCUIT_BREAKER_THRESHOLD = 5000000.0  # 5M tokens (baseline * 5, matches hourly limit)
            MAX_SAFE_BATCH_TOTAL = 500000.0  # 500k tokens max per batch (aggressive but safe with v2.15 limits)
            batch_total_amount = sum(p['amount'] for p in validated_payouts)
            
            logger.info(f"  Batch limits check:")
            logger.info(f"    Batch total: {batch_total_amount} tokens")
            logger.info(f"    MAX_SAFE_BATCH_TOTAL: {MAX_SAFE_BATCH_TOTAL} tokens")
            logger.info(f"    CIRCUIT_BREAKER_BASELINE: {CIRCUIT_BREAKER_BASELINE} tokens")
            logger.info(f"    CIRCUIT_BREAKER_THRESHOLD: {CIRCUIT_BREAKER_THRESHOLD} tokens")
            logger.info(f"    Smart contract batch max: 5M tokens (default)")
            logger.info(f"    Smart contract hourly max: 5M tokens (default)")
            
            # Query contract limits for batch
            try:
                contract_limits = self.query_helper.get_rate_limit_status()
                if contract_limits:
                    hourly_remaining = contract_limits.get('hourly_remaining', 0) / 100000000
                    daily_remaining = contract_limits.get('daily_remaining', 0) / 100000000
                    logger.info(f"    Contract hourly remaining: {hourly_remaining:.2f}M tokens")
                    logger.info(f"    Contract daily remaining: {daily_remaining:.2f}M tokens")
                    
                    if batch_total_amount > hourly_remaining:
                        logger.warning(f"    ⚠️  Batch total ({batch_total_amount} tokens) exceeds hourly remaining ({hourly_remaining:.2f}M tokens)")
                    if batch_total_amount > daily_remaining:
                        logger.warning(f"    ⚠️  Batch total ({batch_total_amount} tokens) exceeds daily remaining ({daily_remaining:.2f}M tokens)")
            except Exception as e:
                logger.warning(f"    ⚠️  Could not query contract limits: {e}")
            
            if batch_total_amount > MAX_SAFE_BATCH_TOTAL:
                logger.warning(f"  ⚠️  Batch total ({batch_total_amount} tokens) exceeds safe limit ({MAX_SAFE_BATCH_TOTAL} tokens)")
                logger.warning(f"  Circuit breaker baseline: {CIRCUIT_BREAKER_BASELINE} tokens")
                logger.warning(f"  Splitting batch into smaller chunks to avoid circuit breaker...")
                
                # Process payouts individually instead of as a batch
                # This ensures each payout stays within safe limits
                logger.info(f"  Processing {len(validated_payouts)} payouts individually to avoid circuit breaker")
                success_count = 0
                fail_count = 0
                
                # Contract requires 10 second interval between payouts (MIN_PAYOUT_INTERVAL v2.15)
                MIN_PAYOUT_INTERVAL_SECONDS = 10
                
                for idx, payout in enumerate(validated_payouts):
                    try:
                        # Wait 10 seconds between payouts (except before first one)
                        if idx > 0:
                            logger.info(f"  Waiting {MIN_PAYOUT_INTERVAL_SECONDS} seconds before next payout (contract requirement)...")
                            time.sleep(MIN_PAYOUT_INTERVAL_SECONDS + 1)  # Add 1 second buffer for safety
                        
                        # Convert back to dict format expected by _process_single_payout
                        payout_dict = {
                            'id': payout['id'],
                            'user_id': payout['user_id'],
                            'wallet': payout['wallet'],
                            'amount': payout['amount'],
                            'amount_units': payout['amount_units'],
                            'status': 'processing'
                        }
                        logger.info(f"  Processing payout {payout['id']} individually: {payout['amount']} tokens")
                        self._process_single_payout(payout_dict)
                        success_count += 1
                    except Exception as e:
                        logger.error(f"  ✗ Failed to process payout {payout['id']} individually: {e}")
                        self._fail_batch([payout['id']], str(e))
                        fail_count += 1
                
                logger.info(f"  Batch split processing complete: {success_count} succeeded, {fail_count} failed")
                return
            
            # STEP 2: Log the batch attempt BEFORE executing transaction
            logger.info("  [STEP 2] Logging batch payout attempt...")
            total_amount = sum(p['amount'] for p in validated_payouts)
            total_units = sum(p['amount_units'] for p in validated_payouts)
            logger.info(f"  Total amount: {total_amount} tokens ({total_units} units)")
            logger.info(f"  Recipients: {len(recipients)}")
            logger.info(f"  ✓ Attempt logged")
            
            # STEP 3: Generate batch identifier
            ts = int(time.time())
            batch_id_str = f"withdrawal_batch_{ts}_{batch_ids[0]}"
            logger.info(f"  Batch ID: {batch_id_str}")
            
            # STEP 4: Build batch transaction
            logger.info("  [STEP 3] Building batch transaction...")
            logger.info(f"  Checking prerequisites...")
            
            # Pre-flight checks
            if not self.tx_handler.oracle_seed:
                error_msg = "ORACLE_SEED not configured in environment"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch(batch_ids, error_msg)
                return
            
            if not self.tx_handler.dapp_address or self.tx_handler.dapp_address.startswith("3P_DUMMY"):
                error_msg = f"DAPP_ADDRESS not configured (current: {self.tx_handler.dapp_address})"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch(batch_ids, error_msg)
                return
            
            logger.info(f"  ✓ Prerequisites check passed")
            logger.info(f"  Building batch transaction: {len(recipients)} recipients, total={total_units} units")
            
            tx = self._build_batch_tx(batch_id_str, recipients, amounts)
            
            if not tx:
                error_msg = "Batch transaction build failed - check logs for details. Common causes: insufficient WAVES for fees, invalid DAPP_ADDRESS, or network connectivity issues"
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Oracle address: {self.tx_handler.oracle_address}")
                logger.error(f"  DApp address: {self.tx_handler.dapp_address}")
                logger.error(f"  Node URL: {self.tx_handler.node_url}")
                self._fail_batch(batch_ids, error_msg)
                return
            
            # Check if tx is an error response
            if isinstance(tx, dict) and 'error' in tx:
                error_code = tx.get('error', 'unknown')
                error_message = tx.get('message', 'Unknown error')
                error_details = tx.get('details', '')
                error_msg = f"Batch transaction build failed: {error_code} - {error_message}"
                if error_details:
                    error_msg += f" | {error_details}"
                
                # Check for insufficient WAVES balance error (error 112: negative waves balance)
                if error_code == 112 or (isinstance(error_message, str) and 'negative waves balance' in error_message.lower()):
                    logger.error(f"  ✗ INSUFFICIENT WAVES BALANCE ERROR DETECTED IN BATCH")
                    logger.error(f"  Error: {error_message}")
                    # Check current balance and send email alert
                    try:
                        balance = self._check_oracle_balance()
                        if balance is not None:
                            logger.error(f"  Oracle wallet balance: {balance} WAVES")
                            self._send_insufficient_waves_alert(balance, 0.01)
                    except:
                        pass
                
                # Check for circuit breaker error specifically
                if 'Circuit breaker' in error_message or 'circuit breaker' in error_message.lower():
                    CIRCUIT_BREAKER_BASELINE = 1000000.0  # 1M tokens baseline (v2.15)
                    logger.error(f"  ✗ CIRCUIT BREAKER TRIGGERED IN BATCH")
                    logger.error(f"  Error: {error_message}")
                    logger.error(f"  Batch total: {total_amount} tokens exceeded circuit breaker threshold")
                    logger.error(f"  Circuit breaker baseline: {CIRCUIT_BREAKER_BASELINE} tokens")
                    logger.error(f"  Attempting to process payouts individually...")
                    
                    # Try processing payouts individually
                    logger.info(f"  Falling back to individual processing for {len(validated_payouts)} payouts")
                    success_count = 0
                    fail_count = 0
                    
                    # Contract requires 60 second interval between payouts (MIN_PAYOUT_INTERVAL)
                    MIN_PAYOUT_INTERVAL_SECONDS = 60
                    
                    for idx, payout in enumerate(validated_payouts):
                        try:
                            # Wait 60 seconds between payouts (except before first one)
                            if idx > 0:
                                logger.info(f"  Waiting {MIN_PAYOUT_INTERVAL_SECONDS} seconds before next payout (contract requirement)...")
                                time.sleep(MIN_PAYOUT_INTERVAL_SECONDS + 1)  # Add 1 second buffer for safety
                            
                            # Convert back to dict format expected by _process_single_payout
                            payout_dict = {
                                'id': payout['id'],
                                'user_id': payout['user_id'],
                                'wallet': payout['wallet'],
                                'amount': payout['amount'],
                                'amount_units': payout['amount_units'],
                                'status': 'processing'
                            }
                            logger.info(f"  Processing payout {payout['id']} individually: {payout['amount']} tokens")
                            self._process_single_payout(payout_dict)
                            success_count += 1
                        except Exception as e:
                            logger.error(f"  ✗ Failed to process payout {payout['id']} individually: {e}")
                            self._fail_batch([payout['id']], str(e))
                            fail_count += 1
                    
                    logger.info(f"  Fallback processing complete: {success_count} succeeded, {fail_count} failed")
                    return
                
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Full error response: {tx}")
                self._fail_batch(batch_ids, error_msg)
                return
            
            logger.info(f"  ✓ Batch transaction built successfully")
            
            # STEP 5: Broadcast transaction and log tx_id IMMEDIATELY
            logger.info("  [STEP 4] Broadcasting batch transaction...")
            
            # Check if tx is already an error response
            if isinstance(tx, dict) and 'error' in tx:
                error_code = tx.get('error', 'unknown')
                error_message = tx.get('message', 'Unknown error')
                error_msg = f"Batch transaction rejected by node: {error_code} - {error_message}"
                logger.error(f"  ✗ {error_msg}")
                self._fail_batch(batch_ids, error_msg)
                return
            
            tx_id = self.tx_handler.broadcast_transaction(tx)
            
            if not tx_id:
                error_msg = "Batch transaction broadcast failed - check logs for details. Common causes: network timeout, node rejection, or transaction validation failure"
                logger.error(f"  ✗ {error_msg}")
                logger.error(f"  Transaction object type: {type(tx)}")
                if isinstance(tx, dict):
                    logger.error(f"  Transaction keys: {list(tx.keys())}")
                    if 'error' in tx:
                        error_code = tx.get('error', 'unknown')
                        error_message = tx.get('message', 'No message')
                        error_details = tx.get('details', '')
                        logger.error(f"  Error in transaction: {error_code} - {error_message}")
                        if error_details:
                            logger.error(f"  Error details: {error_details}")
                        error_msg = f"Batch transaction broadcast failed: {error_code} - {error_message}"
                        if error_details:
                            error_msg += f" | {error_details}"
                    else:
                        # Log full transaction for debugging
                        logger.error(f"  Full transaction response: {tx}")
                
                # Check oracle balance for more context
                try:
                    balance = self._check_oracle_balance()
                    if balance is not None:
                        logger.error(f"  Oracle wallet balance: {balance} WAVES")
                        if balance < 0.01:
                            error_msg += f" (Oracle wallet has insufficient WAVES: {balance} WAVES)"
                            # Send email alert for insufficient WAVES
                            self._send_insufficient_waves_alert(balance, 0.01)
                except:
                    pass
                
                self._fail_batch(batch_ids, error_msg)
                return
            
            logger.info(f"  ✓ Batch transaction broadcast successful")
            logger.info(f"  TX ID: {tx_id}")
            logger.info(f"  Total amount: {total_amount} tokens ({total_units} units)")
            logger.info(f"  Recipients: {len(recipients)}")
            logger.info(f"  Timestamp: {datetime.now().isoformat()}")
            
            # Update all payout statuses with tx_id immediately
            for pid in batch_ids:
                self.db.update_payout_status(pid, 'processing', tx_id, None)
            logger.info(f"  ✓ All payout statuses updated to 'processing' with TX ID")
            
            # STEP 6: Wait for confirmation
            logger.info("  [STEP 5] Waiting for transaction confirmation...")
            confirmed = self.tx_handler.wait_for_confirmation(tx_id)
            
            if not confirmed:
                error_msg = f"Batch transaction confirmation timeout: {tx_id}"
                logger.error(f"  ✗ {error_msg}")
                for pid in batch_ids:
                    self.db.update_payout_status(pid, 'failed', tx_id, 'Confirmation timeout')
                return
            
            logger.info(f"  ✓ Batch transaction confirmed on blockchain")
            
            # STEP 7: Only NOW deduct balances (after successful confirmation)
            logger.info(f"  [STEP 6] Deducting balances for {len(validated_payouts)} users...")
            for p in validated_payouts:
                user_id = p['user_id']
                amount = p['amount']
                amount_units = p['amount_units']
                balance_before = p['balance_before']
                
                logger.info(f"  User {user_id}: Deducting {amount} tokens (balance before: {balance_before})")
                self.db.deduct_user_balance(user_id, amount, amount_units)
                
                # Verify deduction
                user_after = self.db.get_user_by_id(user_id)
                balance_after = float(user_after.get('accumulated_balance', 0) or 0) if user_after else 0
                expected_after = balance_before - amount
                
                if abs(balance_after - expected_after) > 0.00000001:
                    logger.error(f"  ⚠️  BALANCE MISMATCH for user {user_id}! Expected {expected_after}, got {balance_after}")
                else:
                    logger.info(f"  ✓ User {user_id} balance verified")
                
                # Mark accumulated rewards as confirmed
                updated_count = self.db.mark_accumulated_rewards_as_confirmed(user_id, amount, tx_id)
                logger.info(f"  ✓ User {user_id}: {updated_count} reward entries marked as confirmed")
            
            # STEP 8: Mark all payouts as completed
            for pid in batch_ids:
                self.db.update_payout_status(pid, 'completed', tx_id, None)
            
            logger.info(f"✓ Batch payout completed successfully")
            logger.info(f"  TX ID: {tx_id}")
            logger.info(f"  Total amount: {total_amount} tokens")
            logger.info(f"  Recipients: {len(recipients)}")
            logger.info("=" * 80)
                
        except Exception as e:
            logger.error(f"Error processing batch payout: {e}", exc_info=True)
            error_msg = str(e)
            if tx_id:
                for pid in batch_ids:
                    self.db.update_payout_status(pid, 'failed', tx_id, error_msg)
            else:
                self._fail_batch([p['id'] for p in batch], error_msg)

    def _fail_batch(self, batch_ids: List[int], error: str):
        """Mark batch as failed"""
        for pid in batch_ids:
            self.db.update_payout_status(pid, 'failed', error=error)

    def _check_system_health(self):
        """Check system health before processing payouts"""
        logger.info("Checking system health...")
        
        # Check oracle seed
        if not self.tx_handler.oracle_seed:
            logger.error("✗ ORACLE_SEED not configured!")
            logger.error("  This will cause all transactions to fail.")
            logger.error("  Set ORACLE_SEED in .env file or environment variables")
        else:
            logger.info("✓ ORACLE_SEED configured")
        
        # Check DAPP address
        if not self.tx_handler.dapp_address or self.tx_handler.dapp_address.startswith("3P_DUMMY"):
            logger.error(f"✗ DAPP_ADDRESS not configured (current: {self.tx_handler.dapp_address})")
            logger.error("  This will cause all transactions to fail.")
            logger.error("  Set DAPP_ADDRESS in .env file or environment variables")
        else:
            logger.info(f"✓ DAPP_ADDRESS configured: {self.tx_handler.dapp_address}")
        
        # Check node URL
        if not self.tx_handler.node_url:
            logger.error("✗ WAVES_NODE_URL not configured!")
        else:
            logger.info(f"✓ WAVES_NODE_URL configured: {self.tx_handler.node_url}")
        
        # Check oracle wallet balance
        try:
            balance = self._check_oracle_balance()
            if balance is not None:
                # Need at least 0.01 WAVES for fees (900k wavelets per transaction)
                min_required = 0.01
                critical_threshold = 1.0  # Warn when balance drops below 1 WAVES
                
                if balance < min_required:
                    logger.error(f"✗ Oracle wallet has insufficient WAVES balance: {balance} WAVES")
                    logger.error(f"  Minimum required: {min_required} WAVES (for transaction fees)")
                    logger.error("  Please add WAVES to the oracle wallet to process payouts")
                    # Send email alert for insufficient balance
                    self._send_insufficient_waves_alert(balance, min_required)
                elif balance < critical_threshold:
                    logger.warning(f"⚠️  Oracle wallet balance is critically low: {balance} WAVES")
                    logger.warning(f"  Balance is below critical threshold ({critical_threshold} WAVES)")
                    logger.warning("  Please add WAVES to the oracle wallet soon")
                    # Send email alert for low balance
                    self._send_low_waves_alert(balance, critical_threshold)
                else:
                    logger.info(f"✓ Oracle wallet balance: {balance} WAVES (sufficient for fees)")
        except Exception as e:
            logger.warning(f"Could not check oracle wallet balance: {e}")
            logger.warning("  This may indicate network connectivity issues")
        
        logger.info("System health check complete")
    
    def _check_oracle_balance(self) -> float:
        """Check oracle wallet WAVES balance"""
        try:
            import pywaves as pw
            import requests
            
            if not self.tx_handler.oracle_seed:
                return None
            
            # Create oracle address from seed
            oracle = pw.Address(seed=self.tx_handler.oracle_seed)
            oracle_address = oracle.address
            
            # Query balance from node
            url = f"{self.tx_handler.node_url}/addresses/balance/{oracle_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                balance_wavelets = data.get('balance', 0)
                balance_waves = balance_wavelets / 100000000  # Convert wavelets to WAVES
                return balance_waves
            else:
                logger.warning(f"Failed to get balance: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.debug(f"Error checking oracle balance: {e}")
            return None
    
    def _should_send_alert(self, alert_type: str, cooldown_hours: int = 1) -> bool:
        """Check if we should send an alert (prevent spam by using cooldown)."""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o777, exist_ok=True)
            
            alert_file = os.path.join(log_dir, f'alert_{alert_type}.timestamp')
            
            # Check if file exists and read last sent time
            if os.path.exists(alert_file):
                with open(alert_file, 'r') as f:
                    last_sent_str = f.read().strip()
                    try:
                        last_sent = datetime.fromisoformat(last_sent_str)
                        time_since_last = datetime.now() - last_sent
                        if time_since_last < timedelta(hours=cooldown_hours):
                            logger.debug(f"Alert {alert_type} was sent {time_since_last} ago, skipping (cooldown: {cooldown_hours}h)")
                            return False
                    except ValueError:
                        # Invalid timestamp, send alert
                        pass
            
            # Update timestamp
            with open(alert_file, 'w') as f:
                f.write(datetime.now().isoformat())
            
            return True
        except Exception as e:
            logger.error(f"Error checking alert cooldown: {e}")
            # On error, allow sending (better to send duplicate than miss critical alert)
            return True
    
    def _send_low_waves_alert(self, balance: float, threshold: float):
        """Send email alert when WAVES balance is critically low."""
        if not self._should_send_alert('low_waves', cooldown_hours=1):
            return
        
        try:
            from api.email_service import email_service
            
            subject = "⚠️ d.onl Oracle: WAVES Balance Critically Low"
            message = f"The oracle wallet WAVES balance is critically low: {balance:.8f} WAVES.\n\nThe balance has dropped below the critical threshold of {threshold} WAVES. Please add WAVES to the oracle wallet soon to ensure payout processing continues uninterrupted."
            details = f"Oracle Address: {self.tx_handler.oracle_address}\nCurrent Balance: {balance:.8f} WAVES\nCritical Threshold: {threshold} WAVES\nMinimum Required: 0.01 WAVES (for transaction fees)\n\nEach transaction requires 0.0009 WAVES (900k wavelets) in fees."
            
            success = email_service.send_admin_alert(ADMIN_EMAIL, subject, message, details)
            if success:
                logger.info(f"Low WAVES balance alert sent to {ADMIN_EMAIL}")
            else:
                logger.error(f"Failed to send low WAVES balance alert to {ADMIN_EMAIL}")
        except Exception as e:
            logger.error(f"Error sending low WAVES balance alert: {e}", exc_info=True)
    
    def _send_insufficient_waves_alert(self, balance: float, min_required: float):
        """Send email alert when WAVES balance is insufficient for transactions."""
        if not self._should_send_alert('insufficient_waves', cooldown_hours=1):
            return
        
        try:
            from api.email_service import email_service
            
            subject = "🚨 d.onl Oracle: Insufficient WAVES Balance - Transactions Failing"
            message = f"The oracle wallet has insufficient WAVES balance: {balance:.8f} WAVES.\n\nThis is below the minimum required ({min_required} WAVES) for transaction fees. All payout transactions are currently failing. Please add WAVES to the oracle wallet immediately to restore payout processing."
            details = f"Oracle Address: {self.tx_handler.oracle_address}\nCurrent Balance: {balance:.8f} WAVES\nMinimum Required: {min_required} WAVES\n\nEach transaction requires 0.0009 WAVES (900k wavelets) in fees.\n\nAll payout requests are currently failing with 'negative waves balance' errors."
            
            success = email_service.send_admin_alert(ADMIN_EMAIL, subject, message, details)
            if success:
                logger.info(f"Insufficient WAVES balance alert sent to {ADMIN_EMAIL}")
            else:
                logger.error(f"Failed to send insufficient WAVES balance alert to {ADMIN_EMAIL}")
        except Exception as e:
            logger.error(f"Error sending insufficient WAVES balance alert: {e}", exc_info=True)
    
    def _chunk_list(self, lst, n):
        """Yield successive n-sized chunks from lst"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def _build_batch_tx(self, batch_id: str, recipients: List[str], amounts: List[int]):
        """
        Helper to build batch transaction.
        Should technically be in WavesTransactionHandler.
        """
        # This logic mirrors WavesTransactionHandler._build_tx_pywaves
        # but calls payoutBatch
        try:
            import pywaves as pw
            oracle = pw.Address(seed=self.tx_handler.oracle_seed)
            
            # Use 900000 wavelets fee for smart accounts (same as single payout)
            tx_fee = 900000
            
            logger.info(f"Building batch transaction: batch_id={batch_id}, recipients={len(recipients)}, total_amount={sum(amounts)} units")
            
            tx = oracle.invokeScript(
                self.tx_handler.dapp_address,  # Pass string address
                "payoutBatch",
                [
                    {"type": "string", "value": batch_id},
                    {"type": "list", "value": [{"type": "string", "value": r} for r in recipients]},
                    {"type": "list", "value": [{"type": "integer", "value": a} for a in amounts]}
                ],
                txFee=tx_fee
            )
            
            logger.debug(f"invokeScript returned: {tx}")
            logger.debug(f"Return type: {type(tx)}")
            
            if tx is None:
                logger.error("invokeScript returned None - this usually means:")
                logger.error("  1. Oracle wallet has insufficient WAVES for fees")
                logger.error("  2. DAPP_ADDRESS is invalid or contract not deployed")
                logger.error("  3. Network/node connectivity issue")
                return None
            
            # Check if response contains an error
            if isinstance(tx, dict) and 'error' in tx:
                error_code = tx.get('error')
                error_msg = tx.get('message', 'Unknown error')
                logger.error(f"Batch transaction build failed with error {error_code}: {error_msg}")
                logger.error("The transaction was rejected by the node.")
                return None
            
            # Check if transaction has an ID (indicating successful broadcast)
            if isinstance(tx, dict):
                if 'id' in tx:
                    tx_id = tx['id']
                    logger.info(f"Batch transaction built and broadcast successfully: {tx_id}")
                    return tx
                else:
                    # Transaction dict without ID - might be an error or incomplete response
                    logger.error(f"Batch transaction dict missing 'id' field. Response: {tx}")
                    logger.error("This usually means the broadcast failed silently")
                    return None
            else:
                # Non-dict response - might be a string ID or error
                tx_str = str(tx) if tx else 'None'
                if tx_str and tx_str != 'None' and not tx_str.startswith('{'):
                    logger.warning(f"Batch transaction returned as non-dict: {tx_str}")
                    return None
                else:
                    logger.error(f"Invalid batch transaction response: {tx_str}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error building batch tx: {e}", exc_info=True)
            return None

def run_scheduler():
    scheduler = PayoutScheduler()
    scheduler.run()

