"""
file_utils.py — File Operation Utilities
=========================================
Atomic writes, safe backups, file existence checks.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically using write-temp/fsync/rename.

    Args:
        path: Target file path
        content: String content to write
        encoding: File encoding (default: utf-8)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
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


def atomic_write_json(path: Path, data: dict | list, encoding: str = "utf-8") -> None:
    """Write JSON data to a file atomically."""
    import json
    content = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write(path, content, encoding)


def quarantine_store_file(path: Path, reason: str = "", logger=None) -> Optional[Path]:
    """
    Move a corrupt store file aside instead of letting it be silently
    overwritten. The quarantined copy keeps its full content for recovery.

    Args:
        path: Corrupt file to quarantine
        reason: Human-readable failure reason (logged)
        logger: Optional logger; warnings are emitted when provided

    Returns:
        Quarantine path on success, None if the file could not be moved
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    quarantine_path = path.with_name(f"{path.name}.corrupt-{ts}")
    try:
        os.replace(path, quarantine_path)
    except OSError:
        if logger:
            logger.error(f"Could not quarantine corrupt store {path}: {reason}")
        return None
    if logger:
        logger.warning(
            f"Corrupt store quarantined: {path.name} -> {quarantine_path.name} ({reason})"
        )
    return quarantine_path


def load_json_store(path: Path, default_factory=dict, logger=None):
    """
    Load a JSON store with corrupt-file quarantine (X-01 contract).

    A parse failure never returns a silent empty default that the next save
    would cement into total data loss: the corrupt file is renamed aside
    (preserving its content) and the default is returned with a warning.

    Args:
        path: Store file path
        default_factory: Zero-arg callable producing a fresh default value
        logger: Optional logger for quarantine warnings

    Returns:
        Parsed data, or a fresh default when the file is missing/corrupt
    """
    import json

    if not path.exists():
        return default_factory()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as ex:
        quarantine_store_file(path, reason=str(ex), logger=logger)
        return default_factory()


def backup_file(path: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Create a timestamped backup of a file.

    Args:
        path: Path to the file to back up
        backup_dir: Directory for backup (default: same directory as file)

    Returns:
        Path to the backup file, or None if the file doesn't exist
    """
    if not path.exists():
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{path.stem}.backup-{ts}{path.suffix}"
    backup_path = (backup_dir or path.parent) / backup_name

    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except OSError:
        return None


def safe_read_text(path: Path, encoding: str = "utf-8", default: str = "") -> str:
    """Safely read file content with fallback on error."""
    try:
        return path.read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError):
        try:
            return path.read_text(encoding=encoding, errors="replace")
        except OSError:
            return default


def ensure_dir(path: Path) -> None:
    """Create directory and all parents if they don't exist."""
    path.mkdir(parents=True, exist_ok=True)


def is_writable(path: Path) -> bool:
    """Check if a path (or its parent) is writable."""
    target = path if path.exists() else path.parent
    return os.access(str(target), os.W_OK)


def get_file_size_mb(path: Path) -> float:
    """Get file size in megabytes."""
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024 * 1024)