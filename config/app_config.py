"""
app_config.py — Centralized Application Configuration
======================================================
Provides a unified configuration system supporting:
- Environment variables (ROS_ prefix)
- YAML configuration files (config/defaults/*.yaml)
- Default values with validation
- Backward compatibility with existing core/config.py

Existing Config class from core.config is preserved and wrapped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Preserve backward compatibility — re-export existing config module
from core.config import (
    Config,
    DEFAULT_CONFIG,
    load_config,
    save_config,
    get_config_path,
    _atomic_write_json,
    _normalize_aliases,
)

# Re-export entire existing API
__all__ = [
    "Config",
    "DEFAULT_CONFIG",
    "load_config",
    "save_config",
    "get_config_path",
    "AppConfig",
    "get_app_config",
    "ConfigSchema",
]


class ConfigSchema:
    """Configuration schema with validation and environment variable support."""

    @staticmethod
    def get_env(key: str, default: Any = None) -> Any:
        """Read configuration from environment variable with ROS_ prefix."""
        return os.environ.get(f"ROS_{key.upper()}", default)

    @staticmethod
    def get_bool_env(key: str, default: bool = False) -> bool:
        """Read boolean configuration from environment variable."""
        val = os.environ.get(f"ROS_{key.upper()}")
        if val is None:
            return default
        return val.lower() in ("1", "true", "yes", "on")

    @staticmethod
    def get_int_env(key: str, default: int = 0) -> int:
        """Read integer configuration from environment variable."""
        val = os.environ.get(f"ROS_{key.upper()}")
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    @staticmethod
    def validate_api_key(key: str) -> bool:
        """Validate that an API key is non-empty and properly formatted."""
        if not key or not isinstance(key, str):
            return False
        return len(key.strip()) >= 8

    @staticmethod
    def validate_model_name(model: str, supported: Optional[list] = None) -> bool:
        """Validate model name against supported list if provided."""
        if not model or not isinstance(model, str):
            return False
        if supported is not None:
            return model in supported
        return True

    @staticmethod
    def validate_vault_path(path: str) -> bool:
        """Validate that the vault path exists and is writable."""
        if not path:
            return False
        p = Path(path)
        return p.exists() and p.is_dir() and os.access(str(p), os.W_OK)


class AppConfig:
    """
    Centralized application configuration.

    Merges from (lowest to highest priority):
        1. DEFAULT_CONFIG (hardcoded defaults)
        2. config.json (user-saved config)
        3. Environment variables (ROS_* prefix)
        4. Runtime overrides (set programmatically)

    Backward compatible: delegates to core.config for file persistence.
    """

    def __init__(self) -> None:
        self._runtime_overrides: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with priority resolution."""
        # 1. Runtime overrides (highest priority)
        if key in self._runtime_overrides:
            return self._runtime_overrides[key]

        # 2. Environment variables
        env_val = ConfigSchema.get_env(key)
        if env_val is not None:
            return env_val

        # 3. File-based config (delegates to existing core.config)
        config = load_config()
        if key in config:
            return config[key]

        # 4. Hardcoded defaults
        if key in DEFAULT_CONFIG:
            return DEFAULT_CONFIG[key]

        return default

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """Set configuration value. If persist=True, save to disk."""
        self._runtime_overrides[key] = value
        if persist:
            config = load_config()
            config[key] = value
            save_config(config)

    def get_all(self) -> Dict[str, Any]:
        """Get the fully resolved configuration as a dictionary."""
        resolved = dict(DEFAULT_CONFIG)
        resolved.update(load_config())

        # Apply environment overrides
        for key in resolved:
            env_val = ConfigSchema.get_env(key)
            if env_val is not None:
                resolved[key] = env_val

        # Apply runtime overrides
        resolved.update(self._runtime_overrides)
        return resolved

    @property
    def api_key(self) -> str:
        return self.get("api_key", "")

    @property
    def base_url(self) -> str:
        return self.get("base_url", "https://api.openai.com/v1")

    @property
    def model(self) -> str:
        return self.get("model", "gpt-5.2")

    @property
    def vault_path(self) -> str:
        return self.get("vault_path", "")

    @property
    def auto_sync(self) -> bool:
        return self.get("auto_sync", True)

    @property
    def auto_save(self) -> bool:
        return self.get("auto_save", True)

    @property
    def debug_mode(self) -> bool:
        return ConfigSchema.get_bool_env("DEBUG", False)

    @property
    def log_level(self) -> str:
        return ConfigSchema.get_env("LOG_LEVEL", "INFO").upper()

    @property
    def cache_dir(self) -> Path:
        return Path(self.get("cache_dir", str(Path.home() / ".ros_config" / "cache")))

    @property
    def max_rag_file_bytes(self) -> int:
        return ConfigSchema.get_int_env("MAX_RAG_FILE_BYTES", 512 * 1024)

    @property
    def max_content_chars(self) -> int:
        return ConfigSchema.get_int_env("MAX_CONTENT_CHARS", 65000)


# Module-level singleton
_app_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    """Get or create the singleton AppConfig instance."""
    global _app_config
    if _app_config is None:
        _app_config = AppConfig()
    return _app_config