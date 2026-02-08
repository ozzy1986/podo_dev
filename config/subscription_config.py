"""
Subscription frequency configuration and pricing.

Each frequency has:
- minutes: Duration in minutes for calculating next_renewal_at
- price: Cost in DOMAIN tokens per renewal
- display_order: Order in UI dropdown
"""

SUBSCRIPTION_FREQUENCIES = {
    '5min': {
        'minutes': 5,
        'price': 1.0,
        'display_order': 1,
        'label_key': 'freq_5min',
        'label_en': 'Every 5 minutes',
        'label_ru': 'Каждые 5 минут',
        'label_ar': 'كل 5 دقائق'
    },
    '10min': {
        'minutes': 10,
        'price': 1.0,
        'display_order': 2,
        'label_key': 'freq_10min',
        'label_en': 'Every 10 minutes',
        'label_ru': 'Каждые 10 минут',
        'label_ar': 'كل 10 دقائق'
    },
    '15min': {
        'minutes': 15,
        'price': 1.0,
        'display_order': 3,
        'label_key': 'freq_15min',
        'label_en': 'Every 15 minutes',
        'label_ru': 'Каждые 15 минут',
        'label_ar': 'كل 15 دقيقة'
    },
    '1hour': {
        'minutes': 60,
        'price': 1.0,
        'display_order': 4,
        'label_key': 'freq_1hour',
        'label_en': 'Every hour',
        'label_ru': 'Каждый час',
        'label_ar': 'كل ساعة'
    },
    '2hours': {
        'minutes': 120,
        'price': 1.0,
        'display_order': 5,
        'label_key': 'freq_2hours',
        'label_en': 'Every 2 hours',
        'label_ru': 'Каждые 2 часа',
        'label_ar': 'كل ساعتين'
    },
    '3hours': {
        'minutes': 180,
        'price': 1.0,
        'display_order': 6,
        'label_key': 'freq_3hours',
        'label_en': 'Every 3 hours',
        'label_ru': 'Каждые 3 часа',
        'label_ar': 'كل 3 ساعات'
    },
    '5hours': {
        'minutes': 300,
        'price': 1.0,
        'display_order': 7,
        'label_key': 'freq_5hours',
        'label_en': 'Every 5 hours',
        'label_ru': 'Каждые 5 часов',
        'label_ar': 'كل 5 ساعات'
    },
    '7hours': {
        'minutes': 420,
        'price': 1.0,
        'display_order': 8,
        'label_key': 'freq_7hours',
        'label_en': 'Every 7 hours',
        'label_ru': 'Каждые 7 часов',
        'label_ar': 'كل 7 ساعات'
    },
    '10hours': {
        'minutes': 600,
        'price': 1.0,
        'display_order': 9,
        'label_key': 'freq_10hours',
        'label_en': 'Every 10 hours',
        'label_ru': 'Каждые 10 часов',
        'label_ar': 'كل 10 ساعات'
    },
    '24hours': {
        'minutes': 1440,
        'price': 1.0,
        'display_order': 10,
        'label_key': 'freq_24hours',
        'label_en': 'Every 24 hours',
        'label_ru': 'Каждые 24 часа',
        'label_ar': 'كل 24 ساعة'
    },
    '48hours': {
        'minutes': 2880,
        'price': 1.0,
        'display_order': 11,
        'label_key': 'freq_48hours',
        'label_en': 'Every 48 hours',
        'label_ru': 'Каждые 48 часов',
        'label_ar': 'كل 48 ساعة'
    },
    '72hours': {
        'minutes': 4320,
        'price': 1.0,
        'display_order': 12,
        'label_key': 'freq_72hours',
        'label_en': 'Every 72 hours',
        'label_ru': 'Каждые 72 часа',
        'label_ar': 'كل 72 ساعة'
    },
    '1week': {
        'minutes': 10080,
        'price': 1.0,
        'display_order': 13,
        'label_key': 'freq_1week',
        'label_en': 'Every week',
        'label_ru': 'Каждую неделю',
        'label_ar': 'كل أسبوع'
    }
}

# Default frequency if not specified
DEFAULT_FREQUENCY = '1hour'

# Cron job runs every 5 minutes
CRON_INTERVAL_MINUTES = 5


def get_frequency_config(frequency_type: str) -> dict:
    """
    Get configuration for a specific frequency type.
    
    Args:
        frequency_type: Frequency identifier (e.g., '5min', '1hour', '1week')
        
    Returns:
        Dict with frequency configuration or None if invalid
    """
    return SUBSCRIPTION_FREQUENCIES.get(frequency_type)


def is_valid_frequency(frequency_type: str) -> bool:
    """Check if a frequency type is valid."""
    return frequency_type in SUBSCRIPTION_FREQUENCIES


def get_all_frequencies_sorted() -> list:
    """
    Get all frequencies sorted by display_order.
    
    Returns:
        List of tuples: [(frequency_type, config), ...]
    """
    return sorted(
        SUBSCRIPTION_FREQUENCIES.items(),
        key=lambda x: x[1]['display_order']
    )


def calculate_next_renewal(current_time, frequency_type: str):
    """
    Calculate next renewal datetime based on frequency.
    
    Args:
        current_time: datetime object
        frequency_type: Frequency identifier
        
    Returns:
        datetime object for next renewal
    
    Raises:
        ValueError: If frequency_type is invalid and default fails
    """
    from datetime import timedelta
    
    config = get_frequency_config(frequency_type)
    if not config:
        # Fallback to default
        config = get_frequency_config(DEFAULT_FREQUENCY)
        if not config:
            # This should never happen, but handle gracefully
            raise ValueError(f"Invalid frequency type '{frequency_type}' and default '{DEFAULT_FREQUENCY}' not found")
    
    minutes = config['minutes']
    return current_time + timedelta(minutes=minutes)


def get_price_for_frequency(frequency_type: str) -> float:
    """
    Get price for a specific frequency.
    
    Args:
        frequency_type: Frequency identifier
        
    Returns:
        Price in DOMAIN tokens (defaults to 1.0 if invalid)
    """
    config = get_frequency_config(frequency_type)
    if not config:
        config = get_frequency_config(DEFAULT_FREQUENCY)
        if not config:
            # Fallback to safe default
            return 1.0
    
    return config['price']
