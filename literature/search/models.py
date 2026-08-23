"""
models.py — Literature Search Data Models (EPIC 09)
====================================================
Normalized data contracts for scientific literature retrieval.

Every provider (OpenAlex, Semantic Scholar, Crossref, PubMed, ArXiv, SSRN,
or future additions) maps its native payload onto :class:`RetrievedPaper`
so the downstream context engine consumes one canonical shape.

Design principles:
  - Provenance-first: every paper remembers which provider surfaced it,
    through which retrieval channel, and in response to which query.
  - Immutable transport objects: frozen dataclasses only.
  - Zero network access in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LiteratureSource(str, Enum):
    """Provider that supplied a retrieved paper."""

    OPENALEX = "openalex"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    SSRN = "ssrn"
    UNKNOWN = "unknown"


class RetrievalChannel(str, Enum):
    """How a paper was surfaced relative to the seed document."""

    SEARCH = "search"  # bibliographic/title search
    RELATED = "related"  # provider-native related articles
    RECOMMENDATIONS = "recommendations"  # Semantic Scholar recommendations
    CITATIONS = "citations"  # papers citing the seed (follow-up work)
    REFERENCES = "references"  # papers referenced by the seed (influential)
    ELINK = "elink"  # PubMed related-article links


@dataclass(frozen=True)
class SeedPaper:
    """The imported document that is expanded into its scientific context."""

    title: str = ""
    doi: Optional[str] = None
    authors: Tuple[str, ...] = ()
    year: Optional[int] = None
    abstract: str = ""
    venue: str = ""
    external_ids: Dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.title.strip() and not (self.doi or "").strip()

    @property
    def search_query(self) -> str:
        """Best-effort query string for title-based search endpoints."""
        title = self.title.strip()
        if title:
            return title
        return (self.doi or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "doi": self.doi,
            "authors": list(self.authors),
            "year": self.year,
            "abstract": self.abstract,
            "venue": self.venue,
            "external_ids": dict(self.external_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SeedPaper":
        return cls(
            title=data.get("title", "") or "",
            doi=data.get("doi"),
            authors=tuple(data.get("authors", ()) or ()),
            year=data.get("year"),
            abstract=data.get("abstract", "") or "",
            venue=data.get("venue", "") or "",
            external_ids=dict(data.get("external_ids", {}) or {}),
        )


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Lower-case, trim, and strip resolver URL prefixes from a DOI."""
    if not doi:
        return None
    cleaned = str(doi).strip().lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
        "doi/",
    ):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    cleaned = cleaned.strip()
    return cleaned or None


def normalize_title(title: str) -> str:
    """Collapse whitespace and drop non-alphanumerics for dedup keys."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


@dataclass(frozen=True)
class RetrievedPaper:
    """Canonical normalized record returned by every literature provider.

    Provenance is carried inline: ``source`` + ``source_id`` identify the
    providing database record, ``channel`` records how it was surfaced,
    ``query`` records the query used, and ``extra`` preserves provider
    specific identifiers needed for follow-up lookups.
    """

    paper_id: str
    title: str
    source: LiteratureSource
    source_id: str = ""
    authors: Tuple[str, ...] = ()
    year: Optional[int] = None
    venue: str = ""
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: str = ""
    citation_count: Optional[int] = None
    publication_types: Tuple[str, ...] = ()
    keywords: Tuple[str, ...] = ()
    channel: RetrievalChannel = RetrievalChannel.SEARCH
    query: str = ""
    retrieved_at: str = field(default_factory=_now)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)

    @property
    def normalized_doi(self) -> Optional[str]:
        return normalize_doi(self.doi)

    def dedup_key(self) -> str:
        doi = self.normalized_doi
        if doi:
            return f"doi:{doi}"
        if self.normalized_title:
            return f"title:{self.normalized_title}"
        return f"{self.source.value}:{self.source_id}"

    def matches_seed(self, seed: SeedPaper) -> bool:
        """True when this record appears to be the seed paper itself."""
        seed_doi = normalize_doi(seed.doi)
        if seed_doi and self.normalized_doi == seed_doi:
            return True
        seed_norm = normalize_title(seed.title)
        if seed_norm and self.normalized_title and seed_norm == self.normalized_title:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "source": self.source.value,
            "source_id": self.source_id,
            "authors": list(self.authors),
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "url": self.url,
            "abstract": self.abstract,
            "citation_count": self.citation_count,
            "publication_types": list(self.publication_types),
            "keywords": list(self.keywords),
            "channel": self.channel.value,
            "query": self.query,
            "retrieved_at": self.retrieved_at,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetrievedPaper":
        return cls(
            paper_id=data.get("paper_id", ""),
            title=data.get("title", "") or "",
            source=LiteratureSource(data.get("source", "unknown")),
            source_id=data.get("source_id", "") or "",
            authors=tuple(data.get("authors", ()) or ()),
            year=data.get("year"),
            venue=data.get("venue", "") or "",
            doi=data.get("doi"),
            url=data.get("url"),
            abstract=data.get("abstract", "") or "",
            citation_count=data.get("citation_count"),
            publication_types=tuple(data.get("publication_types", ()) or ()),
            keywords=tuple(data.get("keywords", ()) or ()),
            channel=RetrievalChannel(data.get("channel", "search")),
            query=data.get("query", "") or "",
            retrieved_at=data.get("retrieved_at", _now()),
            extra=dict(data.get("extra", {}) or {}),
        )


def make_paper_id(source: LiteratureSource, source_id: str, doi: Optional[str] = None) -> str:
    """Canonical identifier: DOI when known, else provider-scoped id."""
    normalized = normalize_doi(doi)
    if normalized:
        return f"doi:{normalized}"
    return f"{source.value}:{source_id}"


def to_metadata_source(source: LiteratureSource) -> str:
    """Map a literature provider onto ``core.metadata.models.MetadataSource``
    values so retrieved papers can carry standard ROS provenance records."""
    from core.metadata.models import MetadataSource

    mapping = {
        LiteratureSource.OPENALEX: MetadataSource.OPENALEX,
        LiteratureSource.SEMANTIC_SCHOLAR: MetadataSource.SEMANTIC_SCHOLAR,
        LiteratureSource.CROSSREF: MetadataSource.CROSSREF_API,
        LiteratureSource.PUBMED: MetadataSource.PUBMED_API,
        LiteratureSource.ARXIV: MetadataSource.ARXIV,
        LiteratureSource.SSRN: MetadataSource.SSRN,
        LiteratureSource.UNKNOWN: MetadataSource.UNKNOWN,
    }
    return mapping.get(source, MetadataSource.UNKNOWN).value
