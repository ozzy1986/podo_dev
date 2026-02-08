"""
Oracle Reward Processing Module v2.3 (for Smart Contract v2.9)
Handles reward calculation and Waves transaction processing.

UPDATED FOR SMART CONTRACT v2.9:
- Uses payoutSingle() for single-recipient payouts
- Pre-flight checks using getBatchStatus() and getRateLimitStatus()
- Aggregates multiple domain rewards into single wallet transactions
- Generates proper batch IDs with validation
- Compatible with donl.ride v2.9

NEW in v2.3:
- Integrated ContractQueryHelper for smart pre-flight checks
- Automatic batch ID duplicate detection
- Rate limit validation before transaction broadcast
- Reduced wasted gas from failed transactions
"""

import os
import logging
import time
import json
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import config

# Import new query helper for v2.9
try:
    from oracle.contract_query_helper import create_query_helper
    QUERY_HELPER_AVAILABLE = True
except ImportError:
    QUERY_HELPER_AVAILABLE = False

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# WAVES TRANSACTION HANDLER
# ============================================================================

class WavesTransactionHandler:
    """Handles Waves blockchain transactions"""
    
    def __init__(self):
        """Initialize Waves transaction handler"""
        self.node_url = os.getenv('WAVES_NODE_URL', config.WAVES_NODE_URL)
        self.oracle_seed = os.getenv('ORACLE_SEED', '')
        self.chain_id = config.WAVES_CHAIN_ID
        # Read DAPP_ADDRESS from environment first, then fall back to config
        self.dapp_address = os.getenv('DAPP_ADDRESS', config.DAPP_ADDRESS)
        self.oracle_address = os.getenv('ORACLE_ADDRESS', config.ORACLE_ADDRESS)
        
        if not self.oracle_seed:
            logger.error("ORACLE_SEED not set in environment!")
        
        # Try to import waves_transactions library
        try:
            import pywaves as pw
            pw.setNode(node=self.node_url, chain=self.chain_id)
            self.use_pywaves = True
            logger.info("Using PyWaves library for transactions")
        except ImportError:
            self.use_pywaves = False
            logger.info("PyWaves not available, using direct API calls")
    
    def build_invoke_script_tx(self, wallet: str, domain_or_id: str, amount: int) -> Optional[Dict]:
        """
        Build invokeScript transaction for payoutSingle (v2.1).
        
        Args:
            wallet: Recipient wallet address
            domain_or_id: Domain name OR identifier (e.g. "aggregated_N_domains")
            amount: Reward amount in smallest units
        
        Returns:
            Transaction dict or None if error
        """
        # Check prerequisites
        if not self.oracle_seed:
            logger.error("Cannot build transaction: ORACLE_SEED not set in environment!")
            logger.error("Set it with: export ORACLE_SEED='your seed phrase' or add to .env file")
            return None
        
        if not self.dapp_address or self.dapp_address.startswith("3P_DUMMY"):
            logger.error(f"Cannot build transaction: DAPP_ADDRESS not configured! Current: {self.dapp_address}")
            logger.error("Set it with: export DAPP_ADDRESS='your contract address' or add to .env file")
            return None
        
        if not self.use_pywaves:
            logger.error("Cannot build transaction: PyWaves not installed. Install with: pip install pywaves")
            return self._build_tx_api(wallet, domain_or_id, amount)
        
        logger.debug(f"Prerequisites check passed: ORACLE_SEED={'*' * 20 if self.oracle_seed else 'NOT SET'}, DAPP_ADDRESS={self.dapp_address}")
        return self._build_tx_pywaves(wallet, domain_or_id, amount)
    
    def _build_tx_pywaves(self, wallet: str, domain_or_id: str, amount: int) -> Optional[Dict]:
        """Build transaction using PyWaves library for payoutSingle (v2.1)"""
        try:
            import pywaves as pw
            from datetime import datetime
            
            logger.info(f"Building transaction: wallet={wallet}, amount={amount} units")
            logger.debug(f"Using node: {self.node_url}, chain: {self.chain_id}")
            
            # Create oracle address from seed
            try:
                oracle = pw.Address(seed=self.oracle_seed)
                logger.info(f"Oracle address: {oracle.address}")
            except Exception as e:
                logger.error(f"Failed to create oracle address from seed: {e}")
                logger.error("Check that ORACLE_SEED is a valid Waves seed phrase")
                return None
            
            # Validate dapp address (but pass as string, not Address object)
            try:
                # Validate the address format by creating Address object
                dapp_addr_obj = pw.Address(self.dapp_address)
                logger.debug(f"DApp address validated: {self.dapp_address}")
                # But we'll pass the string address to invokeScript, not the object
                dapp_address_str = self.dapp_address
            except Exception as e:
                logger.error(f"Failed to validate dapp address: {e}")
                logger.error(f"Check that DAPP_ADDRESS is valid: {self.dapp_address}")
                return None
            
            # Generate unique batch ID (8-64 characters as per contract validation)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Include domain/identifier in batch ID for uniqueness and traceability
            batch_id = f"{timestamp}_{domain_or_id}"
            
            # Ensure batch ID is within limits (8-64 chars)
            if len(batch_id) > 64:
                batch_id = batch_id[:64]
            
            logger.info(f"Building payoutSingle tx: batch_id={batch_id}, wallet={wallet}, amount={amount}")
            
            # Build transaction for payoutSingle (v2.1 contract)
            # Note: invokeScript expects string address, not Address object
            try:
                logger.debug(f"Calling oracle.invokeScript with:")
                logger.debug(f"  - dapp_address: {dapp_address_str}")
                logger.debug(f"  - function: payoutSingle")
                logger.debug(f"  - batch_id: {batch_id}")
                logger.debug(f"  - wallet: {wallet}")
                logger.debug(f"  - amount: {amount}")
                
                # Set fee to 900000 wavelets for smart accounts (500000 base + 400000 extra)
                # This is required when the oracle address is a smart account
                tx_fee = 900000
                logger.debug(f"  - fee: {tx_fee} wavelets (0.009 WAVES)")
                
                tx = oracle.invokeScript(
                    dapp_address_str,  # Pass string address, not Address object
                    "payoutSingle",  # Updated function name
                    [
                        {"type": "string", "value": batch_id},    # First arg: batch ID
                        {"type": "string", "value": wallet},      # Second arg: recipient
                        {"type": "integer", "value": amount}      # Third arg: amount
                    ],
                    txFee=tx_fee  # Explicit fee for smart account
                )
                
                logger.debug(f"invokeScript returned: {tx}")
                logger.debug(f"Return type: {type(tx)}")
                
                if tx is None:
                    error_details = (
                        "invokeScript returned None - this usually means:\n"
                        "  1. Oracle wallet has insufficient WAVES for fees\n"
                        "  2. DAPP_ADDRESS is invalid or contract not deployed\n"
                        "  3. Network/node connectivity issue\n"
                        f"  Oracle address: {oracle.address}\n"
                        f"  DApp address: {dapp_address_str}\n"
                        f"  Node URL: {self.node_url}"
                    )
                    logger.error(error_details)
                    # Return a dict with error info so caller can extract it
                    return {'error': 'build_failed', 'message': 'invokeScript returned None', 'details': error_details}
                
                # Check if response contains an error
                if isinstance(tx, dict) and 'error' in tx:
                    error_code = tx.get('error')
                    error_msg = tx.get('message', 'Unknown error')
                    full_error = f"Transaction build failed with error {error_code}: {error_msg}"
                    logger.error(full_error)
                    logger.error("The transaction was rejected by the node.")
                    logger.error(f"  Oracle address: {oracle.address}")
                    logger.error(f"  DApp address: {dapp_address_str}")
                    logger.error(f"  Batch ID: {batch_id}")
                    logger.error(f"  Recipient: {wallet}")
                    logger.error(f"  Amount: {amount} units")
                    # Return the error dict so caller can extract details
                    return tx
                
                # Handle different return types from PyWaves
                # Check if transaction has an ID (indicating successful broadcast)
                if isinstance(tx, dict):
                    if 'id' in tx:
                        tx_id = tx['id']
                        logger.info(f"Transaction built and broadcast successfully: {tx_id}")
                        return tx
                    else:
                        # Transaction dict without ID - might be an error or incomplete response
                        error_details = (
                            f"Transaction dict missing 'id' field. Response: {tx}\n"
                            "This usually means the broadcast failed silently"
                        )
                        logger.error(error_details)
                        logger.error(f"  Oracle address: {oracle.address}")
                        logger.error(f"  DApp address: {dapp_address_str}")
                        logger.error(f"  Batch ID: {batch_id}")
                        logger.error(f"  Recipient: {wallet}")
                        logger.error(f"  Amount: {amount} units")
                        # Return error dict for caller to handle
                        return {'error': 'missing_id', 'message': 'Transaction dict missing id field', 'response': str(tx)}
                elif hasattr(tx, 'get'):
                    tx_id = tx.get('id')
                    if tx_id:
                        logger.info(f"Transaction built successfully (object with get): {tx_id}")
                        return tx
                    else:
                        logger.error(f"Transaction object missing 'id' field: {tx}")
                        return None
                else:
                    # Non-dict response - might be a string ID or error
                    tx_str = str(tx) if tx else 'None'
                    if tx_str and tx_str != 'None' and not tx_str.startswith('{'):
                        logger.warning(f"Transaction returned as non-dict: {tx_str}")
                        # Return None since we can't extract proper transaction info
                        return None
                    else:
                        logger.error(f"Invalid transaction response: {tx_str}")
                        return None
            except Exception as e:
                logger.error(f"PyWaves invokeScript failed with exception: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error details: {str(e)}")
                logger.error("Common issues:")
                logger.error("  - Oracle wallet has insufficient WAVES for fees")
                logger.error("  - Contract address is invalid or not deployed")
                logger.error("  - Network connection issue")
                logger.error("  - Invalid function name or parameters")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return None  # Return None instead of raising to see the actual error
            
        except Exception as e:
            logger.error(f"Error building transaction with PyWaves: {e}", exc_info=True)
            return None
    
    def _build_tx_api(self, wallet: str, domain_or_id: str, amount: int) -> Optional[Dict]:
        """Build transaction using direct API (fallback)"""
        try:
            # This is a simplified version - proper implementation would need
            # waves-transactions library or manual transaction signing
            logger.warning("Direct API transaction building not fully implemented")
            logger.warning("Please install PyWaves: pip install pywaves")
            return None
            
        except Exception as e:
            logger.error(f"Error building transaction with API: {e}")
            return None
    
    def broadcast_transaction(self, tx) -> Optional[str]:
        """
        Broadcast transaction to Waves network with retry logic.
        
        Args:
            tx: Transaction object/dict
        
        Returns:
            Transaction ID or None if failed
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                if self.use_pywaves:
                    # PyWaves invokeScript automatically broadcasts, but we need to check the result
                    if tx is None:
                        error_msg = "Transaction is None - invokeScript may have failed"
                        logger.error(f"Broadcast failed (attempt {attempt + 1}): {error_msg}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        return None
                    
                    # Check if tx is an error response
                    if isinstance(tx, dict):
                        if 'error' in tx:
                            error_code = tx.get('error', 'unknown')
                            error_message = tx.get('message', 'Unknown error')
                            error_msg = f"Transaction rejected: {error_code} - {error_message}"
                            logger.error(f"[TRANSACTION] Broadcast FAILED (attempt {attempt + 1}/{max_retries}): {error_msg}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                                continue
                            return None
                        
                        # Check if transaction has an ID (successful broadcast)
                        if 'id' in tx:
                            tx_id = tx['id']
                            logger.info(f"[TRANSACTION] Broadcast SUCCESS (attempt {attempt + 1}/{max_retries})")
                            logger.info(f"[TRANSACTION] TX ID: {tx_id}")
                            return tx_id
                        else:
                            error_msg = "Transaction dict missing 'id' field - broadcast may have failed"
                            logger.error(f"Broadcast failed (attempt {attempt + 1}): {error_msg}")
                            logger.error(f"Transaction response: {tx}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                                continue
                            return None
                    else:
                        # Try to convert to string as fallback
                        tx_id = str(tx) if tx else None
                        if tx_id and tx_id != 'None':
                            logger.warning(f"Transaction broadcast returned non-dict (attempt {attempt + 1}): {tx_id}")
                            return tx_id
                        else:
                            error_msg = f"Invalid transaction response type: {type(tx)}"
                            logger.error(f"Broadcast failed (attempt {attempt + 1}): {error_msg}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                                continue
                            return None
                else:
                    # Direct API broadcast
                    url = f"{self.node_url}/transactions/broadcast"
                    response = requests.post(url, json=tx, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        tx_id = result.get('id')
                        logger.info(f"[TRANSACTION] Broadcast SUCCESS (attempt {attempt + 1}/{max_retries})")
                        logger.info(f"[TRANSACTION] TX ID: {tx_id}")
                        return tx_id
                    elif response.status_code in [500, 502, 503, 504] and attempt < max_retries - 1:
                        # Server error, retry
                        logger.warning(f"Broadcast attempt {attempt + 1} failed with {response.status_code}, retrying in {retry_delay * (attempt + 1)}s...")
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        logger.error(f"[TRANSACTION] Broadcast FAILED (attempt {attempt + 1}/{max_retries}): HTTP {response.status_code} - {response.text}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return None
                        
            except requests.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(f"Broadcast timeout (attempt {attempt + 1}), retrying in {retry_delay * (attempt + 1)}s...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Broadcast timeout after {max_retries} attempts")
                    return None
            except requests.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error (attempt {attempt + 1}): {e}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Connection error after {max_retries} attempts: {e}")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Broadcast error (attempt {attempt + 1}): {e}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Error broadcasting transaction after {max_retries} attempts: {e}")
                    return None
        
        # Should not reach here, but just in case
        logger.error("Broadcast failed after all retries")
        return None
    
    def wait_for_confirmation(self, tx_id: str, timeout: int = None) -> bool:
        """
        Wait for transaction confirmation.
        
        Args:
            tx_id: Transaction ID
            timeout: Timeout in seconds (defaults to config)
        
        Returns:
            True if confirmed, False if failed or timeout
        """
        if timeout is None:
            timeout = config.WAVES_TX_CONFIRMATION_TIMEOUT
        
        url = f"{self.node_url}/transactions/info/{tx_id}"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    # Transaction found and confirmed
                    logger.info(f"Transaction {tx_id} confirmed")
                    return True
                elif response.status_code == 404:
                    # Transaction not yet in blockchain
                    logger.debug(f"Waiting for confirmation of {tx_id}...")
                    time.sleep(config.WAVES_TX_RETRY_WAIT)
                else:
                    logger.warning(f"Unexpected status {response.status_code} for tx {tx_id}")
                    time.sleep(config.WAVES_TX_RETRY_WAIT)
                    
            except Exception as e:
                logger.error(f"Error checking transaction status: {e}")
                time.sleep(config.WAVES_TX_RETRY_WAIT)
        
        logger.error(f"Transaction {tx_id} confirmation timeout")
        return False
    
    def get_transaction_info(self, tx_id: str) -> Optional[Dict]:
        """
        Get transaction information.
        
        Args:
            tx_id: Transaction ID
        
        Returns:
            Transaction info dict or None
        """
        try:
            url = f"{self.node_url}/transactions/info/{tx_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting transaction info: {e}")
            return None


# ============================================================================
# REWARD CALCULATOR
# ============================================================================

class RewardCalculator:
    """Calculates rewards based on time elapsed and domain SLD length"""
    
    def __init__(self):
        """Initialize reward calculator"""
        self.seconds_per_12h = 12 * 60 * 60  # 43200 seconds
    
    def get_base_reward_for_length(self, sld_length: Optional[int]) -> int:
        """
        Get base reward amount (per 12 hours) for a given SLD length.
        
        Args:
            sld_length: Second-level domain length (1-63)
        
        Returns:
            Base reward amount in smallest units (per 12-hour period)
        """
        if sld_length is None or sld_length < 1:
            # Fallback: use length 5 reward for invalid/missing length
            sld_length = 5
            logger.warning(f"Invalid SLD length, using fallback L=5")
        
        # Use lookup table for L=1-5
        if sld_length in config.REWARD_BY_LENGTH_UNITS:
            return config.REWARD_BY_LENGTH_UNITS[sld_length]
        
        # For L > 5, use exponential decay: R(L) = R(5) * decay_factor^(L-5)
        if sld_length > 5:
            base_reward = config.REWARD_BY_LENGTH_UNITS[5]  # 534 tokens
            decay_factor = config.DECAY_FACTOR
            reward = int(base_reward * (decay_factor ** (sld_length - 5)))
            return max(1, reward)  # Ensure at least 1 unit
        
        # Should not reach here, but fallback to L=5
        logger.warning(f"Unexpected SLD length {sld_length}, using fallback L=5")
        return config.REWARD_BY_LENGTH_UNITS[5]
    
    def calculate_reward(self, last_reward_time: Optional[datetime], 
                        sld_length: Optional[int]) -> int:
        """
        Calculate reward amount based on time since last reward and domain length.
        
        Args:
            last_reward_time: Last reward datetime
            sld_length: Second-level domain length (1-63)
        
        Returns:
            Reward amount in smallest units
        """
        now = datetime.now()
        
        if last_reward_time is None:
            # First reward - give one 12-hour period worth
            time_diff = timedelta(hours=12)
        else:
            time_diff = now - last_reward_time
        
        # Get base reward for this domain length (per 12 hours)
        base_reward = self.get_base_reward_for_length(sld_length)
        
        # Calculate proportional reward based on time elapsed
        seconds_elapsed = time_diff.total_seconds()
        reward = int((seconds_elapsed / self.seconds_per_12h) * base_reward)
        
        # Ensure minimum reward (at least 1% of base reward)
        min_reward = max(1, base_reward // 100)
        if reward < min_reward:
            reward = min_reward
        
        # Ensure maximum reward (safety cap)
        if reward > config.MAX_TOKENS_PER_CLAIM_UNITS:
            logger.warning(f"Calculated reward {reward} exceeds maximum, capping to {config.MAX_TOKENS_PER_CLAIM_UNITS}")
            reward = config.MAX_TOKENS_PER_CLAIM_UNITS
        
        return reward
    
    def format_reward(self, amount_units: int) -> float:
        """
        Format reward amount from units to readable format.
        
        Args:
            amount_units: Amount in smallest units
        
        Returns:
            Amount with decimals
        """
        return amount_units / (10 ** config.TOKEN_DECIMALS)
    
    def should_process_reward(self, last_reward_time: Optional[datetime]) -> bool:
        """
        Check if enough time has passed to process reward.
        
        Args:
            last_reward_time: Last reward datetime
        
        Returns:
            True if should process reward
        """
        if last_reward_time is None:
            return True  # First reward
        
        now = datetime.now()
        time_diff = now - last_reward_time
        min_interval = timedelta(seconds=config.MIN_REWARD_INTERVAL_MS / 1000)
        
        return time_diff >= min_interval


# ============================================================================
# REWARD PROCESSOR
# ============================================================================

class RewardProcessor:
    """
    Main reward processor combining calculation and transaction handling.
    Enhanced for v2.9 with pre-flight checks.
    """
    
    def __init__(self, db):
        """
        Initialize reward processor.
        
        Args:
            db: Database instance
        """
        self.db = db
        self.calculator = RewardCalculator()
        self.tx_handler = WavesTransactionHandler()
        
        # Initialize v2.9 query helper if available
        if QUERY_HELPER_AVAILABLE:
            self.query_helper = create_query_helper()
            logger.info("ContractQueryHelper initialized for v2.9 pre-flight checks")
        else:
            self.query_helper = None
            logger.warning("ContractQueryHelper not available, pre-flight checks disabled")
    
    def calculate_domain_reward(self, domain_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate potential reward for a single domain WITHOUT processing it.
        
        Args:
            domain_data: Domain data dict from database (must include sld_length)
            
        Returns:
            Dict with reward details (amount, amount_units, error)
        """
        result = {
            'domain_id': domain_data['id'],
            'domain': domain_data['domain'],
            'amount': 0,
            'amount_units': 0,
            'error': None,
            'should_process': False
        }
        
        try:
            last_reward = domain_data.get('last_reward')
            sld_length = domain_data.get('sld_length')
            
            # Check if we should process reward
            if not self.calculator.should_process_reward(last_reward):
                result['error'] = 'Minimum interval not reached'
                return result
            
            # Calculate reward amount using domain length
            amount_units = self.calculator.calculate_reward(last_reward, sld_length)
            amount = self.calculator.format_reward(amount_units)
            
            result['amount'] = amount
            result['amount_units'] = amount_units
            result['should_process'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating reward for {domain_data.get('domain', 'unknown')}: {e}")
            result['error'] = str(e)
            return result

    def accumulate_rewards(self, user_id: int, wallet: str, domains_rewards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Accumulate rewards in database without sending to blockchain.
        Rewards will be sent when user requests withdrawal.
        
        Args:
            user_id: User ID
            wallet: Wallet address
            domains_rewards: List of reward dicts (from calculate_domain_reward)
            
        Returns:
            Result dict with success status and details
        """
        result = {
            'success': False,
            'wallet': wallet,
            'user_id': user_id,
            'domains_count': len(domains_rewards),
            'total_amount': 0,
            'total_amount_units': 0,
            'error': None
        }
        
        # Input validation
        if not wallet or not isinstance(wallet, str):
            result['error'] = 'Invalid wallet address: empty or wrong type'
            return result
            
        if not wallet.startswith('3'):
            result['error'] = f'Invalid wallet address format: {wallet} (must start with 3)'
            return result
            
        if not domains_rewards or len(domains_rewards) == 0:
            result['error'] = 'No domains to process'
            return result
        
        try:
            # Calculate totals
            total_units = sum(d['amount_units'] for d in domains_rewards)
            total_amount = sum(d['amount'] for d in domains_rewards)
        except (KeyError, TypeError) as e:
            result['error'] = f'Invalid domain reward data structure: {e}'
            logger.error(f"Data structure error for wallet {wallet}: {e}")
            return result
        
        result['total_amount'] = total_amount
        result['total_amount_units'] = total_units
        
        if total_units == 0:
            result['error'] = "Total reward amount is 0"
            return result
            
        try:
            logger.info("=" * 80)
            logger.info(f"REWARD ACCUMULATION START - User {user_id}, Wallet {wallet}")
            logger.info("=" * 80)
            logger.info(f"  Domains count: {len(domains_rewards)}")
            logger.info(f"  Total amount: {total_amount} {config.TOKEN_NAME} ({total_units} units)")
            
            # Create confirmed reward log entries for tracking
            log_ids_created = []
            log_ids_failed = []
            
            for dr in domains_rewards:
                domain_id = dr.get('domain_id')
                domain_name = dr.get('domain', 'unknown')
                amount = dr.get('amount', 0)
                amount_units = dr.get('amount_units', 0)
                
                logger.debug(f"  Creating reward log: domain_id={domain_id}, domain={domain_name}, amount={amount} tokens ({amount_units} units)")
                
                log_id = self.db.create_reward_log(
                    domain_id=domain_id,
                    amount=amount,
                    amount_units=amount_units,
                    wallet=wallet,
                    status='accumulated'  # New status for accumulated rewards
                )
                
                if log_id:
                    log_ids_created.append(log_id)
                    logger.debug(f"    ✓ Reward log created: log_id={log_id}")
                else:
                    log_ids_failed.append(domain_id)
                    logger.error(f"    ✗ Failed to create reward log for domain {domain_name} (domain_id={domain_id})")
            
            if log_ids_failed:
                error_msg = f"Failed to create {len(log_ids_failed)} reward log entries out of {len(domains_rewards)}"
                logger.error(f"  {error_msg}")
                result['error'] = error_msg
                return result
            
            logger.info(f"  ✓ Reward logs created: {len(log_ids_created)} entries")
            
            # Update user's accumulated balance
            logger.debug(f"  Updating user balance: user_id={user_id}, amount={total_amount} tokens ({total_units} units)")
            try:
                self.db.batch_update_user_balances([(total_amount, total_units, user_id)])
                logger.info(f"  ✓ User balance updated successfully")
            except Exception as e:
                logger.error(f"  ✗ Failed to update user balance: {e}")
                result['error'] = f'Failed to update balance: {str(e)}'
                return result
            
            # Update last_reward timestamp for ALL domains
            domains_updated = 0
            for dr in domains_rewards:
                domain_id = dr.get('domain_id')
                try:
                    self.db.update_last_reward(domain_id)
                    domains_updated += 1
                except Exception as e:
                    logger.warning(f"  ⚠️  Failed to update last_reward for domain_id={domain_id}: {e}")
            
            logger.info(f"  ✓ Last reward timestamps updated: {domains_updated}/{len(domains_rewards)} domains")
            
            result['success'] = True
            logger.info("=" * 80)
            logger.info(f"REWARD ACCUMULATION SUCCESS - User {user_id}, Wallet {wallet}")
            logger.info(f"  Total: {total_amount} {config.TOKEN_NAME} ({total_units} units)")
            logger.info(f"  Reward log entries: {len(log_ids_created)}")
            logger.info(f"  Domains processed: {len(domains_rewards)}")
            logger.info("=" * 80)
            
            return result
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"REWARD ACCUMULATION FAILED - User {user_id}, Wallet {wallet}")
            logger.error(f"  Error: {e}")
            logger.error(f"  Total attempted: {total_amount} {config.TOKEN_NAME} ({total_units} units)")
            logger.error(f"  Domains attempted: {len(domains_rewards)}")
            logger.error("=" * 80)
            logger.error(f"Full error details:", exc_info=True)
            result['error'] = f'Database error: {str(e)}'
            return result

    def process_aggregated_reward(self, wallet: str, domains_rewards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        DEPRECATED: This method sends rewards directly to blockchain.
        Use accumulate_rewards() instead for accumulation mode.
        
        Process a single aggregated reward transaction for a wallet.
        
        Args:
            wallet: Wallet address
            domains_rewards: List of reward dicts (from calculate_domain_reward)
            
        Returns:
            Result dict with success status and details
        """
        result = {
            'success': False,
            'wallet': wallet,
            'domains_count': len(domains_rewards),
            'total_amount': 0,
            'total_amount_units': 0,
            'tx_id': None,
            'error': None
        }
        
        # Input validation
        if not wallet or not isinstance(wallet, str):
            result['error'] = 'Invalid wallet address: empty or wrong type'
            return result
            
        if not wallet.startswith('3'):
            result['error'] = f'Invalid wallet address format: {wallet} (must start with 3)'
            return result
            
        if not domains_rewards or len(domains_rewards) == 0:
            result['error'] = 'No domains to process'
            return result
        
        # Reasonable batch size limit (prevent memory/complexity issues)
        if len(domains_rewards) > 100:
            result['error'] = f'Too many domains in one batch: {len(domains_rewards)} (max 100)'
            logger.error(f"Batch size too large for wallet {wallet}")
            return result
        
        try:
            # Calculate totals with error handling
            total_units = sum(d['amount_units'] for d in domains_rewards)
            total_amount = sum(d['amount'] for d in domains_rewards)
        except (KeyError, TypeError) as e:
            result['error'] = f'Invalid domain reward data structure: {e}'
            logger.error(f"Data structure error for wallet {wallet}: {e}")
            return result
        
        result['total_amount'] = total_amount
        result['total_amount_units'] = total_units
        
        if total_units == 0:
            result['error'] = "Total reward amount is 0"
            return result
        
        # Sanity check on amount (prevent impossibly large values)
        if total_units < 0 or total_units > config.MAX_TOKENS_PER_CLAIM_UNITS * 100:
            result['error'] = f'Invalid total amount: {total_units} units (out of reasonable range)'
            logger.error(f"Suspicious amount for wallet {wallet}: {total_units}")
            return result
            
        try:
            logger.info(f"Processing aggregated reward for {wallet}: {total_amount} {config.TOKEN_NAME} ({len(domains_rewards)} domains)")
            
            # Identifier for batch ID (e.g., "agg_5_domains")
            batch_identifier = f"agg_{len(domains_rewards)}_domains"
            
            # ============================================================
            # V2.9 PRE-FLIGHT CHECKS
            # ============================================================
            if self.query_helper:
                logger.debug(f"Running v2.9 pre-flight checks for batch: {batch_identifier}")
                
                can_process, error_msg = self.query_helper.check_can_process_payout(
                    batch_identifier, 
                    total_units
                )
                
                if not can_process:
                    result['error'] = f"Pre-flight check failed: {error_msg}"
                    logger.warning(f"Skipping payout for {wallet}: {error_msg}")
                    return result
                
                logger.debug(f"Pre-flight checks passed for {wallet}")
            else:
                logger.debug("Skipping pre-flight checks (query helper not available)")
            
            # ============================================================
            # CREATE PENDING LOGS
            # ============================================================
            # Create pending log entries for ALL domains involved
            log_ids = []
            for dr in domains_rewards:
                log_id = self.db.create_reward_log(
                    domain_id=dr['domain_id'],
                    amount=dr['amount'],
                    amount_units=dr['amount_units'],
                    wallet=wallet,
                    status='pending'
                )
                if log_id:
                    log_ids.append(log_id)
                else:
                    logger.error(f"Failed to create reward log for domain {dr['domain']}")
            
            if not log_ids:
                result['error'] = 'Failed to create reward logs'
                return result
            
            # ============================================================
            # BUILD TRANSACTION
            # ============================================================
            # Build ONE transaction for the TOTAL amount
            tx = self.tx_handler.build_invoke_script_tx(wallet, batch_identifier, total_units)
            
            if not tx:
                result['error'] = 'Failed to build transaction'
                for lid in log_ids:
                    self.db.update_reward_status(lid, 'failed', error_message='Transaction build failed')
                return result
            
            # Broadcast transaction
            tx_id = self.tx_handler.broadcast_transaction(tx)
            
            if not tx_id:
                result['error'] = 'Failed to broadcast transaction'
                for lid in log_ids:
                    self.db.update_reward_status(lid, 'failed', error_message='Broadcast failed')
                return result
            
            result['tx_id'] = tx_id
            
            # Wait for confirmation
            confirmed = self.tx_handler.wait_for_confirmation(tx_id)
            
            if confirmed:
                # Update ALL reward logs to confirmed
                for lid in log_ids:
                    self.db.update_reward_status(lid, 'confirmed', txid=tx_id)
                
                # Update last_reward timestamp for ALL domains
                for dr in domains_rewards:
                    self.db.update_last_reward(dr['domain_id'])
                
                result['success'] = True
                logger.info(f"Aggregated reward successful for {wallet}: tx {tx_id}")
            else:
                result['error'] = 'Transaction confirmation timeout'
                for lid in log_ids:
                    self.db.update_reward_status(lid, 'failed', txid=tx_id, 
                                                error_message='Confirmation timeout')
            
            return result
        
        except KeyError as e:
            logger.error(f"Missing required field for wallet {wallet}: {e}")
            result['error'] = f'Data structure error: missing field {e}'
            return result
        except ValueError as e:
            logger.error(f"Invalid value for wallet {wallet}: {e}")
            result['error'] = f'Invalid amount or data: {e}'
            return result
        except TypeError as e:
            logger.error(f"Type error for wallet {wallet}: {e}")
            result['error'] = f'Invalid data type: {e}'
            return result
        except Exception as e:
            logger.error(f"Unexpected error processing aggregated reward for {wallet}: {e}", exc_info=True)
            result['error'] = f'Unexpected error: {str(e)}'
            return result


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

def create_reward_processor(db):
    """Create reward processor instance"""
    return RewardProcessor(db)
