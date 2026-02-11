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
    """Extract all literal data-i18n and data-i18n-dynamic keys from web/ (HTML and JS)."""
    keys = set()
    # data-i18n="key" (literal key in quotes)
    literal_re = re.compile(r'data-i18n=["\']([a-zA-Z0-9_]+)["\']')
    # data-i18n="${...}" / data-i18n="' + key + '" - dynamic, skip or use known list
    for path in WEB_DIR.rglob("*.html"):
        keys.update(literal_re.findall(path.read_text(encoding="utf-8")))
    for path in WEB_DIR.rglob("*.js"):
        keys.update(literal_re.findall(path.read_text(encoding="utf-8")))
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
    """Every key referenced in the frontend (data-i18n="key") exists in every locale file."""
    frontend_keys = _get_frontend_i18n_keys()
    assert frontend_keys, "No data-i18n keys found in web/"
    for path in LOCALES_DIR.glob("*.json"):
        locale = _load_locale(path)
        missing = frontend_keys - set(locale.keys())
        assert not missing, (
            f"{path.name} is missing keys used in frontend: {sorted(missing)}. "
            "Add them to all locale files to avoid console warnings."
        )
