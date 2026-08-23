"""
openalex_provider.py — OpenAlex Literature Provider (EPIC 09)
=============================================================
OpenAlex (https://openalex.org) is the primary open scholarly graph:

  * ``GET /works?search=...``                  — relevance search
  * ``GET /works/https://doi.org/<doi>``       — anchor resolution by DOI
  * ``GET /works?filter=cites:<W-id>``         — citing papers (follow-up)
  * ``GET /works?filter=openalex:<W-id|...>``  — resolve related/referenced
                                                  work URL batches

OpenAlex is also the index behind the SSRN provider (SSRN has no public
search API; its working papers are indexed as OpenAlex source S4210172589).

Verified live: work object carries ``type``, ``cited_by_count``,
``related_works``, ``referenced_works``, ``abstract_inverted_index``.
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

OPENALEX_BASE_URL = "https://api.openalex.org"
SSRN_SOURCE_ID = "S4210172589"  # "SSRN Electronic Journal" in OpenAlex


class OpenAlexProvider(LiteratureProvider):
    """OpenAlex works API provider."""

    name: ClassVar[str] = "openalex"
    source: ClassVar[LiteratureSource] = LiteratureSource.OPENALEX

    def __init__(self, *args: Any, mailto: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = OPENALEX_BASE_URL
        self.mailto = mailto  # polite pool: OpenAlex asks for a contact email

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        query = seed.search_query
        if not query:
            return []
        params = self._common_params()
        params.update({"search": query, "per-page": self._limit(limit)})
        payload = self.transport.get_json(f"{self.base_url}/works", params=params)
        return [
            self._work_to_paper(work, RetrievalChannel.SEARCH, query)
            for work in payload.get("results", [])
            if work.get("title") or work.get("display_name")
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
        return self._work_to_paper(payload, RetrievalChannel.SEARCH, f"doi:{normalized}")

    def find_related(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        work_urls = anchor.extra.get("related_works") or []
        return self._resolve_work_batch(work_urls, RetrievalChannel.RELATED, self._limit(limit))

    def find_referenced(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        work_urls = anchor.extra.get("referenced_works") or []
        return self._resolve_work_batch(work_urls, RetrievalChannel.REFERENCES, self._limit(limit))

    def find_citing(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        openalex_id = anchor.extra.get("openalex_id", "")
        if not openalex_id:
            return []
        params = self._common_params()
        params.update(
            {
                "filter": f"cites:{openalex_id}",
                "sort": "cited_by_count:desc",
                "per-page": self._limit(limit),
            }
        )
        payload = self.transport.get_json(f"{self.base_url}/works", params=params)
        return [
            self._work_to_paper(work, RetrievalChannel.CITATIONS, f"cites:{openalex_id}")
            for work in payload.get("results", [])
        ]

    # ── internals ──────────────────────────────────────────────────────────

    def _common_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if self.mailto:
            params["mailto"] = self.mailto
        return params

    def _resolve_work_batch(
        self, work_urls: List[str], channel: RetrievalChannel, limit: int
    ) -> List[RetrievedPaper]:
        openalex_ids = [
            url.rsplit("/", 1)[-1] for url in work_urls if isinstance(url, str) and "/W" in url
        ][:limit]
        if not openalex_ids:
            return []
        params = self._common_params()
        params.update({"filter": f"openalex:{'|'.join(openalex_ids)}", "per-page": limit})
        payload = self.transport.get_json(f"{self.base_url}/works", params=params)
        return [
            self._work_to_paper(work, channel, "openalex:batch")
            for work in payload.get("results", [])
        ]

    def _work_to_paper(
        self, work: Dict[str, Any], channel: RetrievalChannel, query: str
    ) -> RetrievedPaper:
        raw_id = work.get("id") or ""
        source_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
        doi = normalize_doi(work.get("doi"))
        title = work.get("display_name") or work.get("title") or ""

        authors = tuple(
            (authorship.get("author") or {}).get("display_name", "")
            for authorship in work.get("authorships", [])
            if (authorship.get("author") or {}).get("display_name")
        )
        venue = ((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        year = work.get("publication_year")
        cited = work.get("cited_by_count")

        publication_types = tuple(t for t in (work.get("type"),) if t)

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, source_id, doi),
            title=title,
            source=self.source,
            source_id=source_id,
            authors=authors,
            year=int(year) if isinstance(year, (int, float)) else None,
            venue=venue,
            doi=doi,
            url=raw_id or None,
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            citation_count=int(cited) if isinstance(cited, (int, float)) else None,
            publication_types=publication_types,
            keywords=tuple(
                (concept.get("display_name") or "")
                for concept in work.get("concepts", [])[:8]
                if concept.get("display_name")
            ),
            channel=channel,
            query=query,
            extra={
                "openalex_id": source_id,
                "related_works": list(work.get("related_works") or []),
                "referenced_works": list(work.get("referenced_works") or []),
            },
        )


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """Rebuild abstract text from OpenAlex's inverted word-index format."""
    if not inverted_index:
        return ""
    positions: List[tuple] = []
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions.append((idx, word))
    positions.sort(key=lambda pair: pair[0])
    return " ".join(word for _, word in positions)
