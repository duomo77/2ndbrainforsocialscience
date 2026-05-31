"""
contradiction_engine.py — Contradiction Detection System (ROS v3.0)
====================================================================
경제학/계량경제학 특화 모순 감지 엔진.

감지 대상:
- 이론적 모순 (theoretical contradictions)
- 계량경제학적 비일관성 (econometric inconsistencies)
- 가정 충돌 (assumption conflicts)
- 식별 긴장 (identification tensions)
- DSGE vs 축약형 충돌
- 구조 vs 실증 비호환성

모순은 그래프의 1등급 객체(first-class graph objects)로 저장됨.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


# ── 모순 유형 분류 ─────────────────────────────────────────────────────────────

class ContradictionType(str, Enum):
    THEORETICAL       = "theoretical"          # 이론적 모순
    IDENTIFICATION    = "identification"       # 식별 전략 충돌
    ASSUMPTION        = "assumption"           # 가정 충돌
    DSGE_REDUCED      = "dsge_vs_reduced"      # DSGE vs 축약형
    STRUCTURAL_EMPIRICAL = "structural_empirical"  # 구조 vs 실증
    ASYMPTOTIC        = "asymptotic"           # 점근 가정 위반
    SUTVA             = "sutva_violation"      # SUTVA 위반
    EXTERNAL_VALIDITY = "external_validity"    # 외부 타당성 충돌
    WEAK_IV           = "weak_identification"  # 약한 식별
    EQUILIBRIUM       = "equilibrium"          # 균형 가정 불일치
    METHODOLOGICAL    = "methodological"       # 방법론적 불일치
    EMPIRICAL         = "empirical"            # 실증 결과 충돌


class ContradictionSeverity(str, Enum):
    CRITICAL  = "critical"   # 연구 무효화 가능
    MAJOR     = "major"      # 중요한 제한점
    MINOR     = "minor"      # 경미한 긴장
    LATENT    = "latent"     # 잠재적 문제


SEVERITY_ICONS = {
    ContradictionSeverity.CRITICAL: "🔴",
    ContradictionSeverity.MAJOR:    "🟠",
    ContradictionSeverity.MINOR:    "🟡",
    ContradictionSeverity.LATENT:   "🔵",
}

# 경제학 특화 모순 패턴 (규칙 기반 1차 감지)
ECON_CONTRADICTION_PATTERNS = [
    # 약한 식별
    {
        "type": ContradictionType.WEAK_IV,
        "keywords": ["weak instrument", "first stage F", "F-statistic", "relevance condition"],
        "conflict_with": ["IV", "2SLS", "instrumental variable"],
        "description": "약한 도구변수 - 관련성 조건 위반 가능성",
        "severity": ContradictionSeverity.CRITICAL,
    },
    # SUTVA 위반
    {
        "type": ContradictionType.SUTVA,
        "keywords": ["spillover", "interference", "network effect", "general equilibrium"],
        "conflict_with": ["ATE", "LATE", "DID", "RDD"],
        "description": "처치 파급효과 - SUTVA 위반 가능성",
        "severity": ContradictionSeverity.MAJOR,
    },
    # 평행 추세 위반
    {
        "type": ContradictionType.ASSUMPTION,
        "keywords": ["pre-trend", "parallel trend violation", "differential trend"],
        "conflict_with": ["DID", "difference-in-differences"],
        "description": "평행 추세 가정 위반 가능성",
        "severity": ContradictionSeverity.CRITICAL,
    },
    # DSGE vs 축약형
    {
        "type": ContradictionType.DSGE_REDUCED,
        "keywords": ["DSGE", "structural model", "Lucas critique"],
        "conflict_with": ["reduced form", "VAR", "local projection"],
        "description": "DSGE 구조 가정과 축약형 추정의 비호환성",
        "severity": ContradictionSeverity.MAJOR,
    },
    # 점근 가정
    {
        "type": ContradictionType.ASYMPTOTIC,
        "keywords": ["small sample", "finite sample", "n="],
        "conflict_with": ["asymptotic normality", "CLT", "consistency"],
        "description": "소표본에서 점근 이론 적용 가능성",
        "severity": ContradictionSeverity.MINOR,
    },
    # 균형 가정
    {
        "type": ContradictionType.EQUILIBRIUM,
        "keywords": ["partial equilibrium", "general equilibrium", "market clearing"],
        "conflict_with": ["causal effect", "treatment effect", "policy evaluation"],
        "description": "부분균형 vs 일반균형 가정 충돌",
        "severity": ContradictionSeverity.MAJOR,
    },
    # 외부 타당성
    {
        "type": ContradictionType.EXTERNAL_VALIDITY,
        "keywords": ["local average treatment effect", "LATE", "complier"],
        "conflict_with": ["ATE", "policy implication", "generalization"],
        "description": "LATE의 외부 타당성 제한",
        "severity": ContradictionSeverity.MINOR,
    },
]


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class ContradictionEdge:
    """모순 그래프 엣지 - 두 노트/개념 간의 모순 관계."""
    contradiction_id: str
    source_note:   str          # 노트 제목 또는 ID
    target_note:   str          # 충돌하는 노트/개념
    contradiction_type: str     # ContradictionType value
    severity:      str          # ContradictionSeverity value
    description:   str
    evidence:      str          # 근거 텍스트
    detected_at:   str
    resolved:      bool = False
    resolution:    str = ""
    trigger:       str = "auto"  # "auto" | "llm" | "manual"


@dataclass
class AssumptionNode:
    """가정 의존성 트리 노드."""
    assumption_id: str
    name:          str
    formal_statement: str
    depends_on:    list[str] = field(default_factory=list)
    required_by:   list[str] = field(default_factory=list)  # 어떤 추정량이 이 가정 필요
    violated_by:   list[str] = field(default_factory=list)  # 어떤 상황이 위반


# ── Contradiction Store ───────────────────────────────────────────────────────

class ContradictionStore:
    """모순 그래프 영속화 저장소."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir  = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "contradictions.json"
        self._edges: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._edges = json.load(f)
            except Exception:
                self._edges = {}

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._edges, f, ensure_ascii=False, indent=2)

    def add_edge(self, edge: ContradictionEdge):
        self._edges[edge.contradiction_id] = asdict(edge)
        self._save()

    def get_all(self) -> list[ContradictionEdge]:
        return [ContradictionEdge(**d) for d in self._edges.values()]

    def get_for_note(self, note_title: str) -> list[ContradictionEdge]:
        return [
            ContradictionEdge(**d) for d in self._edges.values()
            if d["source_note"] == note_title or d["target_note"] == note_title
        ]

    def get_unresolved(self) -> list[ContradictionEdge]:
        return [ContradictionEdge(**d) for d in self._edges.values() if not d["resolved"]]

    def resolve(self, contradiction_id: str, resolution: str):
        if contradiction_id in self._edges:
            self._edges[contradiction_id]["resolved"] = True
            self._edges[contradiction_id]["resolution"] = resolution
            self._save()

    def stats(self) -> dict:
        edges = self.get_all()
        by_type = {}
        by_severity = {}
        for e in edges:
            by_type[e.contradiction_type] = by_type.get(e.contradiction_type, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        return {
            "total": len(edges),
            "unresolved": len(self.get_unresolved()),
            "by_type": by_type,
            "by_severity": by_severity,
        }


# ── Contradiction Engine ──────────────────────────────────────────────────────

class ContradictionEngine:
    """
    경제학 특화 모순 감지 엔진.
    규칙 기반 1차 감지 + LLM 2차 심층 분석.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.store = ContradictionStore(data_dir)

    def _make_id(self, source: str, target: str, ctype: str) -> str:
        key = f"{source}|{target}|{ctype}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def scan_rule_based(
        self, content: str, note_title: str
    ) -> list[ContradictionEdge]:
        """
        규칙 기반 1차 모순 스캔.
        경제학 특화 패턴 매칭으로 즉각 감지.
        """
        import re
        content_lower = content.lower()
        detected = []

        for pattern in ECON_CONTRADICTION_PATTERNS:
            # 키워드 존재 확인
            has_keywords = any(kw.lower() in content_lower for kw in pattern["keywords"])
            has_conflict = any(cf.lower() in content_lower for cf in pattern["conflict_with"])

            if has_keywords and has_conflict:
                # 근거 텍스트 추출
                evidence_lines = []
                for kw in pattern["keywords"]:
                    for line in content.split("\n"):
                        if kw.lower() in line.lower():
                            evidence_lines.append(line.strip()[:200])
                            break

                edge = ContradictionEdge(
                    contradiction_id = self._make_id(
                        note_title, str(pattern["conflict_with"]), pattern["type"].value
                    ),
                    source_note      = note_title,
                    target_note      = ", ".join(pattern["conflict_with"]),
                    contradiction_type = pattern["type"].value,
                    severity         = pattern["severity"].value,
                    description      = pattern["description"],
                    evidence         = " | ".join(evidence_lines[:3]),
                    detected_at      = datetime.utcnow().isoformat(),
                    trigger          = "auto",
                )
                self.store.add_edge(edge)
                detected.append(edge)

        return detected

    def build_assumption_tree(self, content: str) -> list[AssumptionNode]:
        """
        내용에서 가정 의존성 트리 구축.
        핵심 계량경제학 가정들의 의존 관계 추출.
        """
        import re
        assumptions = []
        content_lower = content.lower()

        ASSUMPTION_MAP = {
            "CIA": {
                "formal": "Y(d) ⊥ D | X  (Conditional Independence Assumption)",
                "depends_on": ["Unconfoundedness", "Overlap"],
                "required_by": ["OLS", "IPW", "DML", "Matching"],
            },
            "Parallel Trends": {
                "formal": "E[Y₀ᵢₜ - Y₀ᵢₜ₋₁ | Dᵢ=1] = E[Y₀ᵢₜ - Y₀ᵢₜ₋₁ | Dᵢ=0]",
                "depends_on": ["No anticipation", "Stable unit treatment"],
                "required_by": ["DID", "Event Study"],
            },
            "Exclusion Restriction": {
                "formal": "Z ⊥ Y | D, X  (IV exclusion)",
                "depends_on": ["Instrument relevance", "Exogeneity"],
                "required_by": ["IV", "2SLS", "LATE"],
            },
            "SUTVA": {
                "formal": "Yᵢ(d₁,...,dₙ) = Yᵢ(dᵢ)  (No interference)",
                "depends_on": ["Stable treatment", "No spillovers"],
                "required_by": ["ATE", "LATE", "DID", "RDD"],
            },
            "Continuity": {
                "formal": "E[Y₀|X=c] continuous at c  (RDD continuity)",
                "depends_on": ["No manipulation", "Local randomization"],
                "required_by": ["RDD", "Fuzzy RDD"],
            },
        }

        for name, info in ASSUMPTION_MAP.items():
            if name.lower() in content_lower or any(
                dep.lower() in content_lower for dep in info["depends_on"]
            ):
                node = AssumptionNode(
                    assumption_id = hashlib.sha256(name.encode()).hexdigest()[:8],
                    name          = name,
                    formal_statement = info["formal"],
                    depends_on    = info["depends_on"],
                    required_by   = info["required_by"],
                )
                assumptions.append(node)

        return assumptions

    def format_contradiction_report(self, note_title: str) -> str:
        """특정 노트의 모순 보고서 생성 (Markdown)."""
        edges = self.store.get_for_note(note_title)
        if not edges:
            return ""

        lines = ["\n## ⚡ Contradiction & Tension Analysis\n"]
        unresolved = [e for e in edges if not e.resolved]
        resolved   = [e for e in edges if e.resolved]

        if unresolved:
            lines.append(f"### 🔴 Unresolved Contradictions ({len(unresolved)})\n")
            for e in sorted(unresolved, key=lambda x: x.severity):
                icon = SEVERITY_ICONS.get(ContradictionSeverity(e.severity), "⚠️")
                lines.append(f"#### {icon} {e.contradiction_type.replace('_',' ').title()}")
                lines.append(f"- **Description**: {e.description}")
                lines.append(f"- **Conflicts with**: {e.target_note}")
                if e.evidence:
                    lines.append(f"- **Evidence**: _{e.evidence[:200]}_")
                lines.append(f"- **Severity**: `{e.severity}`")
                lines.append(f"- **ID**: `{e.contradiction_id}`\n")

        if resolved:
            lines.append(f"\n### ✅ Resolved Contradictions ({len(resolved)})\n")
            for e in resolved:
                lines.append(f"- ~~{e.description}~~ → {e.resolution}")

        return "\n".join(lines)

    def get_tension_summary(self) -> dict:
        """전체 모순/긴장 현황 요약."""
        return self.store.stats()


# ── 싱글톤 접근 ───────────────────────────────────────────────────────────────
_engine: Optional[ContradictionEngine] = None

def get_contradiction_engine() -> ContradictionEngine:
    global _engine
    if _engine is None:
        _engine = ContradictionEngine()
    return _engine
