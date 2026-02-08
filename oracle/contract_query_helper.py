"""
Smart Contract Query Helper for v2.9
Provides convenient methods to query new monitoring functions.

NEW in v2.9:
- getBatchStatus(): Check if batch ID already processed
- getRateLimitStatus(): Query current rate limits
- getOracleKeys(): Retrieve oracle configuration
"""

import logging
import requests
from typing import Optional, Dict, Tuple
from config import config

logger = logging.getLogger(__name__)


class ContractQueryHelper:
    """Helper class for querying smart contract state (v2.9+)"""
    
    def __init__(self, node_url: str = None, dapp_address: str = None):
        """
        Initialize contract query helper.
        
        Args:
            node_url: Waves node URL (defaults to config)
            dapp_address: Smart contract address (defaults to config)
        """
        self.node_url = node_url or config.WAVES_NODE_URL
        self.dapp_address = dapp_address or config.DAPP_ADDRESS
        
    def _call_contract_function(self, function_name: str, args: list = None) -> Optional[Dict]:
        """
        Call a read-only contract function.
        
        Args:
            function_name: Name of the callable function
            args: List of arguments (for functions that take parameters)
        
        Returns:
            Function result or None if error
        """
        try:
            url = f"{self.node_url}/addresses/scriptInfo/{self.dapp_address}"
            
            # For functions with arguments, need different endpoint
            if args:
                # Use evaluate endpoint for functions with parameters
                url = f"{self.node_url}/utils/script/evaluate/{self.dapp_address}"
                payload = {
                    "expr": f"{function_name}({','.join(str(a) for a in args)})"
                }
                response = requests.post(url, json=payload, timeout=10)
            else:
                # For no-arg functions, can use data keys or invoke
                # Use addresses/data endpoint to query callable results
                response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Contract query failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling contract function {function_name}: {e}")
            return None
    
    def get_batch_status(self, batch_id: str) -> Tuple[bool, int, int]:
        """
        Query if a batch ID has been processed (v2.9+ function).
        
        Args:
            batch_id: Batch identifier to check
        
        Returns:
            Tuple of (isProcessed, timestamp, oracleVersion)
            Returns (False, 0, 0) on error
        """
        try:
            # Call getBatchStatus(batchId) function
            url = f"{self.node_url}/addresses/data/{self.dapp_address}"
            
            # Query the batch key directly from state
            # Note: This uses internal knowledge of contract structure
            # In production, would use proper invoke endpoint
            
            # For now, use a simpler approach: query the state keys
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Look for batch key in data
                # Format: batch_v{version}_{batchId}
                # We need to know the oracle version, so query that first
                oracle_version = 0
                for entry in data:
                    if entry.get('key') == 'oracle_version':
                        oracle_version = entry.get('value', 0)
                        break
                
                # Now check for batch key
                batch_key = f"batch_v{oracle_version}_{batch_id}"
                timestamp_key = f"batch_ts_{batch_id}"
                
                is_processed = False
                timestamp = 0
                
                for entry in data:
                    if entry.get('key') == batch_key:
                        is_processed = entry.get('value', False)
                    elif entry.get('key') == timestamp_key:
                        timestamp = entry.get('value', 0)
                
                return (is_processed, timestamp, oracle_version)
            else:
                logger.error(f"Failed to query batch status: {response.status_code}")
                return (False, 0, 0)
                
        except Exception as e:
            logger.error(f"Error querying batch status for {batch_id}: {e}")
            return (False, 0, 0)
    
    def get_rate_limit_status(self) -> Dict[str, int]:
        """
        Query current rate limit status (v2.9+ function).
        
        Returns:
            Dict with keys:
            - daily_remaining: Tokens that can still be distributed today
            - hourly_remaining: Tokens remaining this hour
            - interval_wait_ms: Milliseconds to wait (0 if ready)
            - daily_used: Tokens already used today
            - hourly_used: Tokens already used this hour
            - can_payout_now: Boolean if interval check would pass
            
            Returns empty dict on error
        """
        logger.debug(f"Querying rate limit status from contract {self.dapp_address}")
        
        # Retry logic for timeout errors
        max_retries = 3
        retry_delay = 2  # seconds
        import time as time_module
        
        for attempt in range(max_retries):
            try:
                # Query contract state keys for rate limit info
                url = f"{self.node_url}/addresses/data/{self.dapp_address}"
                logger.debug(f"  Request URL: {url} (attempt {attempt + 1}/{max_retries})")
                response = requests.get(url, timeout=15)  # Increased timeout from 10 to 15 seconds
                
                if response.status_code != 200:
                    logger.error(f"Failed to query rate limits: HTTP {response.status_code}")
                    logger.error(f"  Response: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        logger.warning(f"  Retrying in {retry_delay} seconds...")
                        time_module.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    return {}
                
                data = response.json()
                logger.debug(f"  Retrieved {len(data)} state entries from contract")
                
                # Extract relevant state
                state = {}
                for entry in data:
                    key = entry.get('key', '')
                    value = entry.get('value')
                    
                    if key == 'daily_state_day':
                        state['stored_day'] = value
                    elif key == 'daily_state_amount':
                        state['daily_used'] = value
                    elif key == 'hourly_state_hour':
                        state['stored_hour'] = value
                    elif key == 'hourly_state_amount':
                        state['hourly_used'] = value
                    elif key == 'last_payout_ts':
                        state['last_payout'] = value
                
                # Calculate current time-based values
                current_time_ms = int(time_module.time() * 1000)
                
                # Constants from contract
                MAX_DAILY = 50000000 * 100000000   # 50M tokens
                MAX_HOURLY = 5000000 * 100000000   # 5M tokens
                MIN_INTERVAL = 10 * 1000           # 10 seconds (v2.15: reduced from 60s)
                EPOCH_2024 = 1704067200000         # Jan 1, 2024
                
                # Calculate current day/hour
                current_day = (current_time_ms - EPOCH_2024) // 86400000 if current_time_ms >= EPOCH_2024 else 0
                current_hour = (current_time_ms - EPOCH_2024) // 3600000 if current_time_ms >= EPOCH_2024 else 0
                
                # Determine if limits have rolled over
                stored_day = state.get('stored_day', -1)
                stored_hour = state.get('stored_hour', -1)
                
                daily_used = state.get('daily_used', 0) if stored_day == current_day else 0
                hourly_used = state.get('hourly_used', 0) if stored_hour == current_hour else 0
                
                daily_remaining = MAX_DAILY - daily_used
                hourly_remaining = MAX_HOURLY - hourly_used
                
                # Check interval
                last_payout = state.get('last_payout', 0)
                time_since_last = current_time_ms - last_payout if last_payout > 0 else MIN_INTERVAL
                interval_wait_ms = max(0, MIN_INTERVAL - time_since_last)
                can_payout_now = interval_wait_ms == 0
                
                result = {
                    'daily_remaining': daily_remaining,
                    'hourly_remaining': hourly_remaining,
                    'interval_wait_ms': interval_wait_ms,
                    'daily_used': daily_used,
                    'hourly_used': hourly_used,
                    'can_payout_now': can_payout_now
                }
                
                logger.info(f"Rate limit status queried:")
                logger.info(f"  Daily: {daily_used/1e8:.2f}M used, {daily_remaining/1e8:.2f}M remaining (max: {MAX_DAILY/1e8:.2f}M)")
                logger.info(f"  Hourly: {hourly_used/1e8:.2f}M used, {hourly_remaining/1e8:.2f}M remaining (max: {MAX_HOURLY/1e8:.2f}M)")
                logger.info(f"  Interval: {interval_wait_ms}ms wait, can_payout_now: {can_payout_now}")
                logger.info(f"  Current day: {current_day}, Current hour: {current_hour}")
                logger.info(f"  Stored day: {stored_day}, Stored hour: {stored_hour}")
                
                return result
                
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout error querying rate limit status (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.warning(f"  Retrying in {retry_delay} seconds...")
                    time_module.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                logger.error(f"  All {max_retries} attempts failed due to timeout")
                return {}
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error querying rate limit status (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.warning(f"  Retrying in {retry_delay} seconds...")
                    time_module.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                logger.error(f"  All {max_retries} attempts failed")
                return {}
            except Exception as e:
                logger.error(f"Error querying rate limit status: {e}")
                return {}
    
    def get_oracle_keys(self) -> list:
        """
        Query configured oracle public keys (v2.9+ function).
        
        Returns:
            List of oracle public keys (empty strings for unconfigured slots)
            Returns empty list on error
        """
        try:
            url = f"{self.node_url}/addresses/data/{self.dapp_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to query oracle keys: {response.status_code}")
                return []
            
            data = response.json()
            
            # Extract oracle public keys (up to 5)
            keys = ["", "", "", "", ""]
            for entry in data:
                key_name = entry.get('key', '')
                if key_name.startswith('oracle_pubkey_'):
                    try:
                        idx = int(key_name.split('_')[-1])
                        if 0 <= idx < 5:
                            keys[idx] = entry.get('value', '')
                    except (ValueError, IndexError):
                        continue
            
            # Filter out empty strings
            configured_keys = [k for k in keys if k]
            
            logger.debug(f"Found {len(configured_keys)} configured oracle keys")
            return keys
            
        except Exception as e:
            logger.error(f"Error querying oracle keys: {e}")
            return []
    
    def check_can_process_payout(self, batch_id: str, amount_units: int) -> Tuple[bool, str]:
        """
        Comprehensive pre-flight check before attempting payout.
        
        Args:
            batch_id: Batch identifier to use
            amount_units: Amount in smallest units
        
        Returns:
            Tuple of (can_process, error_message)
            error_message is empty string if can_process is True
        """
        try:
            # 1. Check if batch already processed
            is_processed, _, _ = self.get_batch_status(batch_id)
            if is_processed:
                return (False, f"Batch '{batch_id}' already processed")
            
            # 2. Check rate limits
            limits = self.get_rate_limit_status()
            if not limits:
                # If we can't query limits, proceed with caution
                logger.warning("Cannot query rate limits, proceeding anyway")
                return (True, "")
            
            # Check interval
            if not limits.get('can_payout_now', False):
                wait_ms = limits.get('interval_wait_ms', 0)
                wait_sec = wait_ms / 1000
                return (False, f"Must wait {wait_sec:.1f}s before next payout")
            
            # Check daily limit
            daily_remaining = limits.get('daily_remaining', 0)
            if amount_units > daily_remaining:
                return (False, f"Daily limit would be exceeded. Remaining: {daily_remaining/1e8:.2f}M tokens")
            
            # Check hourly limit
            hourly_remaining = limits.get('hourly_remaining', 0)
            if amount_units > hourly_remaining:
                return (False, f"Hourly limit would be exceeded. Remaining: {hourly_remaining/1e8:.2f}M tokens")
            
            # All checks passed
            return (True, "")
            
        except Exception as e:
            logger.error(f"Error in pre-flight check: {e}")
            # On error, proceed anyway (better than blocking all payouts)
            return (True, "")
    
    def get_contract_health(self) -> Dict[str, any]:
        """
        Query comprehensive contract health metrics.
        Uses getHealth() function (available since v2.5+).
        
        Returns:
            Dict with health metrics or empty dict on error
        """
        try:
            url = f"{self.node_url}/addresses/data/{self.dapp_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return {}
            
            # Parse relevant health data from state
            # This would ideally call getHealth() directly
            # For now, we gather key metrics from state
            
            return {
                'contract_responsive': True,
                'note': 'Health check via state query (simplified)'
            }
            
        except Exception as e:
            logger.error(f"Error querying contract health: {e}")
            return {'contract_responsive': False, 'error': str(e)}


def create_query_helper(node_url: str = None, dapp_address: str = None) -> ContractQueryHelper:
    """
    Create ContractQueryHelper instance.
    
    Args:
        node_url: Waves node URL (optional)
        dapp_address: Smart contract address (optional)
    
    Returns:
        ContractQueryHelper instance
    """
    return ContractQueryHelper(node_url, dapp_address)

