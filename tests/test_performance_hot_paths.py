import os
import time

import pytest

from core import obsidian_sync
from core.embedding_gov import SemanticDeduplicator
from core.perf_engine import CacheEngine
from core.rag_engine import (
    RAGContextBuilder,
    HierarchicalRetriever,
    RetrievalCandidate,
    RetrievalLayer,
)


def _clear_obsidian_caches():
    obsidian_sync._concept_cache.clear()
    obsidian_sync._notes_cache.clear()


def test_scan_vault_concepts_reuses_unchanged_file_cache(tmp_path, monkeypatch):
    _clear_obsidian_caches()
    for i in range(3):
        (tmp_path / f"note-{i}.md").write_text(f"[[Concept {i}]]", encoding="utf-8")

    read_count = 0
    original = type(tmp_path).read_text

    def counted_read_text(self, *args, **kwargs):
        nonlocal read_count
        read_count += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "read_text", counted_read_text)

    assert obsidian_sync.scan_vault_concepts(str(tmp_path)) == [
        "Concept 0", "Concept 1", "Concept 2", "note-0", "note-1", "note-2"
    ]
    assert obsidian_sync.scan_vault_concepts(str(tmp_path)) == [
        "Concept 0", "Concept 1", "Concept 2", "note-0", "note-1", "note-2"
    ]
    assert read_count == 3


def test_list_notes_uses_short_ttl_cache(tmp_path, monkeypatch):
    _clear_obsidian_caches()
    for i in range(3):
        (tmp_path / f"note-{i}.md").write_text("body", encoding="utf-8")

    stat_count = 0
    original = type(tmp_path).stat

    def counted_stat(self, *args, **kwargs):
        nonlocal stat_count
        stat_count += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "stat", counted_stat)

    first = obsidian_sync.list_notes(str(tmp_path))
    second = obsidian_sync.list_notes(str(tmp_path))

    assert len(first) == len(second) == 3
    assert stat_count <= 3


def test_shingles_are_bounded_hashes_not_large_strings():
    dedup = SemanticDeduplicator()
    shingles = dedup._compute_shingles(" ".join(f"word{i}" for i in range(3_000)))

    assert len(shingles) <= 498
    assert all(isinstance(item, bytes) for item in shingles)
    assert all(len(item) == 8 for item in shingles)


def test_duplicate_check_uses_hash_index_to_bound_jaccard_work(monkeypatch):
    dedup = SemanticDeduplicator()
    for i in range(200):
        dedup.register(f"unique{i} alpha beta gamma delta", f"node-{i}")

    calls = 0
    original = dedup._jaccard_similarity

    def counted_jaccard(a, b):
        nonlocal calls
        calls += 1
        return original(a, b)

    monkeypatch.setattr(dedup, "_jaccard_similarity", counted_jaccard)
    is_dup, existing = dedup.is_duplicate("totally new content without shared shingles", "new")

    assert is_dup is False
    assert existing is None
    assert calls < 20


def test_cache_engine_respects_total_budget_env(monkeypatch):
    monkeypatch.setenv("ROS_TOTAL_CACHE_MB", "20")
    engine = CacheEngine()

    total = sum(layer._max_bytes for layer in engine._layers.values())

    assert total <= 20 * 1024 * 1024


def test_rag_traversal_does_not_depend_on_path_rglob(tmp_path, monkeypatch):
    for i in range(5):
        (tmp_path / f"note-{i}.md").write_text("causal identification", encoding="utf-8")

    def explode(*args, **kwargs):
        raise AssertionError("rglob should not be used in bounded hot path")

    monkeypatch.setattr(type(tmp_path), "rglob", explode)
    retriever = HierarchicalRetriever(str(tmp_path))

    candidates = retriever._retrieve_layer(
        "causal identification",
        RetrievalLayer.L4_ATOMIC,
        max_count=3,
        token_budget=500,
    )

    assert len(candidates) <= 3


def test_rag_candidate_metadata_uses_single_stat_per_file(tmp_path, monkeypatch):
    for i in range(3):
        (tmp_path / f"note-{i}.md").write_text("causal identification", encoding="utf-8")

    stat_count = 0
    original = type(tmp_path).stat

    def counted_stat(self, *args, **kwargs):
        nonlocal stat_count
        stat_count += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "stat", counted_stat)
    retriever = HierarchicalRetriever(str(tmp_path))

    candidates = retriever._retrieve_layer(
        "causal identification",
        RetrievalLayer.L4_ATOMIC,
        max_count=3,
        token_budget=500,
    )

    assert len(candidates) == 3
    assert stat_count <= 3


def test_abstraction_density_uses_precompiled_patterns(monkeypatch):
    import re

    def explode(*args, **kwargs):
        raise AssertionError("runtime re.findall should not be used")

    monkeypatch.setattr(re, "findall", explode)
    retriever = HierarchicalRetriever("")

    assert retriever._estimate_abstraction_density("[[DML]] $Y_i = X_i beta$ causal") > 0


def test_context_builder_preserves_output_shape_with_many_sections():
    candidates = [
        RetrievalCandidate(
            node_id=f"n{i}",
            content="content",
            layer=RetrievalLayer.L4_ATOMIC.value,
            semantic_relevance=0.5,
            token_count=1,
        )
        for i in range(50)
    ]

    result = RAGContextBuilder().build(candidates, token_budget=100)

    assert "## ⚛️ Atomic Notes" in result
    assert "### [n0]" in result
