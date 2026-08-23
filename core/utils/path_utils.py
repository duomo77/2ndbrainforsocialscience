"""
path_utils.py — Path Manipulation Utilities
============================================
Safe path operations, sanitization, and vault path resolution.
"""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Sanitize a string for use as a filename.

    Removes or replaces characters that are invalid in file names
    across Windows, macOS, and Linux.

    Args:
        name: Input string
        replacement: Character to replace invalid chars with

    Returns:
        Safe filename string
    """
    # Characters not allowed in filenames on common OS
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, name)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(" .")
    # Ensure non-empty
    return sanitized or "untitled"


def resolve_vault_path(vault_root: str | Path, subfolder: str = "") -> Path:
    """Resolve a path within an Obsidian vault.

    Args:
        vault_root: Root directory of the vault
        subfolder: Subdirectory within the vault

    Returns:
        Resolved absolute Path
    """
    root = Path(vault_root).expanduser().resolve()
    if subfolder:
        target = (root / subfolder).resolve()
        # Security: ensure we don't escape the vault
        if not str(target).startswith(str(root)):
            return root
        return target
    return root


def is_within_vault(path: Path, vault_root: Path) -> bool:
    """Check if a path is within the vault directory.

    Args:
        path: Path to check
        vault_root: Vault root directory

    Returns:
        True if path is inside the vault
    """
    try:
        path.resolve().relative_to(vault_root.resolve())
        return True
    except ValueError:
        return False


def get_relative_path(path: Path, base: Path) -> str:
    """Get a relative path as a POSIX-style string.

    Args:
        path: Target path
        base: Base directory

    Returns:
        Relative path as POSIX string (forward slashes)
    """
    try:
        rel = path.resolve().relative_to(base.resolve())
        return rel.as_posix()
    except ValueError:
        return str(path)


def ensure_unique_path(path: Path) -> Path:
    """If a path already exists, append a number to make it unique.

    Args:
        path: Desired file path

    Returns:
        Unique file path
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def find_files_by_extension(
    directory: Path,
    extensions: set[str],
    recursive: bool = True,
    max_depth: int = 5,
    max_files: int = 10_000,
) -> list[Path]:
    """Find files with specific extensions in a directory.

    Args:
        directory: Root directory to search
        extensions: Set of extensions to match (e.g., {'.md', '.txt'})
        recursive: Whether to search subdirectories
        max_depth: Maximum recursion depth
        max_files: Maximum number of files to return

    Returns:
        List of matching file paths
    """
    results = []
    pattern = "**/*" if recursive else "*"

    for file_path in directory.glob(pattern):
        if len(results) >= max_files:
            break
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            # Check depth
            if recursive:
                depth = len(file_path.relative_to(directory).parts)
                if depth > max_depth:
                    continue
            results.append(file_path)

    return results