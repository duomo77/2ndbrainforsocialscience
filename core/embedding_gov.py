"""
embedding_gov.py — ROS v5.0 Embedding Cost Governance
=======================================================
Philosophy: "Never re-embed unchanged nodes. Never embed low-value debris."

Core Policies:
  1. Embedding TTL (Time-To-Live)
  2. Semantic Deduplication
  3. Incremental Embedding (only changed content)
  4. Abstraction-Level Embedding Reuse
  5. Cluster-Based Embedding Inheritance
"""

from __future__ import annotations

import hashlib
import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = _get_logger("ROS.EmbeddingGov")


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

# 임베딩 TTL 정책 (초 단위)
EMBEDDING_TTL = {
    "hot":  7 * 86400,    # 7일 (활성 연구)
    "warm": 90 * 86400,   # 90일 (안정적 추상화)
    "cold": 365 * 86400,  # 1년 (역사적 노트)
}

# 임베딩 가치 임계값 (이하 임베딩 억제)
MIN_EMBEDDING_VALUE = 0.2

# 의미 중복 임계값 (이상이면 중복으로 판단)
SEMANTIC_DUP_THRESHOLD = 0.92

# 임베딩 비용 추정 (per 1K tokens, USD)
EMBEDDING_COST_PER_1K = 0.0001  # text-embedding-3-small 기준


# ══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmbeddingRecord:
    """임베딩 레코드."""
    content_hash:    str
    node_id:         str
    tier:            str          # hot / warm / cold
    created_at:      float        # Unix timestamp
    last_accessed:   float
    access_count:    int = 0
    token_count:     int = 0
    abstraction_level: int = 0    # 0=atomic, 1=cluster, 2=global
    is_stale:        bool = False
    parent_hash:     Optional[str] = None   # 클러스터 상속 부모

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def ttl(self) -> float:
        return EMBEDDING_TTL.get(self.tier, EMBEDDING_TTL["warm"])

    @property
    def is_expired(self) -> bool:
        return self.age_seconds > self.ttl

    @property
    def value_score(self) -> float:
        """임베딩 가치 점수."""
        recency = max(0.0, 1.0 - self.age_seconds / self.ttl)
        frequency = min(self.access_count / 10.0, 1.0)
        abstraction_bonus = self.abstraction_level * 0.1
        return recency * 0.5 + frequency * 0.3 + abstraction_bonus + 0.1


@dataclass
class EmbeddingDecision:
    """임베딩 결정 결과."""
    should_embed:    bool
    reason:          str
    reuse_hash:      Optional[str] = None   # 재사용 가능한 임베딩 해시
    estimated_cost:  float = 0.0
    cost_saved:      float = 0.0


@dataclass
class EmbeddingGovStats:
    """임베딩 거버넌스 통계."""
    total_requests:    int = 0
    embeddings_created: int = 0
    embeddings_reused:  int = 0
    embeddings_skipped: int = 0
    duplicates_detected: int = 0
    stale_evicted:      int = 0
    total_cost_usd:     float = 0.0
    total_saved_usd:    float = 0.0
    dedup_rate:         float = 0.0
    reuse_rate:         float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Semantic Deduplicator
# ══════════════════════════════════════════════════════════════════════════════

class SemanticDeduplicator:
    """
    의미 중복 감지기.
    실제 벡터 임베딩 없이 콘텐츠 해시 + 구조 유사도로 중복 판단.
    """

    def __init__(self):
        self._hash_registry: dict[str, str] = {}  # content_hash → node_id
        self._shingle_registry: dict[str, set[str]] = {}  # node_id → shingles

    def is_duplicate(self, content: str, node_id: str) -> tuple[bool, Optional[str]]:
        """
        중복 여부 확인.
        Returns: (is_dup, existing_node_id)
        """
        # 1. 정확한 해시 매칭
        content_hash = self._compute_hash(content)
        if content_hash in self._hash_registry:
            existing = self._hash_registry[content_hash]
            if existing != node_id:
                return True, existing

        # 2. Shingling 기반 근사 중복 감지
        shingles = self._compute_shingles(content)
        for existing_id, existing_shingles in self._shingle_registry.items():
            if existing_id == node_id:
                continue
            similarity = self._jaccard_similarity(shingles, existing_shingles)
            if similarity >= SEMANTIC_DUP_THRESHOLD:
                return True, existing_id

        # 중복 아님 → 등록
        self._hash_registry[content_hash] = node_id
        self._shingle_registry[node_id] = shingles
        return False, None

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_shingles(self, content: str, k: int = 3) -> set[str]:
        """k-shingle 집합 생성."""
        words = content.lower().split()
        if len(words) < k:
            return {" ".join(words)}
        return {" ".join(words[i:i+k]) for i in range(len(words) - k + 1)}

    def _jaccard_similarity(self, a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union > 0 else 0.0

    def register(self, content: str, node_id: str):
        """노드 등록 (중복 체크 없이)."""
        content_hash = self._compute_hash(content)
        self._hash_registry[content_hash] = node_id
        self._shingle_registry[node_id] = self._compute_shingles(content)


# ══════════════════════════════════════════════════════════════════════════════
# Embedding Registry (영속 저장)
# ══════════════════════════════════════════════════════════════════════════════

class EmbeddingRegistry:
    """임베딩 레코드 영속 저장소."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "embedding_registry.json"
        self._records: dict[str, EmbeddingRecord] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self._records[k] = EmbeddingRecord(**v)
            except Exception:
                self._records = {}

    def _save(self):
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({k: asdict(v) for k, v in self._records.items()}, indent=2),
                encoding="utf-8"
            )
            tmp.replace(self._path)
        except Exception as e:
            logger.error(f"Registry save failed: {e}")

    def get(self, content_hash: str) -> Optional[EmbeddingRecord]:
        rec = self._records.get(content_hash)
        if rec:
            rec.last_accessed = time.time()
            rec.access_count += 1
        return rec

    def put(self, record: EmbeddingRecord):
        self._records[record.content_hash] = record
        if len(self._records) % 50 == 0:
            self._save()

    def evict_stale(self) -> int:
        """만료된 임베딩 제거."""
        stale = [k for k, v in self._records.items() if v.is_expired]
        for k in stale:
            del self._records[k]
        if stale:
            self._save()
        return len(stale)

    def evict_low_value(self, min_value: float = MIN_EMBEDDING_VALUE) -> int:
        """저가치 임베딩 제거."""
        low = [k for k, v in self._records.items() if v.value_score < min_value]
        for k in low:
            del self._records[k]
        if low:
            self._save()
        return len(low)

    def stats(self) -> dict:
        total = len(self._records)
        expired = sum(1 for v in self._records.values() if v.is_expired)
        by_tier = {"hot": 0, "warm": 0, "cold": 0}
        for v in self._records.values():
            by_tier[v.tier] = by_tier.get(v.tier, 0) + 1
        return {
            "total": total,
            "expired": expired,
            "by_tier": by_tier,
            "dup_rate": 0.0,
        }

    def __len__(self):
        return len(self._records)


# ══════════════════════════════════════════════════════════════════════════════
# Embedding Governance Engine
# ══════════════════════════════════════════════════════════════════════════════

class EmbeddingGovernanceEngine:
    """
    임베딩 비용 거버넌스 메인 엔진.
    모든 임베딩 요청을 평가하고 비용 최적 결정을 내림.
    """

    def __init__(self):
        self._registry   = EmbeddingRegistry()
        self._deduplicator = SemanticDeduplicator()
        self._stats      = EmbeddingGovStats()

    def should_embed(
        self,
        content: str,
        node_id: str,
        tier: str = "warm",
        abstraction_level: int = 0,
        force: bool = False,
    ) -> EmbeddingDecision:
        """
        임베딩 필요 여부 결정.
        Returns: EmbeddingDecision
        """
        self._stats.total_requests += 1
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        token_count  = len(content) // 4
        estimated_cost = token_count / 1000 * EMBEDDING_COST_PER_1K

        if force:
            self._register_new(content_hash, node_id, tier, abstraction_level, token_count)
            self._stats.embeddings_created += 1
            self._stats.total_cost_usd += estimated_cost
            return EmbeddingDecision(
                should_embed=True, reason="forced",
                estimated_cost=estimated_cost
            )

        # 1. 기존 레코드 확인 (재사용 가능?)
        existing = self._registry.get(content_hash)
        if existing and not existing.is_expired:
            self._stats.embeddings_reused += 1
            self._stats.total_saved_usd += estimated_cost
            return EmbeddingDecision(
                should_embed=False,
                reason="cache_hit_unexpired",
                reuse_hash=content_hash,
                cost_saved=estimated_cost,
            )

        # 2. 의미 중복 확인
        is_dup, dup_node = self._deduplicator.is_duplicate(content, node_id)
        if is_dup:
            self._stats.duplicates_detected += 1
            self._stats.total_saved_usd += estimated_cost
            return EmbeddingDecision(
                should_embed=False,
                reason=f"semantic_duplicate_of:{dup_node}",
                reuse_hash=content_hash,
                cost_saved=estimated_cost,
            )

        # 3. 저가치 콘텐츠 억제
        value = self._estimate_content_value(content, tier, abstraction_level)
        if value < MIN_EMBEDDING_VALUE:
            self._stats.embeddings_skipped += 1
            return EmbeddingDecision(
                should_embed=False,
                reason=f"low_value:{value:.2f}",
                cost_saved=estimated_cost,
            )

        # 4. 임베딩 허용
        self._register_new(content_hash, node_id, tier, abstraction_level, token_count)
        self._stats.embeddings_created += 1
        self._stats.total_cost_usd += estimated_cost
        return EmbeddingDecision(
            should_embed=True,
            reason="new_high_value_content",
            estimated_cost=estimated_cost,
        )

    def _register_new(
        self, content_hash: str, node_id: str,
        tier: str, abstraction_level: int, token_count: int
    ):
        record = EmbeddingRecord(
            content_hash=content_hash,
            node_id=node_id,
            tier=tier,
            created_at=time.time(),
            last_accessed=time.time(),
            token_count=token_count,
            abstraction_level=abstraction_level,
        )
        self._registry.put(record)

    def _estimate_content_value(
        self, content: str, tier: str, abstraction_level: int
    ) -> float:
        """콘텐츠 임베딩 가치 추정."""
        score = 0.0
        # 길이 기반 (너무 짧으면 저가치)
        if len(content) > 500:
            score += 0.3
        if len(content) > 2000:
            score += 0.2
        # 티어 기반
        tier_scores = {"hot": 0.4, "warm": 0.2, "cold": 0.05}
        score += tier_scores.get(tier, 0.1)
        # 추상화 레벨 기반 (높을수록 재사용 가치 높음)
        score += abstraction_level * 0.1
        return min(score, 1.0)

    def run_maintenance(self) -> dict:
        """주기적 유지보수 (만료/저가치 임베딩 제거)."""
        evicted_stale = self._registry.evict_stale()
        evicted_low   = self._registry.evict_low_value()
        self._stats.stale_evicted += evicted_stale + evicted_low
        return {
            "evicted_stale": evicted_stale,
            "evicted_low_value": evicted_low,
            "registry_size": len(self._registry),
        }

    def get_stats(self) -> dict:
        total = max(self._stats.total_requests, 1)
        reg_stats = self._registry.stats()
        return {
            "total_requests":      self._stats.total_requests,
            "embeddings_created":  self._stats.embeddings_created,
            "embeddings_reused":   self._stats.embeddings_reused,
            "embeddings_skipped":  self._stats.embeddings_skipped,
            "duplicates_detected": self._stats.duplicates_detected,
            "stale_evicted":       self._stats.stale_evicted,
            "reuse_rate":          round(self._stats.embeddings_reused / total, 3),
            "dup_rate":            round(self._stats.duplicates_detected / total, 3),
            "skip_rate":           round(self._stats.embeddings_skipped / total, 3),
            "total_cost_usd":      round(self._stats.total_cost_usd, 6),
            "total_saved_usd":     round(self._stats.total_saved_usd, 6),
            "registry":            reg_stats,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 3-Tier Memory Manager
# ══════════════════════════════════════════════════════════════════════════════

class MemoryTierManager:
    """
    3-Tier 메모리 계층화 관리자.
    Hot → Warm → Cold 자동 강등/승격.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "memory_tiers.json"
        self._tiers: dict[str, dict] = {"hot": {}, "warm": {}, "cold": {}}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._tiers = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._tiers = {"hot": {}, "warm": {}, "cold": {}}

    def _save(self):
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._tiers, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            pass

    def promote(self, node_id: str, content_summary: str, reason: str = ""):
        """노드를 Hot 티어로 승격."""
        # 다른 티어에서 제거
        for tier in ("warm", "cold"):
            self._tiers[tier].pop(node_id, None)
        self._tiers["hot"][node_id] = {
            "summary": content_summary[:200],
            "promoted_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "access_count": self._get_access_count(node_id) + 1,
        }
        self._save()

    def demote(self, node_id: str):
        """Hot → Warm → Cold 강등."""
        if node_id in self._tiers["hot"]:
            data = self._tiers["hot"].pop(node_id)
            self._tiers["warm"][node_id] = data
        elif node_id in self._tiers["warm"]:
            data = self._tiers["warm"].pop(node_id)
            self._tiers["cold"][node_id] = data
        self._save()

    def get_tier(self, node_id: str) -> str:
        for tier in ("hot", "warm", "cold"):
            if node_id in self._tiers[tier]:
                return tier
        return "warm"  # 기본값

    def get_hot_nodes(self) -> list[str]:
        return list(self._tiers["hot"].keys())

    def get_warm_nodes(self) -> list[str]:
        return list(self._tiers["warm"].keys())

    def run_tier_maintenance(self) -> dict:
        """
        자동 티어 조정:
        - Hot: 7일 이상 미접근 → Warm 강등
        - Warm: 90일 이상 미접근 → Cold 강등
        """
        demoted = 0
        now = datetime.utcnow()

        for node_id, data in list(self._tiers["hot"].items()):
            promoted_at = data.get("promoted_at", "")
            if promoted_at:
                try:
                    age = (now - datetime.fromisoformat(promoted_at)).days
                    if age > 7 and data.get("access_count", 0) < 3:
                        self.demote(node_id)
                        demoted += 1
                except Exception:
                    pass

        for node_id, data in list(self._tiers["warm"].items()):
            promoted_at = data.get("promoted_at", "")
            if promoted_at:
                try:
                    age = (now - datetime.fromisoformat(promoted_at)).days
                    if age > 90:
                        self.demote(node_id)
                        demoted += 1
                except Exception:
                    pass

        return {
            "demoted": demoted,
            "hot_count":  len(self._tiers["hot"]),
            "warm_count": len(self._tiers["warm"]),
            "cold_count": len(self._tiers["cold"]),
        }

    def get_stats(self) -> dict:
        return {
            "hot_count":  len(self._tiers["hot"]),
            "warm_count": len(self._tiers["warm"]),
            "cold_count": len(self._tiers["cold"]),
            "total":      sum(len(v) for v in self._tiers.values()),
        }

    def _get_access_count(self, node_id: str) -> int:
        for tier in ("hot", "warm", "cold"):
            if node_id in self._tiers[tier]:
                return self._tiers[tier][node_id].get("access_count", 0)
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# Singletons
# ══════════════════════════════════════════════════════════════════════════════

_emb_gov: Optional[EmbeddingGovernanceEngine] = None
_mem_tier: Optional[MemoryTierManager] = None


def get_embedding_governance() -> EmbeddingGovernanceEngine:
    global _emb_gov
    if _emb_gov is None:
        _emb_gov = EmbeddingGovernanceEngine()
    return _emb_gov


def get_memory_tier_manager() -> MemoryTierManager:
    global _mem_tier
    if _mem_tier is None:
        _mem_tier = MemoryTierManager()
    return _mem_tier
