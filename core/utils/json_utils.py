"""
json_utils.py — JSON Operation Utilities
=========================================
Safe JSON loading, migration, and file-based operations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def safe_load_json(path: Path, default: Any = None) -> Any:
    """Safely load JSON from a file with fallback default.

    Args:
        path: Path to JSON file
        default: Value to return if file doesn't exist or is corrupt

    Returns:
        Parsed JSON data or default
    """
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def safe_load_json_dict(path: Path, default: Optional[Dict] = None) -> Dict[str, Any]:
    """Safely load JSON as a dictionary with fallback."""
    result = safe_load_json(path, default)
    if isinstance(result, dict):
        return result
    return default or {}


def safe_load_json_list(path: Path, default: Optional[list] = None) -> list:
    """Safely load JSON as a list with fallback."""
    result = safe_load_json(path, default)
    if isinstance(result, list):
        return result
    return default or []


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge two configuration dictionaries.

    Override values take precedence. Nested dicts are merged recursively.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary

    Returns:
        Merged dictionary
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def jsonl_append(path: Path, record: Dict[str, Any]) -> None:
    """Append a record to a JSON Lines file.

    Args:
        path: Path to the .jsonl file
        record: Dictionary record to append
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def validate_json_schema(data: Dict[str, Any], required_fields: list) -> tuple[bool, str]:
    """Validate that a dictionary contains required fields.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Expected a dictionary"

    missing = [field for field in required_fields if field not in data or not data[field]]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    return True, "Valid"