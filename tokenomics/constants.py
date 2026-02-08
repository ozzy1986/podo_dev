"""
PoDO Tokenomics v2.0 Constants
Based on approved specification.
"""

import math

# ============================================================================
# MATHEMATICAL CONSTANTS
# ============================================================================

# Golden Ratio
PHI = (1 + 5**0.5) / 2  # ~1.6180339887

# Emission Parameter
ALPHA = 6

# Total Supply
TOTAL_SUPPLY = 9_999_999_999

# Tail Calibration
F = 0.90  # 90% minted
T1 = 13.0  # in 13 years
A_PARAM = (1 - F)**(1 / (ALPHA - 1))  # ~0.6309
TAU = T1 * A_PARAM / (1 - A_PARAM)    # ~22.2297 years

# Age Bonus Parameters
B_FACTOR = 0.30  # Max 30% bonus
TAU_AGE = 3.0    # 3 years to reach saturation plateau

# Hourly Age Decay Factor
# r_i = phi^(-age/tau_age)
# r_next = r_prev * k
# k = phi^(-1_hour / tau_age)
HOURS_PER_YEAR = 8760.0
DELTA_A = 1.0 / HOURS_PER_YEAR
K_DECAY = PHI**(-DELTA_A / TAU_AGE)  # ~0.9999817

# ============================================================================
# LENGTH WEIGHTS (Golden Flow)
# ============================================================================

# Base Weight
# W_1 = 610 * alpha = 3660
W_BASE = 610.0 * ALPHA

# Precompute weights for lengths 1..63
# W_len(L) = max(1, W_1 * phi^(-(L-1)))
# Index 0 is unused (or None) for convenience, so index matches Length
W_LEN = [0.0] * 64
for L in range(1, 64):
    weight = W_BASE * (PHI**(-(L - 1)))
    W_LEN[L] = max(1.0, weight)

# ============================================================================
# SYSTEM LIMITS
# ============================================================================

# Token Precision
TOKEN_DECIMALS = 8
TOKEN_UNIT = 10**TOKEN_DECIMALS  # 100,000,000

# Minimum amount to trigger a payout (dust protection)
MIN_PAYOUT_THRESHOLD = 100.0  # User can lower this, but system default
MAX_PAYOUT_BATCH_SIZE = 20    # Per smart contract limit

# Valid SLD length range
MIN_SLD_LENGTH = 1
MAX_SLD_LENGTH = 63

