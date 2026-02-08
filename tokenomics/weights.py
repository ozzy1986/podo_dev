"""
PoDO Tokenomics v2.0 - Weights Module
Handles domain length calculation (Unicode) and age bonus logic.
"""

import idna
import datetime
import logging
from typing import Union, Optional
from tokenomics.constants import (
    PHI, B_FACTOR, TAU_AGE, W_LEN, 
    MIN_SLD_LENGTH, MAX_SLD_LENGTH
)

logger = logging.getLogger(__name__)

def get_sld_length(domain: str) -> int:
    """
    Calculate SLD length in Unicode characters (not Punycode).
    
    Args:
        domain: Domain name (e.g., "домен.рф" or "xn--d1acufc.xn--p1ai")
        
    Returns:
        Length clamped to [1, 63].
    """
    if not domain:
        return MAX_SLD_LENGTH  # Fallback for invalid input
        
    try:
        # 1. Convert to Unicode if punycode
        if 'xn--' in domain:
            try:
                domain = idna.decode(domain)
            except idna.IDNAError:
                pass  # Keep as is if decode fails
        
        # 2. Extract SLD (part before the last dot)
        # Handles: "example.com" -> "example", "домен.рф" -> "домен"
        # Also: "sub.example.com" -> "sub.example" (we take everything before TLD)
        parts = domain.rsplit('.', 1)
        if len(parts) > 1:
            sld = parts[0]
        else:
            sld = domain  # No TLD found? Should not happen for valid domains
            
        # 3. Length in Unicode chars
        length = len(sld)
        
        # 4. Clamp
        return max(MIN_SLD_LENGTH, min(MAX_SLD_LENGTH, length))
        
    except Exception as e:
        logger.error(f"Error calculating SLD length for {domain}: {e}")
        return MAX_SLD_LENGTH # Conservative fallback (lowest weight)

def calculate_age_factor(age_years: float) -> float:
    """
    Calculate age decay factor r = phi^(-age/tau_age).
    
    Args:
        age_years: Domain age in years (float)
        
    Returns:
        r value (0 < r <= 1)
    """
    if age_years < 0:
        age_years = 0.0
        
    return PHI ** (-age_years / TAU_AGE)

def get_age_bonus_multiplier(r_factor: float) -> float:
    """
    Calculate final age multiplier w_age = 1 + B * (1 - r).
    
    Args:
        r_factor: Current decay factor phi^(-age/tau)
        
    Returns:
        Multiplier (e.g., 1.0 to 1.30)
    """
    return 1.0 + B_FACTOR * (1.0 - r_factor)

def calculate_domain_weight(length: int, age_years: float) -> float:
    """
    Calculate total domain weight w = W_len(L) * w_age(a).
    
    Args:
        length: SLD length
        age_years: Age in years
        
    Returns:
        Total weight
    """
    L = max(MIN_SLD_LENGTH, min(MAX_SLD_LENGTH, int(length)))
    w_len = W_LEN[L]
    
    r = calculate_age_factor(age_years)
    w_age = get_age_bonus_multiplier(r)
    
    return w_len * w_age

def get_domain_age_years(creation_date: Optional[datetime.datetime]) -> float:
    """
    Calculate age in years from creation date.
    
    Args:
        creation_date: Datetime object
        
    Returns:
        Age in years (float)
    """
    if not creation_date:
        return 0.0
        
    now = datetime.datetime.now()
    if creation_date > now:
        return 0.0  # Future dates?
        
    delta = now - creation_date
    return delta.total_seconds() / (365.25 * 24 * 3600)

