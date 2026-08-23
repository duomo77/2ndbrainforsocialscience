"""
validation_utils.py — Input Validation Utilities
=================================================
Type checking, range validation, and common validation patterns.
"""

from __future__ import annotations

from typing import Any, Optional


def is_non_empty_string(value: Any) -> bool:
    """Check if value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def is_valid_url(value: str) -> bool:
    """Basic URL format validation."""
    if not isinstance(value, str):
        return False
    return value.startswith(("http://", "https://"))


def is_valid_email(value: str) -> bool:
    """Basic email format validation."""
    if not isinstance(value, str):
        return False
    return "@" in value and "." in value.split("@")[-1]


def validate_range(value: int | float, min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
    """Validate that a numeric value is within a range."""
    if not isinstance(value, (int, float)):
        return False
    if min_val is not None and value < min_val:
        return False
    if max_val is not None and value > max_val:
        return False
    return True


def validate_list_length(items: list, min_len: int = 0, max_len: Optional[int] = None) -> bool:
    """Validate list length constraints."""
    if not isinstance(items, list):
        return False
    if len(items) < min_len:
        return False
    if max_len is not None and len(items) > max_len:
        return False
    return True


def validate_choice(value: str, choices: list[str], case_sensitive: bool = True) -> bool:
    """Validate that a string is one of the allowed choices."""
    if not isinstance(value, str):
        return False
    if case_sensitive:
        return value in choices
    return value.lower() in [c.lower() for c in choices]


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int with fallback default."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float with fallback default."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely interpret a value as boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on", "y")
    if isinstance(value, (int, float)):
        return bool(value)
    return default