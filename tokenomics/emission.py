"""
PoDO Tokenomics v2.0 - Emission Module
Handles emission curve calculations (Power Law).

Uses exact cumulative method for precise discrete hourly bucket calculations.
"""

from tokenomics.constants import (
    TOTAL_SUPPLY, ALPHA, TAU, HOURS_PER_YEAR
)
from math import pow

def calculate_cumulative_emission(hour: float) -> float:
    """
    Calculate cumulative emission C(h) from genesis to hour h.
    
    Formula: C(h) = S * [1 - (1 + h/(8760*tau))^(1-alpha)]
    
    This is the exact cumulative emission function. The difference between
    C(h+1) and C(h) gives the exact emission for the discrete hourly bucket [h, h+1).
    
    Args:
        hour: Hour index from genesis (can be float for sub-hour precision)
        
    Returns:
        Cumulative emission in tokens from hour 0 to hour h
    """
    if hour < 0:
        return 0.0
    
    x = 1.0 + hour / (HOURS_PER_YEAR * TAU)
    return TOTAL_SUPPLY * (1.0 - pow(x, 1.0 - ALPHA))

def calculate_hourly_emission(hour: int) -> float:
    """
    Calculate exact emission for discrete hourly bucket [h, h+1).
    
    Uses the exact cumulative method: E_hour(h) = C(h+1) - C(h)
    
    This is the preferred method for discrete hourly buckets as it gives
    the mathematically exact amount for the interval, not an approximation.
    
    Args:
        hour: Hour index from genesis (0, 1, 2...)
        
    Returns:
        Exact emission amount in tokens for interval [h, h+1)
    """
    if hour < 0:
        return 0.0
    
    # Exact method: difference of cumulative function
    return calculate_cumulative_emission(hour + 1) - calculate_cumulative_emission(hour)

def calculate_batch_emission(start_hour: int, duration_hours: int) -> float:
    """
    Calculate total emission for a batch of hours using exact cumulative method.
    
    Uses cumulative function: E_batch = C(end_hour) - C(start_hour)
    This is mathematically equivalent to summing individual hourly emissions
    but more efficient and exact.
    
    Args:
        start_hour: Starting hour index
        duration_hours: Number of hours in the batch
        
    Returns:
        Total emission in tokens for the batch
    """
    if duration_hours <= 0:
        return 0.0
    
    if start_hour < 0:
        start_hour = 0
    
    end_hour = start_hour + duration_hours
    
    # Exact method: difference of cumulative function
    return calculate_cumulative_emission(end_hour) - calculate_cumulative_emission(start_hour)

