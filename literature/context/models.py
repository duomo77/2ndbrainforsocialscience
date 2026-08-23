"""
models.py — Scientific Context Data Models (EPIC 09)
====================================================
The output envelope of scientific knowledge expansion.

Given one seed paper, :class:`ScientificContext` gathers the surrounding
literature into eight categories (related, influential, review,
systematic review, meta-analysis, replication, contradictory, newer
follow-up), scores the overall evidence strength, and records full
provenance for every retrieved document and every provider call.

Every context paper carries a standard ROS ``ProvenanceRecord``
(``core.metadata.models``) so expansion output plugs directly into the
Metadata Engine's audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from core.metadata.models import ExtractorType, MetadataSource, ProvenanceRecord
from literature.search.models import RetrievedPaper, SeedPaper

SCIENTIFIC_CONTEXT_SCHEMA_VERSION = "1.0.0"
SCIENTIFIC_CONTEXT_ENGINE_VERSION = "1.0.0"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ContextCategory(str, Enum):
    RELATED = "related"
    INFLUENTIAL = "influential"
    REVIEW = "review"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    REPLICATION = "replication"
    CONTRADICTORY = "contradictory"
    FOLLOW_UP = "follow_up"


CATEGORY_DISPLAY: Dict[ContextCategory, str] = {
    ContextCategory.RELATED: "Related Papers",
    ContextCategory.INFLUENTIAL: "Influential Papers",
    ContextCategory.REVIEW: "Review Papers",
    ContextCategory.SYSTEMATIC_REVIEW: "Systematic Reviews",
    ContextCategory.META_ANALYSIS: "Meta-Analyses",
    ContextCategory.REPLICATION: "Replication Papers",
    ContextCategory.CONTRADICTORY: "Contradictory Papers",
    ContextCategory.FOLLOW_UP: "Newer Follow-Up Work",
}

# Primary-category precedence when a paper falls in several buckets.
CATEGORY_PRIORITY: tuple = (
    ContextCategory.CONTRADICTORY,
    ContextCategory.META_ANALYSIS,
    ContextCategory.SYSTEMATIC_REVIEW,
    ContextCategory.REVIEW,
    ContextCategory.REPLICATION,
    ContextCategory.INFLUENTIAL,
    ContextCategory.FOLLOW_UP,
    ContextCategory.RELATED,
)


class EvidenceLevel(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    LIMITED = "limited"
    CONTESTED = "contested"
    EMERGING = "emerging"
    INSUFFICIENT = "insufficient"


@dataclass
class ContextPaper:
    """A retrieved paper classified into its scientific-context role(s)."""

    paper: RetrievedPaper
    categories: List[ContextCategory] = field(default_factory=list)
    primary_category: ContextCategory = ContextCategory.RELATED
    relevance: float = 0.0
    rationale: str = ""
    channels: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    provenance: Optional[ProvenanceRecord] = None

    @property
    def title(self) -> str:
        return self.paper.title

    @property
    def year(self) -> Optional[int]:
        return self.paper.year

    @property
    def doi(self) -> Optional[str]:
        return self.paper.doi

    def has(self, category: ContextCategory) -> bool:
        return category in self.categories

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper": self.paper.to_dict(),
            "categories": [category.value for category in self.categories],
            "primary_category": self.primary_category.value,
            "relevance": self.relevance,
            "rationale": self.rationale,
            "channels": list(self.channels),
            "sources": list(self.sources),
            "provenance": _provenance_to_dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContextPaper":
        provenance = None
        raw_prov = data.get("provenance")
        if isinstance(raw_prov, Mapping):
            provenance = ProvenanceRecord(
                source=MetadataSource(raw_prov.get("source", "unknown")),
                extractor=ExtractorType(raw_prov.get("extractor", "database_lookup")),
                confidence=float(raw_prov.get("confidence", 0.0)),
                timestamp=raw_prov.get("timestamp", _now()),
                pipeline_version=raw_prov.get(
                    "pipeline_version", SCIENTIFIC_CONTEXT_SCHEMA_VERSION
                ),
                manual_override=bool(raw_prov.get("manual_override", False)),
                raw_value=raw_prov.get("raw_value"),
                notes=raw_prov.get("notes"),
            )
        return cls(
            paper=RetrievedPaper.from_dict(data.get("paper", {})),
            categories=[ContextCategory(value) for value in data.get("categories", [])],
            primary_category=ContextCategory(data.get("primary_category", "related")),
            relevance=float(data.get("relevance", 0.0)),
            rationale=data.get("rationale", ""),
            channels=list(data.get("channels", [])),
            sources=list(data.get("sources", [])),
            provenance=provenance,
        )


@dataclass
class EvidenceAssessment:
    """Overall strength of the evidence base surrounding the seed paper."""

    level: EvidenceLevel = EvidenceLevel.INSUFFICIENT
    score: float = 0.0
    rationale: List[str] = field(default_factory=list)
    signals: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "score": self.score,
            "rationale": list(self.rationale),
            "signals": dict(self.signals),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceAssessment":
        return cls(
            level=EvidenceLevel(data.get("level", "insufficient")),
            score=float(data.get("score", 0.0)),
            rationale=list(data.get("rationale", [])),
            signals=dict(data.get("signals", {})),
        )


@dataclass
class ProviderProvenance:
    """Audit record of one provider's participation in an expansion run."""

    provider: str
    source: str
    status: str = "pending"  # pending | ok | error | skipped
    error: str = ""
    queries: List[str] = field(default_factory=list)
    retrieved: int = 0
    latency_ms: float = 0.0
    retrieved_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "status": self.status,
            "error": self.error,
            "queries": list(self.queries),
            "retrieved": self.retrieved,
            "latency_ms": self.latency_ms,
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProviderProvenance":
        return cls(
            provider=data.get("provider", ""),
            source=data.get("source", ""),
            status=data.get("status", "pending"),
            error=data.get("error", ""),
            queries=list(data.get("queries", [])),
            retrieved=int(data.get("retrieved", 0)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            retrieved_at=data.get("retrieved_at", _now()),
        )


@dataclass
class ScientificContext:
    """Complete scientific-context expansion for one seed document."""

    seed: SeedPaper
    schema_version: str = SCIENTIFIC_CONTEXT_SCHEMA_VERSION
    engine_version: str = SCIENTIFIC_CONTEXT_ENGINE_VERSION

    related: List[ContextPaper] = field(default_factory=list)
    influential: List[ContextPaper] = field(default_factory=list)
    reviews: List[ContextPaper] = field(default_factory=list)
    systematic_reviews: List[ContextPaper] = field(default_factory=list)
    meta_analyses: List[ContextPaper] = field(default_factory=list)
    replications: List[ContextPaper] = field(default_factory=list)
    contradictory: List[ContextPaper] = field(default_factory=list)
    follow_ups: List[ContextPaper] = field(default_factory=list)

    papers: List[ContextPaper] = field(default_factory=list)
    evidence: EvidenceAssessment = field(default_factory=EvidenceAssessment)
    provider_provenance: List[ProviderProvenance] = field(default_factory=list)

    created_at: str = field(default_factory=_now)
    duration_ms: float = 0.0

    # ── accessors ──────────────────────────────────────────────────────────

    def category_lists(self) -> Dict[ContextCategory, List[ContextPaper]]:
        return {
            ContextCategory.RELATED: self.related,
            ContextCategory.INFLUENTIAL: self.influential,
            ContextCategory.REVIEW: self.reviews,
            ContextCategory.SYSTEMATIC_REVIEW: self.systematic_reviews,
            ContextCategory.META_ANALYSIS: self.meta_analyses,
            ContextCategory.REPLICATION: self.replications,
            ContextCategory.CONTRADICTORY: self.contradictory,
            ContextCategory.FOLLOW_UP: self.follow_ups,
        }

    def summary_counts(self) -> Dict[str, int]:
        return {category.value: len(papers) for category, papers in self.category_lists().items()}

    @property
    def total_papers(self) -> int:
        return len(self.papers)

    # ── serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "engine_version": self.engine_version,
            "seed": self.seed.to_dict(),
            "related": [paper.to_dict() for paper in self.related],
            "influential": [paper.to_dict() for paper in self.influential],
            "reviews": [paper.to_dict() for paper in self.reviews],
            "systematic_reviews": [paper.to_dict() for paper in self.systematic_reviews],
            "meta_analyses": [paper.to_dict() for paper in self.meta_analyses],
            "replications": [paper.to_dict() for paper in self.replications],
            "contradictory": [paper.to_dict() for paper in self.contradictory],
            "follow_ups": [paper.to_dict() for paper in self.follow_ups],
            "papers": [paper.to_dict() for paper in self.papers],
            "evidence": self.evidence.to_dict(),
            "provider_provenance": [prov.to_dict() for prov in self.provider_provenance],
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
        }

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScientificContext":
        context = cls(
            seed=SeedPaper.from_dict(data.get("seed", {})),
            schema_version=data.get("schema_version", SCIENTIFIC_CONTEXT_SCHEMA_VERSION),
            engine_version=data.get("engine_version", SCIENTIFIC_CONTEXT_ENGINE_VERSION),
        )
        context.related = [ContextPaper.from_dict(item) for item in data.get("related", [])]
        context.influential = [ContextPaper.from_dict(item) for item in data.get("influential", [])]
        context.reviews = [ContextPaper.from_dict(item) for item in data.get("reviews", [])]
        context.systematic_reviews = [
            ContextPaper.from_dict(item) for item in data.get("systematic_reviews", [])
        ]
        context.meta_analyses = [
            ContextPaper.from_dict(item) for item in data.get("meta_analyses", [])
        ]
        context.replications = [
            ContextPaper.from_dict(item) for item in data.get("replications", [])
        ]
        context.contradictory = [
            ContextPaper.from_dict(item) for item in data.get("contradictory", [])
        ]
        context.follow_ups = [ContextPaper.from_dict(item) for item in data.get("follow_ups", [])]
        context.papers = [ContextPaper.from_dict(item) for item in data.get("papers", [])]
        context.evidence = EvidenceAssessment.from_dict(data.get("evidence", {}))
        context.provider_provenance = [
            ProviderProvenance.from_dict(item) for item in data.get("provider_provenance", [])
        ]
        context.created_at = data.get("created_at", context.created_at)
        context.duration_ms = float(data.get("duration_ms", 0.0))
        return context

    @classmethod
    def from_json(cls, json_str: str) -> "ScientificContext":
        import json

        return cls.from_dict(json.loads(json_str))


def _provenance_to_dict(provenance: Optional[ProvenanceRecord]) -> Optional[Dict[str, Any]]:
    if provenance is None:
        return None
    return {
        "source": provenance.source.value,
        "extractor": provenance.extractor.value,
        "confidence": provenance.confidence,
        "timestamp": provenance.timestamp,
        "pipeline_version": provenance.pipeline_version,
        "manual_override": provenance.manual_override,
        "raw_value": provenance.raw_value,
        "notes": provenance.notes,
    }
