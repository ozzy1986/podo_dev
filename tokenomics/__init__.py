"""
PoDO Tokenomics v2.0
Golden Flow emission model with age bonuses.
"""

from .constants import (
    PHI, ALPHA, TOTAL_SUPPLY, TAU, B_FACTOR, TAU_AGE, 
    K_DECAY, W_LEN, TOKEN_DECIMALS, TOKEN_UNIT,
    MIN_SLD_LENGTH, MAX_SLD_LENGTH, MAX_PAYOUT_BATCH_SIZE
)
from .weights import (
    get_sld_length, calculate_age_factor, 
    get_age_bonus_multiplier, calculate_domain_weight,
    get_domain_age_years
)
from .emission import calculate_hourly_emission, calculate_cumulative_emission, calculate_batch_emission
from .pool import PoolState

__all__ = [
    # Constants
    'PHI', 'ALPHA', 'TOTAL_SUPPLY', 'TAU', 'B_FACTOR', 'TAU_AGE',
    'K_DECAY', 'W_LEN', 'TOKEN_DECIMALS', 'TOKEN_UNIT',
    'MIN_SLD_LENGTH', 'MAX_SLD_LENGTH', 'MAX_PAYOUT_BATCH_SIZE',
    # Weights
    'get_sld_length', 'calculate_age_factor', 
    'get_age_bonus_multiplier', 'calculate_domain_weight',
    'get_domain_age_years',
    # Emission
    'calculate_hourly_emission', 'calculate_cumulative_emission', 'calculate_batch_emission',
    # Pool
    'PoolState'
]

