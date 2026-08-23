"""
engine.py — Scientific Context Expansion Engine (EPIC 09)
=========================================================
Orchestrates automatic scientific knowledge expansion for one seed paper:

  1. resolve the seed (anchor) by DOI across providers
  2. fan out: bibliographic search + provider-native related / citing /
     referenced retrieval on every registered source
  3. normalize + deduplicate across providers (DOI / title keys)
  4. classify candidates (related, influential, review, systematic review,
     meta-analysis, replication, contradictory, newer follow-up)
  5. score overall evidence strength
  6. record provenance for every paper and every provider call

Failure policy: provider errors never crash an expansion. They are
captured into ``ProviderProvenance`` records; optional circuit-breaking
delegates to ``core.fault_recovery.FaultRecoveryEngine`` when supplied.
The public API returns ``Ok/Err`` result types per ``core.contracts``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from core.contracts import Err, Ok, Result
from core.metadata.models import ExtractorType, MetadataSource, ProvenanceRecord
from literature.context.classifier import ContextClassifier, title_overlap  # noqa: F401 (re-export)
from literature.context.evidence import EvidenceStrengthScorer
from literature.context.models import (
    ContextCategory,
    ContextPaper,
    ProviderProvenance,
    ScientificContext,
)
from literature.search.base import LiteratureProvider
from literature.search.models import (  # noqa: F401 (re-export)
    LiteratureSource,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    to_metadata_source,
)
from literature.search.registry import LiteratureProviderRegistry, default_registry

DEFAULT_OUTPUT_DIR = Path.home() / ".ros_memory" / "scientific_context"

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class ContextExpansionConfig:
    """Immutable knobs controlling an expansion run."""

    max_results_per_provider: int = 25
    max_papers_per_category: int = 12
    min_relevance: float = 0.25
    fetch_related: bool = True
    fetch_citations: bool = True
    fetch_references: bool = True
    enabled_providers: Optional[Tuple[str, ...]] = None
    api_keys: Dict[str, str] = field(default_factory=dict)
    mailto: str = ""
    output_dir: Optional[Path] = None


class ScientificContextEngine:
    """Expands one seed paper into its surrounding scientific context."""

    def __init__(
        self,
        registry: Optional[LiteratureProviderRegistry] = None,
        classifier: Optional[ContextClassifier] = None,
        scorer: Optional[EvidenceStrengthScorer] = None,
        config: Optional[ContextExpansionConfig] = None,
        fault_recovery: Any = None,
    ) -> None:
        self.config = config or ContextExpansionConfig()
        self.registry = registry or default_registry(
            api_keys=self.config.api_keys,
            mailto=self.config.mailto,
            max_results=self.config.max_results_per_provider,
            enabled=self.config.enabled_providers,
        )
        self.classifier = classifier or ContextClassifier()
        self.scorer = scorer or EvidenceStrengthScorer()
        self.fault_recovery = fault_recovery

    # ── public API ─────────────────────────────────────────────────────────

    def expand(self, seed: SeedPaper) -> Result:
        """Expand the seed into a full :class:`ScientificContext`."""
        if seed.is_empty():
            return Err(error="empty_seed", context="Seed paper needs a title or DOI")

        start = time.perf_counter()
        context = ScientificContext(seed=seed)
        candidates: Dict[str, _Candidate] = {}

        for provider in self.registry.available():
            provenance = ProviderProvenance(provider=provider.name, source=provider.source.value)
            started = time.perf_counter()
            try:
                papers = self._collect(provider, seed, provenance)
                provenance.status = "ok"
                provenance.retrieved = len(papers)
            except Exception as exc:  # provider-level failure
                provenance.status = "error"
                provenance.error = str(exc)[:300]
                papers = []
            provenance.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            provenance.retrieved_at = _now_iso()
            context.provider_provenance.append(provenance)

            for paper in papers:
                if paper.matches_seed(seed):
                    continue
                _merge_candidate(candidates, paper)

        context_papers = self._classify_candidates(candidates, seed)
        context.papers = sorted(context_papers, key=lambda cp: (-cp.relevance, cp.title.casefold()))
        self._fill_buckets(context)
        context.evidence = self.scorer.assess(context.papers)
        context.duration_ms = round((time.perf_counter() - start) * 1000, 1)
        return Ok(context)

    def expand_and_persist(self, seed: SeedPaper, output_dir: Optional[Path] = None) -> Result:
        """Expand and, on success, write SCIENTIFIC_CONTEXT.md + JSON."""
        from literature.context.markdown import write_outputs

        result = self.expand(seed)
        if not result.ok:
            return result
        write_outputs(result.value, output_dir or self.config.output_dir)
        return result

    # ── collection ─────────────────────────────────────────────────────────

    def _collect(
        self, provider: LiteratureProvider, seed: SeedPaper, provenance: ProviderProvenance
    ) -> List[RetrievedPaper]:
        papers: List[RetrievedPaper] = []

        # Primary search failures propagate to the caller so they are
        # recorded as provider-level provenance errors; secondary lookups
        # (related / citing / referenced) are best-effort.
        search_results = self._call_search(provider, seed)
        if seed.search_query:
            provenance.queries.append(seed.search_query)
        papers.extend(search_results)

        anchor = self._resolve_anchor(provider, seed)
        if anchor is not None:
            limit = self.config.max_results_per_provider
            if self.config.fetch_related:
                papers.extend(
                    self._protected(provider.name, lambda: provider.find_related(anchor, limit))
                    or []
                )
            if self.config.fetch_citations:
                papers.extend(
                    self._protected(provider.name, lambda: provider.find_citing(anchor, limit))
                    or []
                )
            if self.config.fetch_references:
                papers.extend(
                    self._protected(provider.name, lambda: provider.find_referenced(anchor, limit))
                    or []
                )

        return papers

    def _call_search(self, provider: LiteratureProvider, seed: SeedPaper) -> List[RetrievedPaper]:
        func = lambda: provider.search(seed, self.config.max_results_per_provider)
        if self.fault_recovery is not None and hasattr(
            self.fault_recovery, "execute_with_recovery"
        ):
            result, fallback_used = self.fault_recovery.execute_with_recovery(
                f"literature.{provider.name}", func, max_retries=1
            )
            if fallback_used and result is None:
                raise RuntimeError(
                    f"provider '{provider.name}' search failed (circuit open or retries exhausted)"
                )
            return result or []
        return func()

    def _resolve_anchor(
        self, provider: LiteratureProvider, seed: SeedPaper
    ) -> Optional[RetrievedPaper]:
        if not seed.doi:
            return None
        try:
            return provider.resolve_doi(seed.doi)
        except Exception:
            return None

    def _protected(self, provider_name: str, func: Callable[[], Any]) -> Any:
        """Run a provider call through the circuit breaker when available."""
        if self.fault_recovery is not None and hasattr(
            self.fault_recovery, "execute_with_recovery"
        ):
            result, _fallback_used = self.fault_recovery.execute_with_recovery(
                f"literature.{provider_name}", func, max_retries=1
            )
            return result
        try:
            return func()
        except Exception:
            return None

    # ── classification & bucketing ─────────────────────────────────────────

    def _classify_candidates(
        self, candidates: Dict[str, "_Candidate"], seed: SeedPaper
    ) -> List[ContextPaper]:
        context_papers: List[ContextPaper] = []
        always_keep = {
            ContextCategory.META_ANALYSIS,
            ContextCategory.SYSTEMATIC_REVIEW,
            ContextCategory.REPLICATION,
            ContextCategory.CONTRADICTORY,
        }

        for candidate in candidates.values():
            paper = candidate.to_paper()
            result = self.classifier.classify(paper, seed, candidate.channels)
            if result.relevance < self.config.min_relevance and not (
                set(result.categories) & always_keep
            ):
                continue

            primary_source = LiteratureSource(paper.source.value)
            provenance = ProvenanceRecord(
                source=MetadataSource(to_metadata_source(primary_source)),
                extractor=ExtractorType.DATABASE_LOOKUP,
                confidence=result.relevance,
                pipeline_version="1.0.0",
                raw_value=paper.paper_id,
                notes=(
                    f"providers={','.join(sorted(candidate.sources))}; "
                    f"channels={','.join(sorted(candidate.channels))}; "
                    f"query={paper.query}"
                ),
            )
            context_papers.append(
                ContextPaper(
                    paper=paper,
                    categories=list(result.categories),
                    primary_category=result.primary_category,
                    relevance=result.relevance,
                    rationale=result.rationale,
                    channels=sorted(candidate.channels),
                    sources=sorted(candidate.sources),
                    provenance=provenance,
                )
            )
        return context_papers

    def _fill_buckets(self, context: ScientificContext) -> None:
        buckets = context.category_lists()
        for category, bucket in buckets.items():
            members = [cp for cp in context.papers if cp.has(category)]
            members.sort(key=lambda cp: (-cp.relevance, cp.title.casefold()))
            bucket.extend(members[: self.config.max_papers_per_category])

    # ── helpers ────────────────────────────────────────────────────────────


class _Candidate:
    """Mutable accumulator merging one paper across providers/channels."""

    def __init__(self, paper: RetrievedPaper) -> None:
        self.paper = paper
        self.channels: Set[str] = {paper.channel.value}
        self.sources: Set[str] = {paper.source.value}

    def merge(self, paper: RetrievedPaper) -> None:
        self.channels.add(paper.channel.value)
        self.sources.add(paper.source.value)
        current = self.paper
        upgraded = current
        # prefer richer records: abstract > none, citations > none, venue > ""
        if not current.abstract and paper.abstract:
            upgraded = replace(upgraded, abstract=paper.abstract)
        if current.citation_count is None and paper.citation_count is not None:
            upgraded = replace(upgraded, citation_count=paper.citation_count)
        elif (paper.citation_count or 0) > (current.citation_count or 0):
            upgraded = replace(upgraded, citation_count=paper.citation_count)
        if not current.venue and paper.venue:
            upgraded = replace(upgraded, venue=paper.venue)
        if not current.doi and paper.doi:
            upgraded = replace(upgraded, doi=paper.doi)
        publication_types = tuple(
            dict.fromkeys(current.publication_types + paper.publication_types)
        )
        if publication_types != current.publication_types:
            upgraded = replace(upgraded, publication_types=publication_types)
        extra = {**current.extra, **paper.extra}
        if extra != current.extra:
            upgraded = replace(upgraded, extra=extra)
        self.paper = upgraded

    def to_paper(self) -> RetrievedPaper:
        channels = ",".join(sorted(self.channels))
        sources = ",".join(sorted(self.sources))
        return replace(
            self.paper,
            channel=self.paper.channel,
            query=self.paper.query or channels,
            extra={**self.paper.extra, "channels": channels, "providers": sources},
        )


def _merge_candidate(candidates: Dict[str, _Candidate], paper: RetrievedPaper) -> None:
    key = paper.dedup_key()
    if key in candidates:
        candidates[key].merge(paper)
        return
    # Records of the same work often carry different DOIs (working paper vs
    # published version) or none at all — fall back to a title cross-check.
    if paper.normalized_title:
        for candidate in candidates.values():
            if candidate.paper.normalized_title == paper.normalized_title:
                candidate.merge(paper)
                return
    candidates[key] = _Candidate(paper)


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


# ── seed construction helpers ────────────────────────────────────────────────


def seed_from_fields(
    title: str = "",
    doi: str = "",
    authors: Iterable[str] = (),
    year: Optional[int] = None,
    abstract: str = "",
    venue: str = "",
) -> SeedPaper:
    """Build a seed from plain fields, normalizing the DOI."""
    from literature.search.models import normalize_doi

    return SeedPaper(
        title=(title or "").strip(),
        doi=normalize_doi(doi),
        authors=tuple(authors),
        year=year,
        abstract=(abstract or "").strip(),
        venue=(venue or "").strip(),
    )


def extract_doi_from_text(text: str) -> Optional[str]:
    match = _DOI_PATTERN.search(text or "")
    if not match:
        return None
    from literature.search.models import normalize_doi

    return normalize_doi(match.group(0))


def slugify_title(title: str, doi: Optional[str] = None, max_length: int = 80) -> str:
    """Filesystem-safe slug for output filenames."""
    base = (title or "").strip()
    if not base and doi:
        base = doi
    slug = re.sub(r"[^\w\s-]", "", base, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-").lower()
    return slug[:max_length].rstrip("-") or "untitled"
