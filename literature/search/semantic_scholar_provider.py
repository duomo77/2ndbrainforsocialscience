"""
semantic_scholar_provider.py — Semantic Scholar Provider (EPIC 09)
==================================================================
Semantic Scholar Graph API v1 (https://api.semanticscholar.org/graph/v1):

  * ``GET /paper/search?query=...``                  — relevance search
  * ``GET /paper/DOI:<doi>``                         — anchor resolution
  * ``GET /paper/{id}/recommendations``              — related papers
  * ``GET /paper/{id}/citations``                    — citing papers

The unauthenticated pool is aggressively throttled (100 req / 5 min);
the transport layer retries 429 responses with Retry-After backoff, and
an optional ``api_key`` is sent via the ``x-api-key`` header.

``publicationTypes`` (Review, MetaAnalysis, SystematicReview, ...) is the
most reliable review-family signal available across all providers.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from literature.search.base import LiteratureProvider
from literature.search.models import (
    LiteratureSource,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    make_paper_id,
    normalize_doi,
)

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = (
    "paperId,title,abstract,year,venue,citationCount,authors,"
    "externalIds,publicationTypes,openAccessPdf"
)


class SemanticScholarProvider(LiteratureProvider):
    """Semantic Scholar Graph API v1 provider."""

    name: ClassVar[str] = "semantic_scholar"
    source: ClassVar[LiteratureSource] = LiteratureSource.SEMANTIC_SCHOLAR

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = S2_BASE_URL

    def is_configured(self) -> bool:
        # Public pool works without a key; a key only raises rate limits.
        return True

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        query = seed.search_query
        if not query:
            return []
        payload = self.transport.get_json(
            f"{self.base_url}/paper/search",
            params={"query": query, "fields": S2_FIELDS, "limit": self._limit(limit)},
            headers=self._auth_headers(),
        )
        return [
            self._item_to_paper(item, RetrievalChannel.SEARCH, query)
            for item in payload.get("data", [])
            if item.get("title")
        ]

    def resolve_doi(self, doi: str) -> Optional[RetrievedPaper]:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        payload = self.transport.get_json(
            f"{self.base_url}/paper/DOI:{normalized}",
            params={"fields": S2_FIELDS},
            headers=self._auth_headers(),
        )
        if not isinstance(payload, dict) or not payload.get("paperId"):
            return None
        return self._item_to_paper(payload, RetrievalChannel.SEARCH, f"doi:{normalized}")

    def find_related(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        paper_id = anchor.extra.get("s2_paper_id", "")
        if not paper_id:
            return []
        payload = self.transport.get_json(
            f"{self.base_url}/paper/{paper_id}/recommendations",
            params={"fields": S2_FIELDS, "limit": self._limit(limit)},
            headers=self._auth_headers(),
        )
        return [
            self._item_to_paper(
                item, RetrievalChannel.RECOMMENDATIONS, f"recommendations:{paper_id}"
            )
            for item in payload.get("data", [])
            if item.get("title")
        ]

    def find_citing(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        paper_id = anchor.extra.get("s2_paper_id", "")
        if not paper_id:
            return []
        payload = self.transport.get_json(
            f"{self.base_url}/paper/{paper_id}/citations",
            params={"fields": S2_FIELDS, "limit": self._limit(limit)},
            headers=self._auth_headers(),
        )
        papers: List[RetrievedPaper] = []
        for row in payload.get("data", []):
            item = row.get("citingPaper") or row  # endpoint wraps items in "citingPaper"
            if item.get("title"):
                papers.append(
                    self._item_to_paper(item, RetrievalChannel.CITATIONS, f"citations:{paper_id}")
                )
        return papers

    # ── internals ──────────────────────────────────────────────────────────

    def _auth_headers(self) -> Dict[str, str]:
        return {"x-api-key": self.api_key} if self.api_key else {}

    def _item_to_paper(
        self, item: Dict[str, Any], channel: RetrievalChannel, query: str
    ) -> RetrievedPaper:
        paper_id = item.get("paperId") or ""
        external_ids = item.get("externalIds") or {}
        doi = normalize_doi(external_ids.get("DOI"))
        authors = tuple(
            author.get("name", "") for author in item.get("authors", []) if author.get("name")
        )
        pdf_url = (item.get("openAccessPdf") or {}).get("url")
        url = (
            pdf_url
            or (f"https://doi.org/{doi}" if doi else None)
            or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None)
        )
        citation_count = item.get("citationCount")

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, paper_id, doi),
            title=item.get("title") or "",
            source=self.source,
            source_id=paper_id,
            authors=authors,
            year=item.get("year"),
            venue=item.get("venue") or "",
            doi=doi,
            url=url,
            abstract=item.get("abstract") or "",
            citation_count=(
                int(citation_count) if isinstance(citation_count, (int, float)) else None
            ),
            publication_types=tuple(item.get("publicationTypes") or ()),
            keywords=tuple(external_ids.get("ArXiv") and (f"arxiv:{external_ids['ArXiv']}",) or ()),
            channel=channel,
            query=query,
            extra={
                "s2_paper_id": paper_id,
                "external_ids": dict(external_ids),
            },
        )
