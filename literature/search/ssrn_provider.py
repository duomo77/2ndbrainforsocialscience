"""
ssrn_provider.py — SSRN Provider (EPIC 09)
==========================================
SSRN (Social Science Research Network) does not publish a stable search
API. Its working papers are, however, indexed by OpenAlex under source
``S4210172589`` ("SSRN Electronic Journal", ~1.7M works), which provides
a reliable, citable access path today.

This provider therefore issues SSRN-scoped queries through the OpenAlex
works endpoint and records ``via="openalex"`` in each paper's provenance
extra. The provider contract is unchanged, so a native SSRN client can be
swapped in later without touching the engine or registry.
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
from literature.search.openalex_provider import OPENALEX_BASE_URL, SSRN_SOURCE_ID


class SSRNProvider(LiteratureProvider):
    """SSRN works via the OpenAlex index of the SSRN Electronic Journal."""

    name: ClassVar[str] = "ssrn"
    source: ClassVar[LiteratureSource] = LiteratureSource.SSRN

    def __init__(self, *args: Any, mailto: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = OPENALEX_BASE_URL
        self.source_filter = f"primary_location.source.id:{SSRN_SOURCE_ID}"
        self.mailto = mailto

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        query = seed.search_query
        if not query:
            return []
        params = self._common_params()
        params.update(
            {
                "filter": self.source_filter,
                "search": query,
                "per-page": self._limit(limit),
            }
        )
        payload = self.transport.get_json(f"{self.base_url}/works", params=params)
        return [
            self._work_to_paper(work, RetrievalChannel.SEARCH, query)
            for work in payload.get("results", [])
        ]

    def resolve_doi(self, doi: str) -> Optional[RetrievedPaper]:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        params = self._common_params()
        payload = self.transport.get_json(
            f"{self.base_url}/works/https://doi.org/{normalized}", params=params
        )
        if not isinstance(payload, dict) or not payload.get("id"):
            return None
        if not self._is_ssrn_work(payload):
            return None
        return self._work_to_paper(payload, RetrievalChannel.SEARCH, f"doi:{normalized}")

    # ── internals ──────────────────────────────────────────────────────────

    def _common_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if self.mailto:
            params["mailto"] = self.mailto
        return params

    @staticmethod
    def _is_ssrn_work(work: Dict[str, Any]) -> bool:
        locations = [work.get("primary_location")] + list(work.get("locations") or [])
        for location in locations:
            source_id = ((location or {}).get("source") or {}).get("id", "")
            if source_id == SSRN_SOURCE_ID:
                return True
        return False

    def _work_to_paper(
        self, work: Dict[str, Any], channel: RetrievalChannel, query: str
    ) -> RetrievedPaper:
        raw_id = work.get("id") or ""
        source_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
        doi = normalize_doi(work.get("doi"))
        authors = tuple(
            (authorship.get("author") or {}).get("display_name", "")
            for authorship in work.get("authorships", [])
            if (authorship.get("author") or {}).get("display_name")
        )
        cited = work.get("cited_by_count")
        year = work.get("publication_year")

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, source_id, doi),
            title=work.get("display_name") or "",
            source=self.source,
            source_id=source_id,
            authors=authors,
            year=int(year) if isinstance(year, (int, float)) else None,
            venue="SSRN",
            doi=doi,
            url=raw_id or None,
            abstract="",
            citation_count=int(cited) if isinstance(cited, (int, float)) else None,
            publication_types=tuple(t for t in (work.get("type"),) if t) + ("working_paper",),
            channel=channel,
            query=query,
            extra={"openalex_id": source_id, "via": "openalex", "ssrn_source_id": SSRN_SOURCE_ID},
        )
