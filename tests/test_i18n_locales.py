"""
Tests for i18n: locale files are valid, have same keys, and every key used in the frontend exists in all locales.
This catches missing translation keys (e.g. 'comments', 'send') that would cause console warnings in the browser.
"""

import json
import re
from pathlib import Path

import pytest

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = PROJECT_ROOT / "locales"
WEB_DIR = PROJECT_ROOT / "web"


def _load_locale(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_frontend_i18n_keys() -> set:
    """Extract all i18n keys from web/: data-i18n="key" and i18n.t('key') / i18n.t(\"key\")."""
    keys = set()
    # data-i18n="key" (literal key in quotes)
    data_i18n_re = re.compile(r'data-i18n=["\']([a-zA-Z0-9_]+)["\']')
    # i18n.t('key') or i18n.t("key") (placeholders, JS-driven strings)
    i18n_t_re = re.compile(r"i18n\.t\s*\(\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\)")
    for path in WEB_DIR.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        keys.update(data_i18n_re.findall(text))
    for path in WEB_DIR.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        keys.update(data_i18n_re.findall(text))
        keys.update(i18n_t_re.findall(text))
    return keys


def test_locales_exist():
    """Locales dir exists and contains en.json."""
    assert LOCALES_DIR.is_dir(), "locales/ directory missing"
    en = LOCALES_DIR / "en.json"
    assert en.is_file(), "locales/en.json missing"


def test_locales_valid_json():
    """All .json in locales/ are valid JSON."""
    for path in LOCALES_DIR.glob("*.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{path.name} must be a JSON object"


def test_locales_same_keys():
    """All locale files have the same set of keys (no missing or extra per locale)."""
    files = list(LOCALES_DIR.glob("*.json"))
    assert files, "No locale JSON files found"
    key_sets = {}
    for path in files:
        key_sets[path.name] = set(_load_locale(path).keys())
    ref_name = "en.json"
    ref_keys = key_sets[ref_name]
    for name, keys in key_sets.items():
        missing = ref_keys - keys
        extra = keys - ref_keys
        assert not missing, f"{name} missing keys vs en.json: {sorted(missing)}"
        assert not extra, f"{name} has extra keys vs en.json: {sorted(extra)}"


def test_frontend_keys_exist_in_all_locales():
    """Every key used in the frontend (data-i18n or i18n.t) exists in every locale file."""
    frontend_keys = _get_frontend_i18n_keys()
    assert frontend_keys, "No data-i18n keys found in web/"
    for path in LOCALES_DIR.glob("*.json"):
        locale = _load_locale(path)
        missing = frontend_keys - set(locale.keys())
        assert not missing, (
            f"{path.name} is missing keys used in frontend: {sorted(missing)}. "
            "Add them to all locale files to avoid console warnings."
        )


# Keys where the same value as en is allowed (examples, codes, symbols, proper nouns)
TRANSLATION_SAME_ALLOWLIST = {
    "wallet_example",   # address format
    "domain_example",   # example.com
    "rank",             # "#" symbol
    "wallet_command_example",  # /wallet YOUR_ADDRESS format
    "domain_command_example",  # /adddomain format
}


def test_no_english_text_in_translated_locales():
    """Non-English locales must not have the same value as en.json (catches untranslated copy-paste)."""
    en_path = LOCALES_DIR / "en.json"
    en = _load_locale(en_path)
    files = [p for p in LOCALES_DIR.glob("*.json") if p.name != "en.json"]
    assert files, "No non-en locale files"

    errors = []
    for path in files:
        locale = _load_locale(path)
        lang = path.stem
        for key, en_val in en.items():
            if key not in locale:
                continue
            loc_val = locale[key]
            if loc_val != en_val:
                continue
            if key in TRANSLATION_SAME_ALLOWLIST:
                continue
            errors.append(f"{path.name} key {key!r}: value is same as en ({en_val[:50]!r}...)")

    assert not errors, (
        "These keys have the same value as English (likely untranslated). "
        "Translate them or add to TRANSLATION_SAME_ALLOWLIST if intentional.\n  " + "\n  ".join(errors)
    )
