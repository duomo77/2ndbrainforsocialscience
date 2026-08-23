"""
crossref_provider.py — Crossref Literature Provider (EPIC 09)
=============================================================
Crossref REST API (https://api.crossref.org) — the canonical DOI registry:

  * ``GET /works?query.bibliographic=...`` — relevance search
  * ``GET /works/<doi>``                   — anchor resolution

Crossref contributes authoritative bibliographic metadata, the
``type`` field (``journal-article``, ``review``, ...) and
``is-referenced-by-count`` citation counts. The polite pool is used
when ``mailto`` is configured.
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

CROSSREF_BASE_URL = "https://api.crossref.org"


class CrossrefProvider(LiteratureProvider):
    """Crossref works API provider."""

    name: ClassVar[str] = "crossref"
    source: ClassVar[LiteratureSource] = LiteratureSource.CROSSREF

    def __init__(self, *args: Any, mailto: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = CROSSREF_BASE_URL
        self.mailto = mailto

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        query = seed.search_query
        if not query:
            return []
        payload = self.transport.get_json(
            f"{self.base_url}/works",
            params=self._with_mailto({"query.bibliographic": query, "rows": self._limit(limit)}),
        )
        items = (payload.get("message") or {}).get("items", [])
        return [self._item_to_paper(item, RetrievalChannel.SEARCH, query) for item in items]

    def resolve_doi(self, doi: str) -> Optional[RetrievedPaper]:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        payload = self.transport.get_json(
            f"{self.base_url}/works/{normalized}",
            params=self._with_mailto({}),
        )
        item = (payload.get("message") or {}) if isinstance(payload, dict) else {}
        if not item.get("DOI"):
            return None
        return self._item_to_paper(item, RetrievalChannel.SEARCH, f"doi:{normalized}")

    # ── internals ──────────────────────────────────────────────────────────

    def _with_mailto(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.mailto:
            params["mailto"] = self.mailto
        return params

    def _item_to_paper(
        self, item: Dict[str, Any], channel: RetrievalChannel, query: str
    ) -> RetrievedPaper:
        doi = normalize_doi(item.get("DOI"))
        titles = item.get("title") or []
        title = titles[0] if isinstance(titles, list) and titles else str(titles or "")

        authors = tuple(
            " ".join(
                part for part in (author.get("given", ""), author.get("family", "")) if part
            ).strip()
            for author in item.get("author", [])
            if isinstance(author, dict)
        )
        authors = tuple(name for name in authors if name)

        containers = item.get("container-title") or []
        venue = containers[0] if isinstance(containers, list) and containers else ""

        year = _extract_year(item)
        cited = item.get("is-referenced-by-count")
        work_type = item.get("type") or ""

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, doi or item.get("DOI", ""), doi),
            title=title,
            source=self.source,
            source_id=doi or item.get("DOI", ""),
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            abstract=_strip_jats(item.get("abstract") or ""),
            citation_count=int(cited) if isinstance(cited, (int, float)) else None,
            publication_types=(work_type,) if work_type else (),
            channel=channel,
            query=query,
            extra={"crossref_type": work_type},
        )


def _extract_year(item: Dict[str, Any]) -> Optional[int]:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        date_parts = (item.get(key) or {}).get("date-parts") or [[]]
        if date_parts and date_parts[0] and date_parts[0][0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def _strip_jats(abstract: str) -> str:
    """Crossref abstracts arrive as JATS XML; drop tags for plain text."""
    import re

    text = re.sub(r"<jats:title>.*?</jats:title>", " ", abstract, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
