"""
embedding_gov.py — Semantic Deduplication for Graph Content (EPIC follow-up)
============================================================================
Bounded near-duplicate detection for node content. Used to keep the concept
registry and graph from accumulating paraphrased copies of the same idea.

Design constraints (performance hot-path contract, pinned by
tests/test_performance_hot_paths.py):
  - shingles are fixed-size 8-byte hashes, never large strings
  - per-document shingle count is hard-capped
  - duplicate checks go through a shingle → node inverted index so
    Jaccard work is bounded by actual shingle overlap, not corpus size

No embeddings are involved yet: this is a lexical shingle layer that a
future embedding index can sit on top of without API changes.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Dict, List, Optional, Set, Tuple

_MAX_SHINGLES = 498          # hard cap on shingles kept per document
_SHINGLE_WORDS = 3           # words per shingle
_SIMILARITY_THRESHOLD = 0.5  # Jaccard threshold for "duplicate"


class SemanticDeduplicator:
    """Shingle-based near-duplicate detector with an inverted hash index."""

    def __init__(
        self,
        shingle_words: int = _SHINGLE_WORDS,
        max_shingles: int = _MAX_SHINGLES,
        similarity_threshold: float = _SIMILARITY_THRESHOLD,
    ) -> None:
        self._shingle_words = max(1, int(shingle_words))
        self._max_shingles = max(1, int(max_shingles))
        self._similarity_threshold = similarity_threshold
        self._index: Dict[bytes, Set[str]] = {}
        self._node_shingles: Dict[str, frozenset] = {}

    # ── public API ─────────────────────────────────────────────────────────

    def register(self, content: str, node_id: str) -> None:
        """Index a node's content for future duplicate checks."""
        shingles = frozenset(self._compute_shingles(content))
        self._node_shingles[node_id] = shingles
        for shingle in shingles:
            self._index.setdefault(shingle, set()).add(node_id)

    def unregister(self, node_id: str) -> None:
        shingles = self._node_shingles.pop(node_id, frozenset())
        for shingle in shingles:
            holders = self._index.get(shingle)
            if holders:
                holders.discard(node_id)
                if not holders:
                    del self._index[shingle]

    def is_duplicate(self, content: str, node_id: str) -> Tuple[bool, Optional[str]]:
        """Check content against registered nodes.

        Returns (is_duplicate, matching_node_id). Only nodes sharing at
        least one shingle are compared — Jaccard work stays bounded.
        """
        shingles = set(self._compute_shingles(content))
        candidates: Set[str] = set()
        for shingle in shingles:
            candidates.update(self._index.get(shingle, ()))
        candidates.discard(node_id)

        for candidate in candidates:
            if self._jaccard_similarity(shingles, self._node_shingles[candidate]) \
                    >= self._similarity_threshold:
                return True, candidate
        return False, None

    def __len__(self) -> int:
        return len(self._node_shingles)

    # ── internals ──────────────────────────────────────────────────────────

    def _compute_shingles(self, text: str) -> List[bytes]:
        """Bounded set of fixed-size shingle hashes for a text."""
        words = (text or "").lower().split()
        k = self._shingle_words
        if not words:
            return []
        if len(words) < k:
            return [self._hash_shingle(" ".join(words))]

        hashed = {
            self._hash_shingle(" ".join(words[i:i + k]))
            for i in range(len(words) - k + 1)
        }
        # Deterministic bound: sorted byte order, hard-capped
        return sorted(hashed)[: self._max_shingles]

    @staticmethod
    def _hash_shingle(shingle: str) -> bytes:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest()
        return struct.pack("8s", digest)

    @staticmethod
    def _jaccard_similarity(a: set, b: frozenset) -> float:
        if not a and not b:
            return 1.0
        union = len(a | b)
        if union == 0:
            return 0.0
        return len(a & b) / union
