"""
base.py — Literature Provider Contract (EPIC 09)
================================================
Every academic source (OpenAlex, Semantic Scholar, Crossref, PubMed, ArXiv,
SSRN, and future additions) implements :class:`LiteratureProvider`.

The contract mirrors the retrieval needs of scientific context expansion:

  * ``search``          — bibliographic search around the seed paper
  * ``resolve_doi``     — fetch the canonical record for a DOI (anchor)
  * ``find_related``    — provider-native related/recommended articles
  * ``find_citing``     — newer papers citing the anchor (follow-up work)
  * ``find_referenced`` — works referenced by the anchor (influential)

Only ``search`` is mandatory; the remaining hooks default to empty so a
minimal provider stays valid. All methods return normalized
``RetrievedPaper`` lists and raise ``TransportError`` on network failure —
the engine converts failures into provenance records, never crashes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, List, Optional

from literature.search.models import (
    LiteratureSource,
    RetrievedPaper,
    SeedPaper,
)
from literature.search.transport import HttpTransport


class LiteratureProvider(ABC):
    """Abstract base class for literature search providers."""

    name: ClassVar[str] = "abstract"
    source: ClassVar[LiteratureSource] = LiteratureSource.UNKNOWN

    def __init__(
        self,
        transport: Optional[HttpTransport] = None,
        api_key: str = "",
        max_results: int = 25,
        timeout: float = 25.0,
    ) -> None:
        self.transport = transport or HttpTransport()
        self.api_key = api_key
        self.max_results = max(1, int(max_results))
        self.timeout = timeout

    # ── contract ───────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Whether this provider can run with its current configuration."""
        return True

    @abstractmethod
    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        """Search the source for papers related to the seed document."""

    def resolve_doi(self, doi: str) -> Optional[RetrievedPaper]:
        """Resolve the canonical record for a DOI, if this source knows it."""
        return None

    def find_related(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        """Provider-native related or recommended articles for the anchor."""
        return []

    def find_citing(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        """Papers citing the anchor (candidates for newer follow-up work)."""
        return []

    def find_referenced(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        """Papers referenced by the anchor (candidates for influential work)."""
        return []

    # ── helpers ────────────────────────────────────────────────────────────

    def _limit(self, limit: Optional[int]) -> int:
        return max(1, int(limit if limit is not None else self.max_results))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_results={self.max_results})"
