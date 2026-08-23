"""
hash_utils.py — Hashing Utilities
==================================
Content hashing, stable ID generation, fingerprinting.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


def content_hash(text: str, algorithm: str = "sha256") -> str:
    """Generate a content-based hash for deduplication/caching.

    Args:
        text: Input text to hash
        algorithm: Hash algorithm (sha256, md5, blake2b)

    Returns:
        Hex digest string
    """
    if algorithm == "md5":
        return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
    elif algorithm == "blake2b":
        return hashlib.blake2b(text.encode("utf-8", errors="replace"), digest_size=16).hexdigest()
    else:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> Optional[str]:
    """Generate a hash of file contents (streaming, memory-efficient).

    Args:
        path: Path to the file
        algorithm: Hash algorithm
        chunk_size: Bytes to read per iteration

    Returns:
        Hex digest string, or None if file can't be read
    """
    try:
        if algorithm == "md5":
            h = hashlib.md5()
        elif algorithm == "blake2b":
            h = hashlib.blake2b(digest_size=16)
        else:
            h = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def stable_id(*parts: str) -> str:
    """Generate a stable, deterministic ID from string parts.

    Uses SHA-256 truncated to 12 hex chars for readability.

    Args:
        *parts: String components to include in the ID

    Returns:
        12-character hex string
    """
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]


def quick_hash(text: str) -> str:
    """Fast, non-cryptographic hash for caching (Blake2b, 8 bytes)."""
    return hashlib.blake2b(
        text.encode("utf-8", errors="replace"),
        digest_size=8,
    ).hexdigest()