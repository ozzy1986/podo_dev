"""
Internationalization (i18n) support for d.onl Telegram Bot
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from database.db import get_db

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'ru', 'ar']
DEFAULT_LANGUAGE = 'en'

# Translation cache
_translations: Dict[str, Dict[str, Any]] = {}

def _load_translations():
    """Load all translation files into memory."""
    global _translations

    if _translations:
        return  # Already loaded

    locales_dir = os.path.dirname(__file__)

    for lang in SUPPORTED_LANGUAGES:
        try:
            with open(os.path.join(locales_dir, f"{lang}.json"), 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)
                logger.info(f"Loaded translations for {lang}")
        except Exception as e:
            logger.error(f"Failed to load translations for {lang}: {e}")
            _translations[lang] = {}

_load_translations()

def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Get translated text for a given key and language.

    Args:
        key: Translation key
        language: Language code (en, ru, ar)
        **kwargs: Format parameters

    Returns:
        Translated and formatted text
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    translations = _translations.get(language, {})
    text = translations.get(key, f"[{key}]")  # Fallback to key in brackets

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to format text '{key}' with {kwargs}: {e}")

    return text

def get_user_language(telegram_id: int) -> str:
    """
    Get user's preferred language from database.

    Args:
        telegram_id: Telegram user ID

    Returns:
        Language code or default language
    """
    try:
        db = get_db()
        with db.get_cursor() as (cursor, conn):
            cursor.execute("SELECT language FROM users WHERE telegram_id = %s", (telegram_id,))
            result = cursor.fetchone()
            if result and result['language']:
                return result['language']
    except Exception as e:
        logger.error(f"Error getting user language for {telegram_id}: {e}")

    return DEFAULT_LANGUAGE

def set_user_language(telegram_id: int, language: str) -> bool:
    """
    Set user's preferred language in database.

    Args:
        telegram_id: Telegram user ID
        language: Language code

    Returns:
        True if successful, False otherwise
    """
    if language not in SUPPORTED_LANGUAGES:
        return False

    try:
        db = get_db()
        with db.get_cursor() as (cursor, conn):
            cursor.execute(
                "UPDATE users SET language = %s WHERE telegram_id = %s",
                (language, telegram_id)
            )
            conn.commit()
            logger.info(f"Set language to {language} for user {telegram_id}")
            return True
    except Exception as e:
        logger.error(f"Error setting user language for {telegram_id}: {e}")
        return False

def get_language_name(language_code: str) -> str:
    """Get the display name of a language in that language."""
    names = {
        'en': {'en': 'English', 'ru': 'Английский', 'ar': 'الإنجليزية'},
        'ru': {'en': 'Russian', 'ru': 'Русский', 'ar': 'الروسية'},
        'ar': {'en': 'Arabic', 'ru': 'Арабский', 'ar': 'العربية'}
    }
    return names.get(language_code, {}).get(language_code, language_code)

def validate_language(language: str) -> bool:
    """Check if a language code is supported."""
    return language in SUPPORTED_LANGUAGES
