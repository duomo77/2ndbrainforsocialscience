"""
perf_engine.py — ROS v4.0 Performance Engine
=============================================
Three optimization subsystems in one module:

  A. Token Economy Engine
     - Minimize unnecessary context injection
     - Compress semantic retrieval
     - Hierarchical retrieval
     - Maximum intellectual signal per token

  B. Multi-Layer Cache Engine
     - Embedding cache
     - Retrieval cache
     - Semantic query cache
     - Prompt compilation cache
     - Memory-aware eviction (LRU)

  C. Incremental Computation Engine
     - Incremental embeddings (skip unchanged nodes)
     - Partial graph mutation
     - Dependency-aware recomputation
     - Selective cache invalidation
     - Event-driven indexing
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import time
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = _get_logger("ROS.PerfEngine")


# ══════════════════════════════════════════════════════════════════════════════
# A. TOKEN ECONOMY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# 컨텍스트 주입 우선순위 (명세서 §TOKEN ECONOMY ENGINE)
CONTEXT_PRIORITY = [
    "unresolved_tensions",
    "active_hypotheses",
    "high_confidence_abstractions",
    "recent_graph_mutations",
    "mathematically_central_concepts",
]

# 토큰 예산 (모델별)
TOKEN_BUDGETS = {
    "gpt-4o":          16_000,
    "gpt-4o-mini":      8_000,
    "gpt-4.1":         16_000,
    "gpt-4.1-mini":     8_000,
    "gpt-4.1-nano":     4_000,
    "deepseek-v3":     16_000,
    "deepseek-chat":   16_000,
    "qwen-max":        16_000,
    "qwen-plus":        8_000,
    "qwen3-4b":         4_000,
    "glm-4-plus":      16_000,
    "moonshot-v1-128k": 32_000,
    "default":          8_000,
}

# 대략적 토큰/문자 비율
CHARS_PER_TOKEN = 3.5


@dataclass
class ContextSlot:
    priority:    int        # 낮을수록 높은 우선순위
    slot_type:   str        # CONTEXT_PRIORITY 중 하나
    content:     str
    token_est:   int        # 추정 토큰 수
    trust_score: float = 1.0


class TokenEconomyEngine:
    """
    최대 지적 신호 밀도(intellectual signal per token) 최적화.
    컨텍스트 주입 우선순위 기반 토큰 예산 관리.
    """

    def __init__(self):
        self._stats = {"total_tokens_saved": 0, "calls": 0}

    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / CHARS_PER_TOKEN))

    def get_budget(self, model: str) -> int:
        for key in TOKEN_BUDGETS:
            if key in model.lower():
                return TOKEN_BUDGETS[key]
        return TOKEN_BUDGETS["default"]

    def build_optimized_context(
        self,
        model:       str,
        slots:       list[ContextSlot],
        system_prompt_tokens: int = 800,
        output_reserve_tokens: int = 2000,
    ) -> str:
        """
        토큰 예산 내에서 최대 신호 밀도 컨텍스트 구성.
        우선순위 순서대로 슬롯을 채움.
        """
        budget = self.get_budget(model)
        available = budget - system_prompt_tokens - output_reserve_tokens
        if available <= 0:
            return ""

        # 우선순위 정렬
        sorted_slots = sorted(slots, key=lambda s: s.priority)
        selected = []
        used_tokens = 0

        for slot in sorted_slots:
            if used_tokens + slot.token_est <= available:
                selected.append(slot)
                used_tokens += slot.token_est
            else:
                # 슬롯 잘라내기 (부분 포함)
                remaining = available - used_tokens
                if remaining > 100:
                    chars = int(remaining * CHARS_PER_TOKEN)
                    truncated = ContextSlot(
                        priority    = slot.priority,
                        slot_type   = slot.slot_type,
                        content     = slot.content[:chars] + "...[truncated]",
                        token_est   = remaining,
                        trust_score = slot.trust_score,
                    )
                    selected.append(truncated)
                break

        saved = sum(s.token_est for s in sorted_slots) - used_tokens
        self._stats["total_tokens_saved"] += max(0, saved)
        self._stats["calls"] += 1

        return "\n\n".join(
            f"### [{s.slot_type.replace('_', ' ').title()}]\n{s.content}"
            for s in selected
        )

    def compress_content(self, content: str, target_tokens: int) -> str:
        """추상화 기반 콘텐츠 압축."""
        current_tokens = self.estimate_tokens(content)
        if current_tokens <= target_tokens:
            return content
        # 단순 잘라내기 (실제로는 LLM 요약 사용 가능)
        target_chars = int(target_tokens * CHARS_PER_TOKEN)
        return content[:target_chars] + "\n...[compressed for token efficiency]"

    def get_stats(self) -> dict:
        return self._stats.copy()


# ══════════════════════════════════════════════════════════════════════════════
# B. MULTI-LAYER CACHE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class LRUCache:
    """메모리 인식 LRU 캐시."""

    def __init__(self, max_size: int = 500, max_bytes: int = 50 * 1024 * 1024):
        self._cache:     OrderedDict[str, Any] = OrderedDict()
        self._sizes:     dict[str, int] = {}
        self.max_size    = max_size
        self.max_bytes   = max_bytes
        self._max_bytes  = max_bytes
        self._total_bytes = 0
        self._hits       = 0
        self._misses     = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, value: Any, size_bytes: int = 0):
        if size_bytes == 0:
            size_bytes = len(str(value).encode("utf-8", errors="ignore"))
        # 크기 제한 초과 시 LRU 제거
        while (
            (len(self._cache) >= self.max_size or self._total_bytes + size_bytes > self.max_bytes)
            and self._cache
        ):
            evict_key, _ = self._cache.popitem(last=False)
            self._total_bytes -= self._sizes.pop(evict_key, 0)
        self._cache[key]  = value
        self._sizes[key]  = size_bytes
        self._total_bytes += size_bytes

    def invalidate(self, key: str):
        if key in self._cache:
            self._total_bytes -= self._sizes.pop(key, 0)
            del self._cache[key]

    def invalidate_prefix(self, prefix: str):
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            self.invalidate(k)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size":       len(self._cache),
            "bytes":      self._total_bytes,
            "hits":       self._hits,
            "misses":     self._misses,
            "hit_rate":   round(self._hits / max(total, 1), 3),
        }


class CacheEngine:
    """
    6-레이어 캐시 아키텍처.
    각 레이어는 독립적 LRU 캐시.
    """

    def __init__(self):
        total_mb = max(8, int(os.getenv("ROS_TOTAL_CACHE_MB", "50")))
        total_bytes = total_mb * 1024 * 1024
        weights = {
            "embedding": 0.35,
            "retrieval": 0.20,
            "semantic": 0.18,
            "graph": 0.10,
            "prompt": 0.07,
            "transcript": 0.10,
        }

        self.embedding_cache    = LRUCache(max_size=1000, max_bytes=int(total_bytes * weights["embedding"]))
        self.retrieval_cache    = LRUCache(max_size=300,  max_bytes=int(total_bytes * weights["retrieval"]))
        self.semantic_cache     = LRUCache(max_size=500,  max_bytes=int(total_bytes * weights["semantic"]))
        self.graph_cache        = LRUCache(max_size=200,  max_bytes=int(total_bytes * weights["graph"]))
        self.prompt_cache       = LRUCache(max_size=100,  max_bytes=int(total_bytes * weights["prompt"]))
        self.transcript_cache   = LRUCache(max_size=50,   max_bytes=int(total_bytes * weights["transcript"]))

        self._layers = {
            "embedding":   self.embedding_cache,
            "retrieval":   self.retrieval_cache,
            "semantic":    self.semantic_cache,
            "graph":       self.graph_cache,
            "prompt":      self.prompt_cache,
            "transcript":  self.transcript_cache,
        }

    def _make_key(self, *parts) -> str:
        return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:20]

    # ── 프롬프트 캐시 ─────────────────────────────────────────────────────────

    def get_prompt(self, title: str, input_type: str, model: str) -> Optional[str]:
        key = self._make_key("prompt", title, input_type, model)
        return self.prompt_cache.get(key)

    def put_prompt(self, title: str, input_type: str, model: str, prompt: str):
        key = self._make_key("prompt", title, input_type, model)
        self.prompt_cache.put(key, prompt)

    # ── 분석 결과 캐시 ────────────────────────────────────────────────────────

    def get_analysis(self, content_hash: str, model: str) -> Optional[str]:
        key = self._make_key("analysis", content_hash, model)
        return self.retrieval_cache.get(key)

    def put_analysis(self, content_hash: str, model: str, result: str):
        key = self._make_key("analysis", content_hash, model)
        self.retrieval_cache.put(key, result)

    # ── 그래프 순회 캐시 ──────────────────────────────────────────────────────

    def get_graph_traversal(self, node_id: str, depth: int) -> Optional[list]:
        key = self._make_key("graph_trav", node_id, depth)
        return self.graph_cache.get(key)

    def put_graph_traversal(self, node_id: str, depth: int, result: list):
        key = self._make_key("graph_trav", node_id, depth)
        self.graph_cache.put(key, result)

    def invalidate_graph_node(self, node_id: str):
        """노드 변경 시 관련 그래프 캐시 무효화."""
        self.graph_cache.invalidate_prefix(
            self._make_key("graph_trav", node_id, "")[:15]
        )

    # ── 전사 캐시 ─────────────────────────────────────────────────────────────

    def get_transcript(self, file_path: str) -> Optional[str]:
        key = self._make_key("transcript", file_path)
        return self.transcript_cache.get(key)

    def put_transcript(self, file_path: str, content: str):
        key = self._make_key("transcript", file_path)
        self.transcript_cache.put(key, content)

    def all_stats(self) -> dict:
        return {name: cache.stats() for name, cache in self._layers.items()}


# ══════════════════════════════════════════════════════════════════════════════
# C. INCREMENTAL COMPUTATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ComputationNode:
    node_id:   str
    checksum:  str          # 내용 해시
    computed_at: str
    dependencies: list[str] = field(default_factory=list)
    is_dirty:  bool = False


class IncrementalEngine:
    """
    증분 계산 엔진.
    변경되지 않은 노드는 재계산하지 않음.
    의존성 기반 선택적 캐시 무효화.
    """

    def __init__(self, data_dir: Optional[Path] = None, cache: Optional[CacheEngine] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        self._path  = data_dir / "incremental_state.json"
        self._nodes: dict[str, ComputationNode] = {}
        self._cache = cache
        self._load()
        self._stats = {"skipped": 0, "recomputed": 0}

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for n in data:
                    self._nodes[n["node_id"]] = ComputationNode(**n)
            except Exception:
                pass

    def _save(self):
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(n) for n in self._nodes.values()], indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    def content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def needs_recompute(self, node_id: str, content: str) -> bool:
        """콘텐츠 변경 여부 확인."""
        new_hash = self.content_hash(content)
        existing = self._nodes.get(node_id)
        if existing is None or existing.checksum != new_hash or existing.is_dirty:
            return True
        self._stats["skipped"] += 1
        return False

    def mark_computed(self, node_id: str, content: str, dependencies: list[str] = None):
        """계산 완료 마킹."""
        self._stats["recomputed"] += 1
        self._nodes[node_id] = ComputationNode(
            node_id      = node_id,
            checksum     = self.content_hash(content),
            computed_at  = datetime.utcnow().isoformat(),
            dependencies = dependencies or [],
            is_dirty     = False,
        )
        self._save()

        # 의존 노드 캐시 무효화
        if self._cache:
            self._cache.invalidate_graph_node(node_id)

    def mark_dirty(self, node_id: str):
        """노드를 dirty로 표시 → 다음 접근 시 재계산."""
        if node_id in self._nodes:
            self._nodes[node_id].is_dirty = True
            # 역방향 의존성 전파
            for n in self._nodes.values():
                if node_id in n.dependencies:
                    n.is_dirty = True
            self._save()

    def get_stats(self) -> dict:
        dirty = sum(1 for n in self._nodes.values() if n.is_dirty)
        return {
            "total_nodes": len(self._nodes),
            "dirty_nodes": dirty,
            **self._stats,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Singleton Access
# ══════════════════════════════════════════════════════════════════════════════

_token_engine:       Optional[TokenEconomyEngine] = None
_cache_engine:       Optional[CacheEngine]        = None
_incremental_engine: Optional[IncrementalEngine]  = None


def get_token_engine() -> TokenEconomyEngine:
    global _token_engine
    if _token_engine is None:
        _token_engine = TokenEconomyEngine()
    return _token_engine


def get_cache_engine() -> CacheEngine:
    global _cache_engine
    if _cache_engine is None:
        _cache_engine = CacheEngine()
    return _cache_engine


def get_incremental_engine() -> IncrementalEngine:
    global _incremental_engine
    if _incremental_engine is None:
        _incremental_engine = IncrementalEngine(cache=get_cache_engine())
    return _incremental_engine
