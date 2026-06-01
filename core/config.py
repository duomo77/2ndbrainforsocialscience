"""
Configuration persistence for ROS.

The config file is small, but it is operationally critical: losing an API key
or vault path makes the desktop app look broken. Writes therefore use an
atomic replace, corrupted files are preserved for recovery, and legacy aliases
are normalized at the boundary.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".econometric_wiki"
CONFIG_FILE = CONFIG_DIR / "config.json"
_CONFIG_LOCK = threading.RLock()


DEFAULT_CONFIG = {
    "api_key": "",
    "api_base_url": "https://api.openai.com/v1",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-5.2",
    "obsidian_vault_path": "",
    "vault_path": "",
    "obsidian_subfolder": "Papers",
    "auto_sync": True,
    "auto_save": True,
    "existing_concepts": [],
    "zotero_link_prefix": "zotero://select/library/items/",
    "use_topic_folders": True,
    "llm_classify_fallback": True,
    "classification_rules": {},
    "custom_topics": [],
}


def _normalize_aliases(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    base_url = normalized.get("base_url")
    api_base_url = normalized.get("api_base_url")
    canonical_base_url = base_url or api_base_url or DEFAULT_CONFIG["api_base_url"]
    normalized["base_url"] = canonical_base_url
    normalized["api_base_url"] = canonical_base_url

    vault_path = normalized.get("vault_path")
    obsidian_vault_path = normalized.get("obsidian_vault_path")
    canonical_vault_path = vault_path or obsidian_vault_path or ""
    normalized["vault_path"] = canonical_vault_path
    normalized["obsidian_vault_path"] = canonical_vault_path

    return normalized


def _backup_corrupt_config() -> None:
    if not CONFIG_FILE.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = CONFIG_FILE.with_name(f"{CONFIG_FILE.stem}.corrupt-{ts}{CONFIG_FILE.suffix}")
    try:
        CONFIG_FILE.replace(backup_path)
    except OSError:
        try:
            backup_path.write_text(
                CONFIG_FILE.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )
        except OSError:
            pass


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def load_config() -> dict[str, Any]:
    """Load config, preserving a corrupt file before falling back to defaults."""
    with _CONFIG_LOCK:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            return _normalize_aliases(dict(DEFAULT_CONFIG))

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _backup_corrupt_config()
            return _normalize_aliases(dict(DEFAULT_CONFIG))

        return _normalize_aliases({**DEFAULT_CONFIG, **data})


def save_config(config: dict[str, Any]) -> None:
    """Persist config via write-temp/fsync/atomic-replace."""
    with _CONFIG_LOCK:
        data = _normalize_aliases({**DEFAULT_CONFIG, **config})
        _atomic_write_json(CONFIG_FILE, data)


def get_config_path() -> str:
    return str(CONFIG_FILE)


class Config:
    """Small dict-like adapter used by the PyQt UI."""

    def __init__(self):
        self._data = load_config()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def save(self):
        self._data = _normalize_aliases(self._data)
        save_config(self._data)

    def reload(self):
        self._data = load_config()
