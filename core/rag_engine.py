"""
rag_engine.py — ROS v5.0 RAG Cost Optimization Architecture
=============================================================
Philosophy: "Maximum scientific cognition with minimum retrieval and inference cost."

Core Principles:
  1. Cheapest-Cognition-First Policy
  2. 4-Layer Hierarchical Retrieval
  3. Token Budget Orchestration
  4. Semantic Retrieval Radius Minimization
  5. Selective Retrieval (not all memory deserves retrieval)
"""

from __future__ import annotations

import hashlib
import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = _get_logger("ROS.RAG")


# ══════════════════════════════════════════════════════════════════════════════
# Enums & Constants
# ══════════════════════════════════════════════════════════════════════════════

class CognitionPath(Enum):
    """Cheapest-Cognition-First 우선순위 (낮을수록 저렴)."""
    CACHED_ABSTRACTION  = 1   # 캐시된 의미 추상화 (무료)
    CACHED_RETRIEVAL    = 2   # 캐시된 검색 결과 (무료)
    LOCAL_GRAPH         = 3   # 로컬 그래프 순회 (매우 저렴)
    EMBEDDING_SEARCH    = 4   # 임베딩 유사도 검색 (저렴)
    SMALL_MODEL         = 5   # 소형 로컬 모델 추론 (중간)
    LARGE_CLOUD         = 6   # 대형 클라우드 LLM (비쌈)


class RetrievalLayer(Enum):
    """4-Layer 계층적 검색."""
    L1_GLOBAL   = "global_abstraction"    # 연구 프로그램, 주요 테마
    L2_CLUSTER  = "topic_cluster"         # 방법론 클러스터, 도메인
    L3_LOCAL    = "local_neighborhood"    # 인근 그래프 노드, 계보
    L4_ATOMIC   = "atomic_note"           # 정확한 개념, 수식, 가정


class MemoryTier(Enum):
    """3-Tier 메모리 계층."""
    HOT  = "hot"    # 활성 연구, 미해결 긴장
    WARM = "warm"   # 안정적 추상화, 자주 참조되는 방법
    COLD = "cold"   # 역사적 노트, 저빈도 개념


# 토큰 예산 기본값
DEFAULT_TOKEN_BUDGET = {
    "total":     8000,   # 전체 컨텍스트 예산
    "retrieval": 3000,   # 검색 결과 예산
    "graph":     1500,   # 그래프 순회 예산
    "history":   1000,   # 대화 히스토리 예산
    "system":    500,    # 시스템 프롬프트 예산
}

# 검색 반경 제한
MAX_RETRIEVAL_RADIUS = {
    RetrievalLayer.L1_GLOBAL:  5,    # 글로벌 추상화 최대 5개
    RetrievalLayer.L2_CLUSTER: 10,   # 클러스터 최대 10개
    RetrievalLayer.L3_LOCAL:   15,   # 로컬 이웃 최대 15개
    RetrievalLayer.L4_ATOMIC:  20,   # 원자 노트 최대 20개
}

# Guardrails for desktop vaults that can grow into tens of thousands of notes.
MAX_RAG_SCAN_MULTIPLIER = 3
MAX_RAG_FILE_BYTES = 512 * 1024
MAX_RAG_CONTENT_CHARS = 16_000

# 검색 후보 랭킹 가중치
RANKING_WEIGHTS = {
    "semantic_relevance":    0.30,
    "contradiction_import":  0.15,
    "tension_relevance":     0.15,
    "math_centrality":       0.10,
    "lineage_importance":    0.10,
    "trust_score":           0.10,
    "recency_decay":         0.05,
    "abstraction_density":   0.05,
}


# ══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetrievalCandidate:
    """검색 후보 노드."""
    node_id:             str
    content:             str
    layer:               str
    tier:                str = MemoryTier.WARM.value
    semantic_relevance:  float = 0.0
    contradiction_import: float = 0.0
    tension_relevance:   float = 0.0
    math_centrality:     float = 0.0
    lineage_importance:  float = 0.0
    trust_score:         float = 1.0
    recency_decay:       float = 1.0
    abstraction_density: float = 0.5
    token_count:         int   = 0

    @property
    def composite_score(self) -> float:
        return sum(
            RANKING_WEIGHTS[k] * getattr(self, k, 0.0)
            for k in RANKING_WEIGHTS
        )

    @property
    def cost_efficiency(self) -> float:
        """단위 토큰당 가치."""
        if self.token_count == 0:
            return 0.0
        return self.composite_score / max(self.token_count, 1)


@dataclass
class RetrievalPlan:
    """검색 실행 계획."""
    query:          str
    cognition_path: str
    layers_needed:  list[str]
    token_budget:   dict
    candidates:     list[RetrievalCandidate] = field(default_factory=list)
    selected:       list[RetrievalCandidate] = field(default_factory=list)
    total_tokens:   int = 0
    cache_hit:      bool = False
    cost_saved:     float = 0.0   # 절약된 추정 비용 (USD)
    created_at:     str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RAGMetrics:
    """RAG 관측성 메트릭."""
    total_queries:          int = 0
    cache_hits:             int = 0
    graph_traversals:       int = 0
    embedding_searches:     int = 0
    llm_calls:              int = 0
    total_tokens_used:      int = 0
    total_tokens_saved:     int = 0
    retrieval_waste_ratio:  float = 0.0   # 사용되지 않은 검색 비율
    token_per_insight:      float = 0.0
    embedding_dup_rate:     float = 0.0
    context_redundancy:     float = 0.0
    avg_retrieval_latency:  float = 0.0
    retrieval_entropy:      float = 0.0
    cost_saved_usd:         float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Token Budget Manager
# ══════════════════════════════════════════════════════════════════════════════

class TokenBudgetManager:
    """토큰 예산 오케스트레이션."""

    def __init__(self, budget: Optional[dict] = None):
        self._budget = budget or DEFAULT_TOKEN_BUDGET.copy()
        self._used: dict[str, int] = {k: 0 for k in self._budget}

    def allocate(self, category: str, tokens: int) -> bool:
        """토큰 할당 시도. 예산 초과 시 False."""
        if category not in self._budget:
            return True
        if self._used[category] + tokens > self._budget[category]:
            logger.warning(f"Token budget exceeded: {category} ({self._used[category]+tokens}/{self._budget[category]})")
            return False
        self._used[category] += tokens
        return True

    def remaining(self, category: str) -> int:
        return self._budget.get(category, 0) - self._used.get(category, 0)

    def total_remaining(self) -> int:
        return self._budget["total"] - sum(self._used.values())

    def utilization(self) -> dict:
        return {k: self._used[k] / max(self._budget[k], 1) for k in self._budget}

    def reset(self):
        self._used = {k: 0 for k in self._budget}

    def snapshot(self) -> dict:
        return {
            "budget": self._budget.copy(),
            "used":   self._used.copy(),
            "remaining": {k: self._budget[k] - self._used[k] for k in self._budget},
        }


# ══════════════════════════════════════════════════════════════════════════════
# Retrieval Ranker
# ══════════════════════════════════════════════════════════════════════════════

class RetrievalRanker:
    """검색 후보 랭킹 및 저가치 검색 억제."""

    # 최소 복합 점수 임계값 (이하 억제)
    MIN_COMPOSITE_SCORE = 0.15
    # 최소 신뢰 점수
    MIN_TRUST_SCORE = 0.3

    def rank(
        self,
        candidates: list[RetrievalCandidate],
        token_budget: int,
        top_k: int = 20,
    ) -> list[RetrievalCandidate]:
        """
        후보를 랭킹하고 토큰 예산 내에서 최고 가치 후보 선택.
        저가치 검색은 억제.
        """
        # 1. 저가치 필터링
        filtered = [
            c for c in candidates
            if c.composite_score >= self.MIN_COMPOSITE_SCORE
            and c.trust_score >= self.MIN_TRUST_SCORE
        ]

        # 2. 비용 효율 기반 정렬
        ranked = sorted(filtered, key=lambda c: c.cost_efficiency, reverse=True)

        # 3. 토큰 예산 내 탐욕적 선택
        selected = []
        used_tokens = 0
        for candidate in ranked[:top_k * 2]:
            if used_tokens + candidate.token_count > token_budget:
                continue
            selected.append(candidate)
            used_tokens += candidate.token_count
            if len(selected) >= top_k:
                break

        return selected

    def compute_retrieval_entropy(self, candidates: list[RetrievalCandidate]) -> float:
        """검색 엔트로피 계산 (낮을수록 정밀)."""
        if not candidates:
            return 0.0
        scores = [c.composite_score for c in candidates]
        total = sum(scores)
        if total == 0:
            return 0.0
        probs = [s / total for s in scores]
        return -sum(p * math.log2(p + 1e-10) for p in probs)


# ══════════════════════════════════════════════════════════════════════════════
# Cheapest Cognition Router
# ══════════════════════════════════════════════════════════════════════════════

class CheapestCognitionRouter:
    """
    Cheapest-Cognition-First 정책 라우터.
    가장 저렴한 유효 인지 경로를 선택.
    """

    def __init__(self, cache_engine=None):
        self._cache = cache_engine
        self._decision_log: list[dict] = []

    def decide(
        self,
        query: str,
        model: str,
        vault_path: str,
        force_llm: bool = False,
    ) -> tuple[CognitionPath, Any]:
        """
        인지 경로 결정.
        Returns: (path, cached_result_or_None)
        """
        # 1. 캐시된 의미 추상화 확인 (무료)
        if self._cache and not force_llm:
            cache_key = hashlib.md5(f"{query[:200]}{model}".encode()).hexdigest()
            cached = self._cache.get_analysis(cache_key, model)
            if cached:
                self._log_decision(CognitionPath.CACHED_ABSTRACTION, query, "cache_hit")
                return CognitionPath.CACHED_ABSTRACTION, cached

        # 2. 로컬 그래프 순회 가능 여부 확인
        if vault_path and Path(vault_path).exists():
            note_count = len(list(Path(vault_path).rglob("*.md")))
            if note_count > 0:
                self._log_decision(CognitionPath.LOCAL_GRAPH, query, f"graph_available:{note_count}")
                # 그래프가 있으면 L1-L3 검색 먼저 시도
                return CognitionPath.LOCAL_GRAPH, None

        # 3. 클라우드 LLM 폴백
        self._log_decision(CognitionPath.LARGE_CLOUD, query, "no_local_context")
        return CognitionPath.LARGE_CLOUD, None

    def _log_decision(self, path: CognitionPath, query: str, reason: str):
        self._decision_log.append({
            "path": path.name,
            "query_hash": hashlib.md5(query[:50].encode()).hexdigest()[:8],
            "reason": reason,
            "ts": datetime.utcnow().isoformat(),
        })
        if len(self._decision_log) > 1000:
            self._decision_log = self._decision_log[-500:]

    def get_path_distribution(self) -> dict:
        """인지 경로 분포 통계."""
        dist: dict[str, int] = {}
        for entry in self._decision_log:
            dist[entry["path"]] = dist.get(entry["path"], 0) + 1
        return dist


# ══════════════════════════════════════════════════════════════════════════════
# Hierarchical Retriever
# ══════════════════════════════════════════════════════════════════════════════

class HierarchicalRetriever:
    """
    4-Layer 계층적 검색기.
    검색 반경을 최소화하면서 최대 의미 정밀도 달성.
    """

    def __init__(self, vault_path: str = ""):
        self._vault = Path(vault_path) if vault_path else None
        self._ranker = RetrievalRanker()

    def retrieve(
        self,
        query: str,
        token_budget: int = 3000,
        layers: Optional[list[RetrievalLayer]] = None,
        memory_tier_filter: Optional[list[MemoryTier]] = None,
    ) -> list[RetrievalCandidate]:
        """
        계층적 검색 실행.
        상위 레이어부터 시작하여 필요 시 하위 레이어로 내려감.
        """
        if not self._vault or not self._vault.exists():
            return []

        layers = layers or [
            RetrievalLayer.L1_GLOBAL,
            RetrievalLayer.L2_CLUSTER,
            RetrievalLayer.L3_LOCAL,
            RetrievalLayer.L4_ATOMIC,
        ]

        all_candidates: list[RetrievalCandidate] = []
        remaining_budget = token_budget

        for layer in layers:
            if remaining_budget <= 0:
                break

            layer_candidates = self._retrieve_layer(
                query, layer,
                max_count=MAX_RETRIEVAL_RADIUS[layer],
                token_budget=remaining_budget,
            )

            # 메모리 티어 필터
            if memory_tier_filter:
                layer_candidates = [
                    c for c in layer_candidates
                    if c.tier in [t.value for t in memory_tier_filter]
                ]

            all_candidates.extend(layer_candidates)
            used = sum(c.token_count for c in layer_candidates)
            remaining_budget -= used

            # L1/L2에서 충분한 컨텍스트 확보 시 하위 레이어 스킵
            if layer in (RetrievalLayer.L1_GLOBAL, RetrievalLayer.L2_CLUSTER):
                if len(all_candidates) >= 5 and remaining_budget < token_budget * 0.3:
                    logger.info(f"Early stopping at {layer.value}: sufficient context")
                    break

        # 최종 랭킹
        return self._ranker.rank(all_candidates, token_budget)

    def _retrieve_layer(
        self,
        query: str,
        layer: RetrievalLayer,
        max_count: int,
        token_budget: int,
    ) -> list[RetrievalCandidate]:
        """레이어별 검색 구현 (Obsidian 볼트 기반)."""
        if not self._vault:
            return []

        candidates = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        # 레이어별 폴더 매핑
        layer_folders = {
            RetrievalLayer.L1_GLOBAL:  ["_INDEX.md", "Papers/_INDEX.md"],
            RetrievalLayer.L2_CLUSTER: ["Papers/Econometrics", "Papers/MachineLearning",
                                        "Papers/Statistics", "Papers/GeneralEconomics"],
            RetrievalLayer.L3_LOCAL:   ["Papers"],
            RetrievalLayer.L4_ATOMIC:  [],  # 전체 볼트 검색
        }

        md_files = self._iter_layer_files(layer, layer_folders, max_count)

        for md_file in md_files:
            try:
                if self._should_skip_file(md_file):
                    continue
                content = self._read_text_limited(md_file)
                if not content.strip():
                    continue

                # 의미 관련성 점수 (간단한 키워드 기반)
                content_lower = content.lower()
                matched_terms = sum(1 for t in query_terms if t in content_lower and len(t) > 3)
                semantic_relevance = min(matched_terms / max(len(query_terms), 1), 1.0)

                if semantic_relevance < 0.05 and layer == RetrievalLayer.L4_ATOMIC:
                    continue  # 원자 레이어에서 무관한 노트 스킵

                # 토큰 수 추정 (4자 = 1토큰)
                token_count = len(content) // 4

                # 메모리 티어 추정
                tier = self._estimate_tier(md_file, content)

                # 추상화 밀도 추정
                abstraction_density = self._estimate_abstraction_density(content)

                candidate = RetrievalCandidate(
                    node_id=str(md_file.relative_to(self._vault)),
                    content=content[:2000],  # 최대 2000자만 저장
                    layer=layer.value,
                    tier=tier,
                    semantic_relevance=semantic_relevance,
                    trust_score=0.9,
                    recency_decay=self._compute_recency_decay(md_file),
                    abstraction_density=abstraction_density,
                    token_count=min(token_count, 500),  # 노트당 최대 500토큰
                )
                candidates.append(candidate)

                if len(candidates) >= max_count:
                    break

            except Exception as e:
                logger.debug("Skipping RAG candidate %s: %s", md_file, e)
                continue

        return candidates

    def _iter_layer_files(
        self,
        layer: RetrievalLayer,
        layer_folders: dict[RetrievalLayer, list[str]],
        max_count: int,
    ):
        """Yield a bounded stream of candidate markdown files without materializing the vault."""
        limit = max_count * MAX_RAG_SCAN_MULTIPLIER
        yielded = 0

        if layer == RetrievalLayer.L4_ATOMIC:
            for md_file in self._vault.rglob("*.md"):
                if yielded >= limit:
                    break
                if md_file.is_symlink():
                    continue
                yielded += 1
                yield md_file
            return

        for folder_hint in layer_folders.get(layer, []):
            if yielded >= limit:
                break
            target = self._vault / folder_hint
            if target.is_symlink():
                continue
            if target.is_file() and target.suffix.lower() == ".md":
                yielded += 1
                yield target
            elif target.is_dir():
                for md_file in target.glob("*.md"):
                    if yielded >= limit:
                        break
                    if md_file.is_symlink():
                        continue
                    yielded += 1
                    yield md_file

    def _should_skip_file(self, md_file: Path) -> bool:
        try:
            return md_file.stat().st_size > MAX_RAG_FILE_BYTES
        except OSError:
            return True

    def _read_text_limited(self, md_file: Path) -> str:
        with md_file.open("r", encoding="utf-8", errors="ignore") as f:
            return f.read(MAX_RAG_CONTENT_CHARS)

    def _estimate_tier(self, md_file: Path, content: str) -> str:
        """메모리 티어 추정."""
        # 최근 수정 시간 기반
        try:
            mtime = md_file.stat().st_mtime
            age_days = (time.time() - mtime) / 86400
            if age_days < 7:
                return MemoryTier.HOT.value
            elif age_days < 90:
                return MemoryTier.WARM.value
            else:
                return MemoryTier.COLD.value
        except Exception:
            return MemoryTier.WARM.value

    def _estimate_abstraction_density(self, content: str) -> float:
        """추상화 밀도 추정 (수식, WikiLink, 방법론 키워드 기반)."""
        score = 0.0
        # LaTeX 수식
        import re
        score += min(len(re.findall(r'\$[^$]+\$', content)) * 0.05, 0.3)
        # WikiLink
        score += min(len(re.findall(r'\[\[[^\]]+\]\]', content)) * 0.03, 0.2)
        # 방법론 키워드
        econ_keywords = ["DML", "IV", "DID", "RDD", "OLS", "GMM", "CATE", "ATE",
                         "causal", "identification", "estimator", "assumption"]
        score += min(sum(1 for k in econ_keywords if k.lower() in content.lower()) * 0.04, 0.3)
        return min(score, 1.0)

    def _compute_recency_decay(self, md_file: Path) -> float:
        """최신성 감쇠 계산 (지수 감쇠)."""
        try:
            mtime = md_file.stat().st_mtime
            age_days = (time.time() - mtime) / 86400
            return math.exp(-age_days / 180)  # 180일 반감기
        except Exception:
            return 0.5


# ══════════════════════════════════════════════════════════════════════════════
# RAG Context Builder
# ══════════════════════════════════════════════════════════════════════════════

class RAGContextBuilder:
    """
    검색 결과를 LLM 컨텍스트로 조립.
    토큰 예산 내에서 최고 가치 컨텍스트 구성.
    """

    def build(
        self,
        candidates: list[RetrievalCandidate],
        token_budget: int = 3000,
        include_metadata: bool = True,
    ) -> str:
        """
        선택된 후보들을 컨텍스트 문자열로 조립.
        상위 레이어 → 하위 레이어 순서로 배치.
        """
        if not candidates:
            return ""

        # 레이어 순서로 정렬
        layer_order = {
            RetrievalLayer.L1_GLOBAL.value: 0,
            RetrievalLayer.L2_CLUSTER.value: 1,
            RetrievalLayer.L3_LOCAL.value: 2,
            RetrievalLayer.L4_ATOMIC.value: 3,
        }
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (layer_order.get(c.layer, 4), -c.composite_score)
        )

        sections = []
        used_tokens = 0

        # 레이어별 섹션 헤더
        current_layer = None
        for c in sorted_candidates:
            if used_tokens >= token_budget:
                break

            if c.layer != current_layer:
                current_layer = c.layer
                layer_label = {
                    RetrievalLayer.L1_GLOBAL.value:  "## 🌐 Global Context",
                    RetrievalLayer.L2_CLUSTER.value: "## 📚 Domain Cluster",
                    RetrievalLayer.L3_LOCAL.value:   "## 🔗 Local Neighborhood",
                    RetrievalLayer.L4_ATOMIC.value:  "## ⚛️ Atomic Notes",
                }.get(c.layer, f"## {c.layer}")
                sections.append(layer_label)

            # 메타데이터 헤더
            if include_metadata:
                header = (
                    f"### [{c.node_id}] "
                    f"(relevance={c.semantic_relevance:.2f}, "
                    f"tier={c.tier}, "
                    f"score={c.composite_score:.2f})"
                )
                sections.append(header)

            # 컨텐츠 (토큰 예산 내)
            content_tokens = c.token_count
            if used_tokens + content_tokens > token_budget:
                # 남은 예산만큼만 포함
                remaining_chars = (token_budget - used_tokens) * 4
                sections.append(c.content[:remaining_chars] + "\n...[truncated]")
                used_tokens = token_budget
            else:
                sections.append(c.content)
                used_tokens += content_tokens

        return "\n\n".join(sections)


# ══════════════════════════════════════════════════════════════════════════════
# RAG Engine (메인 진입점)
# ══════════════════════════════════════════════════════════════════════════════

class RAGEngine:
    """
    ROS v5.0 RAG 비용 최적화 엔진.
    모든 RAG 작업의 단일 진입점.
    """

    def __init__(self, vault_path: str = "", cache_engine=None):
        self._vault_path   = vault_path
        self._retriever    = HierarchicalRetriever(vault_path)
        self._ranker       = RetrievalRanker()
        self._router       = CheapestCognitionRouter(cache_engine)
        self._context_builder = RAGContextBuilder()
        self._budget_mgr   = TokenBudgetManager()
        self._metrics      = RAGMetrics()
        self._cache        = cache_engine
        self._plans: list[RetrievalPlan] = []

    def set_vault_path(self, vault_path: str):
        self._vault_path = vault_path
        self._retriever  = HierarchicalRetriever(vault_path)

    def prepare_context(
        self,
        query: str,
        model: str = "gpt-4o-mini",
        token_budget: Optional[dict] = None,
        force_llm: bool = False,
        hot_only: bool = False,
    ) -> tuple[str, RetrievalPlan]:
        """
        쿼리에 대한 최적 RAG 컨텍스트 준비.

        Returns:
            (context_string, retrieval_plan)
        """
        t0 = time.time()
        self._metrics.total_queries += 1
        self._budget_mgr.reset()

        budget = token_budget or DEFAULT_TOKEN_BUDGET.copy()

        # 1. 인지 경로 결정 (Cheapest-First)
        path, cached = self._router.decide(query, model, self._vault_path, force_llm)

        plan = RetrievalPlan(
            query=query[:200],
            cognition_path=path.name,
            layers_needed=[],
            token_budget=budget,
        )

        # 2. 캐시 히트 처리
        if path == CognitionPath.CACHED_ABSTRACTION and cached:
            self._metrics.cache_hits += 1
            plan.cache_hit = True
            plan.cost_saved = self._estimate_cost_saved(len(cached) // 4, model)
            self._metrics.cost_saved_usd += plan.cost_saved
            self._plans.append(plan)
            return cached, plan

        # 3. 로컬 그래프 검색
        tier_filter = [MemoryTier.HOT] if hot_only else None
        candidates = self._retriever.retrieve(
            query,
            token_budget=budget.get("retrieval", 3000),
            memory_tier_filter=tier_filter,
        )

        plan.candidates = candidates
        self._metrics.graph_traversals += 1

        # 4. 랭킹 및 선택
        selected = self._ranker.rank(
            candidates,
            token_budget=budget.get("retrieval", 3000),
        )
        plan.selected = selected
        plan.total_tokens = sum(c.token_count for c in selected)

        # 5. 컨텍스트 조립
        context = self._context_builder.build(
            selected,
            token_budget=budget.get("retrieval", 3000),
        )

        # 6. 검색 낭비 비율 업데이트
        if candidates:
            waste = 1.0 - len(selected) / len(candidates)
            self._metrics.retrieval_waste_ratio = (
                self._metrics.retrieval_waste_ratio * 0.9 + waste * 0.1
            )

        # 7. 검색 엔트로피
        self._metrics.retrieval_entropy = self._ranker.compute_retrieval_entropy(selected)

        # 8. 평균 지연 업데이트
        latency = time.time() - t0
        self._metrics.avg_retrieval_latency = (
            self._metrics.avg_retrieval_latency * 0.9 + latency * 0.1
        )

        plan.layers_needed = list({c.layer for c in selected})
        self._plans.append(plan)

        # 캐시 저장 (다음 동일 쿼리 대비)
        if self._cache and context:
            cache_key = hashlib.md5(f"{query[:200]}{model}".encode()).hexdigest()
            # 컨텍스트 자체는 캐시하지 않음 (분석 결과만 캐시)

        return context, plan

    def get_metrics(self) -> RAGMetrics:
        return self._metrics

    def get_metrics_dict(self) -> dict:
        m = self._metrics
        total = max(m.total_queries, 1)
        return {
            "total_queries":         m.total_queries,
            "cache_hit_rate":        round(m.cache_hits / total, 3),
            "graph_traversal_rate":  round(m.graph_traversals / total, 3),
            "retrieval_waste_ratio": round(m.retrieval_waste_ratio, 3),
            "avg_latency_ms":        round(m.avg_retrieval_latency * 1000, 1),
            "retrieval_entropy":     round(m.retrieval_entropy, 3),
            "cost_saved_usd":        round(m.cost_saved_usd, 4),
            "total_tokens_saved":    m.total_tokens_saved,
            "path_distribution":     self._router.get_path_distribution(),
        }

    def get_budget_snapshot(self) -> dict:
        return self._budget_mgr.snapshot()

    def _estimate_cost_saved(self, tokens: int, model: str) -> float:
        """캐시 히트로 절약된 추정 비용 (USD)."""
        # 대략적인 토큰 단가 (per 1K tokens)
        rates = {
            "gpt-4o":       0.005,
            "gpt-4o-mini":  0.00015,
            "deepseek":     0.00014,
            "qwen":         0.0002,
            "default":      0.001,
        }
        rate = next((v for k, v in rates.items() if k in model.lower()), rates["default"])
        return tokens / 1000 * rate

    def get_recent_plans(self, n: int = 10) -> list[dict]:
        """최근 검색 계획 반환."""
        return [
            {
                "query":         p.query[:80],
                "path":          p.cognition_path,
                "layers":        p.layers_needed,
                "tokens":        p.total_tokens,
                "cache_hit":     p.cache_hit,
                "cost_saved":    round(p.cost_saved, 5),
                "candidates":    len(p.candidates),
                "selected":      len(p.selected),
                "created_at":    p.created_at,
            }
            for p in self._plans[-n:]
        ]


# ══════════════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════════════

_rag_engine: Optional[RAGEngine] = None


def get_rag_engine(vault_path: str = "", cache_engine=None) -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine(vault_path, cache_engine)
    elif vault_path and _rag_engine._vault_path != vault_path:
        _rag_engine.set_vault_path(vault_path)
    return _rag_engine
