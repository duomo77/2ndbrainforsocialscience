"""
note_evolution.py — Note Evolution System (ROS v3.0)
=====================================================
6단계 상태전이 아키텍처:
  fleeting_note → literature_note → permanent_note
  → synthesis_note → paper_hypothesis → research_program

Meta-scale 원칙:
- 이벤트 기반 상태전이 (event-driven transitions)
- 의미론적 성숙도 스코어링 (semantic maturity scoring)
- 증분 그래프 업데이트 (incremental graph updates)
- 버전 인식 진화 추적 (version-aware evolution tracking)
"""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


# ── 상태 정의 ─────────────────────────────────────────────────────────────────

class NoteStage(str, Enum):
    FLEETING       = "fleeting_note"       # 1. 즉흥적 아이디어
    LITERATURE     = "literature_note"     # 2. 문헌 기반 노트
    PERMANENT      = "permanent_note"      # 3. 영구 노트 (Zettelkasten)
    SYNTHESIS      = "synthesis_note"      # 4. 합성 노트 (여러 개념 통합)
    HYPOTHESIS     = "paper_hypothesis"    # 5. 논문 가설
    PROGRAM        = "research_program"    # 6. 연구 프로그램


# 상태 전이 조건 (최소 요구사항)
TRANSITION_REQUIREMENTS: dict[NoteStage, dict] = {
    NoteStage.FLEETING: {
        "min_links": 0, "min_words": 10, "min_concepts": 0,
        "description": "초기 아이디어 캡처",
    },
    NoteStage.LITERATURE: {
        "min_links": 1, "min_words": 50, "min_concepts": 1,
        "description": "문헌 참조 포함, 개념 식별",
    },
    NoteStage.PERMANENT: {
        "min_links": 2, "min_words": 150, "min_concepts": 2,
        "description": "독립적 지식 단위, 재사용 가능",
    },
    NoteStage.SYNTHESIS: {
        "min_links": 4, "min_words": 300, "min_concepts": 4,
        "description": "여러 노트 통합, 새로운 통찰",
    },
    NoteStage.HYPOTHESIS: {
        "min_links": 6, "min_words": 500, "min_concepts": 5,
        "description": "검증 가능한 연구 가설",
    },
    NoteStage.PROGRAM: {
        "min_links": 10, "min_words": 1000, "min_concepts": 8,
        "description": "체계적 연구 프로그램",
    },
}

STAGE_ORDER = [
    NoteStage.FLEETING, NoteStage.LITERATURE, NoteStage.PERMANENT,
    NoteStage.SYNTHESIS, NoteStage.HYPOTHESIS, NoteStage.PROGRAM,
]

STAGE_ICONS = {
    NoteStage.FLEETING:   "💭",
    NoteStage.LITERATURE: "📚",
    NoteStage.PERMANENT:  "🧱",
    NoteStage.SYNTHESIS:  "🔗",
    NoteStage.HYPOTHESIS: "🔬",
    NoteStage.PROGRAM:    "🚀",
}

STAGE_COLORS = {
    NoteStage.FLEETING:   "#6b7280",
    NoteStage.LITERATURE: "#3b82f6",
    NoteStage.PERMANENT:  "#10b981",
    NoteStage.SYNTHESIS:  "#8b5cf6",
    NoteStage.HYPOTHESIS: "#f59e0b",
    NoteStage.PROGRAM:    "#ef4444",
}


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class StageTransition:
    """상태 전이 이벤트 레코드."""
    from_stage:  str
    to_stage:    str
    timestamp:   str
    trigger:     str          # "auto" | "manual" | "merge" | "llm"
    maturity_score: float
    reason:      str = ""


@dataclass
class NoteEvolutionRecord:
    """노트의 진화 이력 전체."""
    note_id:      str           # 불변 ID (SHA-256 기반)
    title:        str
    current_stage: str          # NoteStage value
    created_at:   str
    updated_at:   str
    maturity_score: float = 0.0
    word_count:   int = 0
    link_count:   int = 0
    concept_count: int = 0
    transitions:  list[dict] = field(default_factory=list)
    ancestors:    list[str] = field(default_factory=list)   # lineage IDs
    descendants:  list[str] = field(default_factory=list)
    merged_from:  list[str] = field(default_factory=list)
    version:      int = 1
    checksum:     str = ""


# ── Evolution Store ───────────────────────────────────────────────────────────

class NoteEvolutionStore:
    """
    노트 진화 상태 영속화 저장소.
    ~/.econometric_wiki/evolution.json
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "evolution.json"
        self._records: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
            except Exception:
                self._records = {}

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)

    def get(self, note_id: str) -> Optional[NoteEvolutionRecord]:
        d = self._records.get(note_id)
        if d:
            r = NoteEvolutionRecord(**d)
            return r
        return None

    def upsert(self, record: NoteEvolutionRecord):
        record.updated_at = datetime.utcnow().isoformat()
        record.version += 1
        self._records[record.note_id] = asdict(record)
        self._save()

    def all_records(self) -> list[NoteEvolutionRecord]:
        return [NoteEvolutionRecord(**d) for d in self._records.values()]

    def get_by_stage(self, stage: NoteStage) -> list[NoteEvolutionRecord]:
        return [r for r in self.all_records() if r.current_stage == stage.value]

    def stage_stats(self) -> dict[str, int]:
        stats = {s.value: 0 for s in NoteStage}
        for r in self.all_records():
            if r.current_stage in stats:
                stats[r.current_stage] += 1
        return stats


# ── Maturity Scorer ───────────────────────────────────────────────────────────

class MaturityScorer:
    """
    노트의 의미론적 성숙도를 0~1 스코어로 계산.
    링크 수, 단어 수, 개념 수, 수식 포함 여부, 인용 수를 종합.
    """

    WEIGHTS = {
        "word_count":    0.20,
        "link_count":    0.25,
        "concept_count": 0.25,
        "has_equations": 0.15,
        "has_citations": 0.10,
        "has_methods":   0.05,
    }

    def score(self, content: str, wikilinks: list[str]) -> tuple[float, dict]:
        import re
        words    = len(content.split())
        links    = len(wikilinks)
        concepts = len(re.findall(r'\[\[.+?\]\]', content))
        equations = 1 if re.search(r'\$\$.+?\$\$|\$[^$]+\$', content, re.DOTALL) else 0
        citations = 1 if re.search(r'\[@\w+|doi:|arxiv:|p\.\s*\d+', content, re.IGNORECASE) else 0
        methods   = 1 if re.search(
            r'\b(DML|IV|DID|RDD|OLS|2SLS|GMM|MLE|LASSO|Random Forest|Causal Forest)\b',
            content, re.IGNORECASE
        ) else 0

        # 정규화 (각 차원 0~1)
        norm = {
            "word_count":    min(words / 1000, 1.0),
            "link_count":    min(links / 10, 1.0),
            "concept_count": min(concepts / 8, 1.0),
            "has_equations": float(equations),
            "has_citations": float(citations),
            "has_methods":   float(methods),
        }
        total = sum(norm[k] * w for k, w in self.WEIGHTS.items())
        return round(total, 4), norm


# ── Evolution Engine ──────────────────────────────────────────────────────────

class NoteEvolutionEngine:
    """
    노트 진화 엔진 - 상태전이 자동화, 성숙도 평가, 병합 관리.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.store  = NoteEvolutionStore(data_dir)
        self.scorer = MaturityScorer()

    def make_note_id(self, title: str) -> str:
        """제목 기반 불변 ID 생성."""
        return hashlib.sha256(title.strip().lower().encode()).hexdigest()[:16]

    def register_note(
        self,
        title: str,
        content: str,
        wikilinks: list[str],
        initial_stage: NoteStage = NoteStage.FLEETING,
        ancestors: list[str] = None,
    ) -> NoteEvolutionRecord:
        """새 노트 등록 또는 기존 노트 업데이트."""
        note_id = self.make_note_id(title)
        score, _ = self.scorer.score(content, wikilinks)

        existing = self.store.get(note_id)
        if existing:
            # 기존 노트 업데이트
            existing.word_count    = len(content.split())
            existing.link_count    = len(wikilinks)
            existing.concept_count = len([l for l in wikilinks if l])
            existing.maturity_score = score
            existing.checksum      = hashlib.md5(content.encode()).hexdigest()[:8]
            record = existing
        else:
            now = datetime.utcnow().isoformat()
            record = NoteEvolutionRecord(
                note_id       = note_id,
                title         = title,
                current_stage = initial_stage.value,
                created_at    = now,
                updated_at    = now,
                maturity_score = score,
                word_count    = len(content.split()),
                link_count    = len(wikilinks),
                concept_count = len([l for l in wikilinks if l]),
                ancestors     = ancestors or [],
                checksum      = hashlib.md5(content.encode()).hexdigest()[:8],
                version       = 0,
            )

        # 자동 승격 시도
        record = self._try_promote(record, content, wikilinks)
        self.store.upsert(record)
        return record

    def _try_promote(
        self,
        record: NoteEvolutionRecord,
        content: str,
        wikilinks: list[str],
    ) -> NoteEvolutionRecord:
        """성숙도 기반 자동 상태 승격."""
        current_idx = next(
            (i for i, s in enumerate(STAGE_ORDER) if s.value == record.current_stage), 0
        )
        if current_idx >= len(STAGE_ORDER) - 1:
            return record  # 이미 최고 단계

        next_stage = STAGE_ORDER[current_idx + 1]
        req = TRANSITION_REQUIREMENTS[next_stage]

        can_promote = (
            record.word_count    >= req["min_words"] and
            record.link_count    >= req["min_links"] and
            record.concept_count >= req["min_concepts"]
        )

        if can_promote:
            transition = StageTransition(
                from_stage     = record.current_stage,
                to_stage       = next_stage.value,
                timestamp      = datetime.utcnow().isoformat(),
                trigger        = "auto",
                maturity_score = record.maturity_score,
                reason         = f"Maturity threshold met: words={record.word_count}, links={record.link_count}",
            )
            record.transitions.append(asdict(transition))
            record.current_stage = next_stage.value
            # 재귀적으로 추가 승격 시도
            record = self._try_promote(record, content, wikilinks)

        return record

    def manual_promote(self, note_id: str, target_stage: NoteStage, reason: str = "") -> bool:
        """수동 상태 승격."""
        record = self.store.get(note_id)
        if not record:
            return False
        transition = StageTransition(
            from_stage     = record.current_stage,
            to_stage       = target_stage.value,
            timestamp      = datetime.utcnow().isoformat(),
            trigger        = "manual",
            maturity_score = record.maturity_score,
            reason         = reason or "Manual promotion",
        )
        record.transitions.append(asdict(transition))
        record.current_stage = target_stage.value
        self.store.upsert(record)
        return True

    def merge_notes(
        self,
        source_ids: list[str],
        merged_title: str,
        merged_content: str,
        merged_wikilinks: list[str],
    ) -> NoteEvolutionRecord:
        """여러 노트를 병합하여 새 합성 노트 생성 (아이디어 계보 보존)."""
        ancestors = []
        for sid in source_ids:
            r = self.store.get(sid)
            if r:
                ancestors.append(sid)
                ancestors.extend(r.ancestors)

        new_record = self.register_note(
            title         = merged_title,
            content       = merged_content,
            wikilinks     = merged_wikilinks,
            initial_stage = NoteStage.SYNTHESIS,
            ancestors     = list(set(ancestors)),
        )
        new_record.merged_from = source_ids

        # 원본 노트에 descendant 등록
        for sid in source_ids:
            r = self.store.get(sid)
            if r:
                if new_record.note_id not in r.descendants:
                    r.descendants.append(new_record.note_id)
                self.store.upsert(r)

        self.store.upsert(new_record)
        return new_record

    def get_evolution_summary(self) -> dict:
        """전체 진화 현황 요약."""
        stats = self.store.stage_stats()
        records = self.store.all_records()
        avg_score = sum(r.maturity_score for r in records) / max(len(records), 1)
        return {
            "total_notes":  len(records),
            "stage_dist":   stats,
            "avg_maturity": round(avg_score, 3),
            "top_mature":   sorted(records, key=lambda r: r.maturity_score, reverse=True)[:5],
        }

    def inject_evolution_frontmatter(
        self, markdown: str, title: str, wikilinks: list[str]
    ) -> str:
        """생성된 Markdown에 evolution 메타데이터 주입."""
        import re
        record = self.register_note(title, markdown, wikilinks)
        stage  = record.current_stage
        icon   = STAGE_ICONS.get(NoteStage(stage), "💭")
        score  = record.maturity_score

        evolution_block = (
            f"evolution_stage: {stage}\n"
            f"evolution_icon: \"{icon}\"\n"
            f"maturity_score: {score}\n"
            f"note_id: {record.note_id}\n"
            f"version: {record.version}\n"
        )

        # YAML frontmatter에 삽입
        if markdown.startswith("---"):
            end = markdown.find("\n---", 3)
            if end > 0:
                return markdown[:end] + "\n" + evolution_block + markdown[end:]
        return f"---\n{evolution_block}---\n\n" + markdown


# ── 싱글톤 접근 ───────────────────────────────────────────────────────────────
_engine: Optional[NoteEvolutionEngine] = None

def get_evolution_engine() -> NoteEvolutionEngine:
    global _engine
    if _engine is None:
        _engine = NoteEvolutionEngine()
    return _engine
