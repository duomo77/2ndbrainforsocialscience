"""
memory_trust.py — ROS v4.0 Memory Trust System
================================================
Long-term memory must be protected from:
  - Memory poisoning
  - Hallucinated abstraction reinforcement
  - Low-confidence semantic drift
  - Recursive hallucination loops

Implements:
  - Memory trust layers (verified / probable / uncertain / quarantined)
  - Memory aging (confidence decay over time)
  - Semantic confidence scoring
  - Retrieval quality scoring
  - Contradiction-aware memory ranking
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
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

logger = _get_logger("ROS.MemoryTrust")


# ══════════════════════════════════════════════════════════════════════════════
# Trust Layers
# ══════════════════════════════════════════════════════════════════════════════

class MemoryTrustLayer(Enum):
    VERIFIED     = "verified"      # 검증된 학술 사실 (score ≥ 0.85)
    PROBABLE     = "probable"      # 높은 신뢰도 (0.65 ~ 0.84)
    UNCERTAIN    = "uncertain"     # 불확실 (0.35 ~ 0.64)
    QUARANTINED  = "quarantined"   # 격리 (< 0.35 또는 모순 감지)


LAYER_THRESHOLDS = {
    MemoryTrustLayer.VERIFIED:    0.85,
    MemoryTrustLayer.PROBABLE:    0.65,
    MemoryTrustLayer.UNCERTAIN:   0.35,
    MemoryTrustLayer.QUARANTINED: 0.0,
}

LAYER_ICONS = {
    MemoryTrustLayer.VERIFIED:    "✅",
    MemoryTrustLayer.PROBABLE:    "🔵",
    MemoryTrustLayer.UNCERTAIN:   "🟡",
    MemoryTrustLayer.QUARANTINED: "🔴",
}

# 신뢰도 감쇠 파라미터
DECAY_HALF_LIFE_DAYS = 90   # 90일마다 신뢰도 50% 감쇠
MIN_TRUST_SCORE      = 0.05 # 최소 신뢰도 (완전 소멸 방지)
RETRIEVAL_BOOST      = 0.05 # 검색될 때마다 신뢰도 소폭 증가


# ══════════════════════════════════════════════════════════════════════════════
# Memory Record
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryRecord:
    memory_id:     str
    content:       str          # 핵심 명제 또는 개념
    source:        str          # 출처 (논문 제목, URL 등)
    source_type:   str          # paper | transcript | dataset | user_input
    trust_score:   float        # 0.0 ~ 1.0
    trust_layer:   str          # MemoryTrustLayer.value
    created_at:    str
    last_accessed: str
    access_count:  int = 0
    contradiction_count: int = 0
    is_quarantined: bool = False
    decay_applied: bool = False
    tags:          list[str] = field(default_factory=list)
    related_ids:   list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Memory Store
# ══════════════════════════════════════════════════════════════════════════════

class MemoryStore:
    def __init__(self, data_dir: Path):
        self._path = data_dir / "memory_trust.json"
        self._records: dict[str, MemoryRecord] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for r in data:
                    self._records[r["memory_id"]] = MemoryRecord(**r)
            except Exception as ex:
                logger.error(f"MemoryStore load error: {ex}")

    def save(self):
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([asdict(r) for r in self._records.values()], indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self._records.get(memory_id)

    def upsert(self, record: MemoryRecord):
        self._records[record.memory_id] = record

    def all_records(self) -> list[MemoryRecord]:
        return list(self._records.values())

    def by_layer(self, layer: MemoryTrustLayer) -> list[MemoryRecord]:
        return [r for r in self._records.values() if r.trust_layer == layer.value]

    def quarantined(self) -> list[MemoryRecord]:
        return [r for r in self._records.values() if r.is_quarantined]


# ══════════════════════════════════════════════════════════════════════════════
# Trust Scorer
# ══════════════════════════════════════════════════════════════════════════════

class MemoryTrustScorer:
    """메모리 항목의 신뢰도 점수 계산."""

    SOURCE_BASE_SCORES = {
        "paper":       0.90,   # 동료 심사 논문
        "dataset":     0.85,   # 공식 데이터셋
        "transcript":  0.60,   # 강의/회의 녹취
        "user_input":  0.50,   # 사용자 직접 입력
        "llm_output":  0.45,   # LLM 생성 내용
        "unknown":     0.40,
    }

    def initial_score(self, source_type: str, content: str) -> float:
        base = self.SOURCE_BASE_SCORES.get(source_type, 0.40)
        # 내용 길이 보너스 (짧은 내용은 덜 신뢰)
        length_bonus = min(len(content) / 5000, 0.10)
        # 수식 포함 보너스 (수학적 엄밀성)
        math_bonus = 0.05 if any(c in content for c in ["$", "\\", "∀", "∃", "⊥"]) else 0.0
        return min(base + length_bonus + math_bonus, 1.0)

    def apply_decay(self, record: MemoryRecord) -> float:
        """시간 기반 신뢰도 감쇠 (지수 감쇠)."""
        created = datetime.fromisoformat(record.created_at)
        days_elapsed = (datetime.utcnow() - created).days
        if days_elapsed <= 0:
            return record.trust_score
        decay_factor = math.exp(
            -math.log(2) * days_elapsed / DECAY_HALF_LIFE_DAYS
        )
        new_score = max(record.trust_score * decay_factor, MIN_TRUST_SCORE)
        return round(new_score, 4)

    def apply_contradiction_penalty(self, score: float, contradiction_count: int) -> float:
        """모순 감지 시 신뢰도 패널티."""
        penalty = min(contradiction_count * 0.15, 0.60)
        return max(score - penalty, MIN_TRUST_SCORE)

    def classify_layer(self, score: float) -> MemoryTrustLayer:
        if score >= LAYER_THRESHOLDS[MemoryTrustLayer.VERIFIED]:
            return MemoryTrustLayer.VERIFIED
        elif score >= LAYER_THRESHOLDS[MemoryTrustLayer.PROBABLE]:
            return MemoryTrustLayer.PROBABLE
        elif score >= LAYER_THRESHOLDS[MemoryTrustLayer.UNCERTAIN]:
            return MemoryTrustLayer.UNCERTAIN
        else:
            return MemoryTrustLayer.QUARANTINED


# ══════════════════════════════════════════════════════════════════════════════
# Memory Trust Engine
# ══════════════════════════════════════════════════════════════════════════════

class MemoryTrustEngine:
    """
    장기 메모리 신뢰 관리 시스템.
    환각 강화 방지 + 신뢰도 감쇠 + 격리 시스템.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.store  = MemoryStore(data_dir)
        self.scorer = MemoryTrustScorer()

    def store_memory(
        self,
        content:     str,
        source:      str,
        source_type: str = "unknown",
        tags:        list[str] = None,
    ) -> MemoryRecord:
        """새 메모리 항목 저장."""
        memory_id = hashlib.sha256(
            f"{source}{content[:100]}".encode()
        ).hexdigest()[:16]

        # 기존 항목 업데이트
        existing = self.store.get(memory_id)
        if existing:
            existing.access_count += 1
            existing.trust_score   = min(
                existing.trust_score + RETRIEVAL_BOOST, 1.0
            )
            existing.last_accessed = datetime.utcnow().isoformat()
            existing.trust_layer   = self.scorer.classify_layer(existing.trust_score).value
            self.store.upsert(existing)
            self.store.save()
            return existing

        # 신규 항목
        init_score = self.scorer.initial_score(source_type, content)
        layer      = self.scorer.classify_layer(init_score)
        now        = datetime.utcnow().isoformat()
        record     = MemoryRecord(
            memory_id     = memory_id,
            content       = content[:2000],
            source        = source,
            source_type   = source_type,
            trust_score   = init_score,
            trust_layer   = layer.value,
            created_at    = now,
            last_accessed = now,
            tags          = tags or [],
        )
        self.store.upsert(record)
        self.store.save()
        return record

    def retrieve(
        self,
        query_tags: list[str] = None,
        min_trust:  float = 0.35,
        limit:      int = 20,
        exclude_quarantined: bool = True,
    ) -> list[MemoryRecord]:
        """
        신뢰도 기반 메모리 검색.
        우선순위: unresolved tensions > active hypotheses > high-confidence abstractions
        """
        records = self.store.all_records()

        # 감쇠 적용
        for r in records:
            if not r.decay_applied:
                r.trust_score  = self.scorer.apply_decay(r)
                r.trust_layer  = self.scorer.classify_layer(r.trust_score).value
                r.decay_applied = True
                r.is_quarantined = (r.trust_layer == MemoryTrustLayer.QUARANTINED.value)
                self.store.upsert(r)

        # 필터링
        filtered = [
            r for r in records
            if r.trust_score >= min_trust
            and (not exclude_quarantined or not r.is_quarantined)
        ]

        # 태그 필터
        if query_tags:
            filtered = [
                r for r in filtered
                if any(t in r.tags for t in query_tags)
            ] or filtered  # 태그 매칭 없으면 전체

        # 정렬: 신뢰도 × 접근 빈도 (환각 강화 방지: 접근 많다고 무조건 높이지 않음)
        def rank(r: MemoryRecord) -> float:
            recency = 1.0 / max(
                (datetime.utcnow() - datetime.fromisoformat(r.last_accessed)).days + 1, 1
            )
            return r.trust_score * 0.7 + recency * 0.3

        filtered.sort(key=rank, reverse=True)
        self.store.save()
        return filtered[:limit]

    def quarantine(self, memory_id: str, reason: str = ""):
        """메모리 항목 격리."""
        r = self.store.get(memory_id)
        if r:
            r.is_quarantined = True
            r.trust_layer    = MemoryTrustLayer.QUARANTINED.value
            r.trust_score    = MIN_TRUST_SCORE
            self.store.upsert(r)
            self.store.save()
            logger.warning(f"Memory quarantined: {memory_id} — {reason}")

    def apply_contradiction_penalty(self, memory_id: str):
        """모순 감지 시 신뢰도 패널티 적용."""
        r = self.store.get(memory_id)
        if r:
            r.contradiction_count += 1
            r.trust_score = self.scorer.apply_contradiction_penalty(
                r.trust_score, r.contradiction_count
            )
            r.trust_layer = self.scorer.classify_layer(r.trust_score).value
            r.is_quarantined = (r.trust_layer == MemoryTrustLayer.QUARANTINED.value)
            self.store.upsert(r)
            self.store.save()

    def run_decay_cycle(self):
        """전체 메모리 감쇠 사이클 실행 (주기적 호출)."""
        records = self.store.all_records()
        decayed = 0
        quarantined_new = 0
        for r in records:
            old_score = r.trust_score
            r.trust_score   = self.scorer.apply_decay(r)
            r.trust_layer   = self.scorer.classify_layer(r.trust_score).value
            r.decay_applied = True
            if old_score != r.trust_score:
                decayed += 1
            if r.trust_layer == MemoryTrustLayer.QUARANTINED.value and not r.is_quarantined:
                r.is_quarantined = True
                quarantined_new += 1
            self.store.upsert(r)
        self.store.save()
        logger.info(f"Decay cycle: {decayed} records decayed, {quarantined_new} newly quarantined")
        return {"decayed": decayed, "quarantined_new": quarantined_new}

    def format_context_injection(self, records: list[MemoryRecord]) -> str:
        """
        Token-economical context injection.
        우선순위: verified > probable > uncertain
        환각 강화 방지: quarantined 항목은 절대 주입하지 않음.
        """
        if not records:
            return ""

        lines = ["## Trusted Memory Context\n"]
        for r in records:
            if r.is_quarantined:
                continue  # 격리 항목 절대 주입 금지
            icon = LAYER_ICONS.get(MemoryTrustLayer(r.trust_layer), "❓")
            lines.append(
                f"- {icon} [{r.trust_layer.upper()}] "
                f"(trust={r.trust_score:.2f}) "
                f"**{r.source}**: {r.content[:200]}"
            )
        return "\n".join(lines)

    def get_stats(self) -> dict:
        records = self.store.all_records()
        layer_counts = {}
        for layer in MemoryTrustLayer:
            layer_counts[layer.value] = len(self.store.by_layer(layer))
        return {
            "total":       len(records),
            "layers":      layer_counts,
            "quarantined": len(self.store.quarantined()),
            "avg_trust":   round(
                sum(r.trust_score for r in records) / max(len(records), 1), 3
            ),
        }


# ── 싱글톤 ────────────────────────────────────────────────────────────────────
_engine: Optional[MemoryTrustEngine] = None

def get_memory_trust_engine() -> MemoryTrustEngine:
    global _engine
    if _engine is None:
        _engine = MemoryTrustEngine()
    return _engine
