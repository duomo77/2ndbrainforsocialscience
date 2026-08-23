"""
arxiv_provider.py — arXiv API Provider (EPIC 09)
================================================
arXiv export API (https://export.arxiv.org/api/query) — Atom XML feed:

  * ``?search_query=ti:"..."`` — title-scoped search for the seed
  * ``?id_list=<arxiv-id>``    — anchor resolution

arXiv serves physics / CS / quantitative social science preprints. It has
no citation counts or native related-papers endpoint, so ``find_related``
re-searches the anchor title. Survey/review detection is keyword-based.

arXiv's API terms ask for ~3 s between requests; the transport is built
with that minimum interval.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import ClassVar, List, Optional

from literature.search.base import LiteratureProvider
from literature.search.models import (
    LiteratureSource,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    make_paper_id,
)
from literature.search.transport import HttpTransport, TransportConfig

ARXIV_BASE_URL = "https://export.arxiv.org/api/query"

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

_REVIEW_HINTS = ("survey", "review", "overview of", "literature review", "tutorial")


class ArXivProvider(LiteratureProvider):
    """arXiv Atom API provider."""

    name: ClassVar[str] = "arxiv"
    source: ClassVar[LiteratureSource] = LiteratureSource.ARXIV

    def __init__(self, transport: Optional[HttpTransport] = None, **kwargs):
        # arXiv asks for ~3 s between requests.
        if transport is None:
            transport = HttpTransport(TransportConfig(min_interval=3.0))
        super().__init__(transport=transport, **kwargs)
        self.base_url = ARXIV_BASE_URL

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        title = seed.title.strip()
        if not title:
            return []
        return self._query(_title_query(title), RetrievalChannel.SEARCH, title, self._limit(limit))

    def find_related(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        title = anchor.title.strip()
        if not title:
            return []
        return self._query(_title_query(title), RetrievalChannel.RELATED, title, self._limit(limit))

    # ── internals ──────────────────────────────────────────────────────────

    def _query(
        self, search_query: str, channel: RetrievalChannel, query_label: str, limit: int
    ) -> List[RetrievedPaper]:
        payload = self.transport.get_text(
            self.base_url,
            params={"search_query": search_query, "start": 0, "max_results": limit},
        )
        return self._parse_feed(payload, channel, query_label)

    def _parse_feed(
        self, xml_text: str, channel: RetrievalChannel, query: str
    ) -> List[RetrievedPaper]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        papers: List[RetrievedPaper] = []
        for entry in root.findall(f"{_ATOM}entry"):
            paper = self._entry_to_paper(entry, channel, query)
            if paper is not None:
                papers.append(paper)
        return papers

    def _entry_to_paper(
        self, entry: ET.Element, channel: RetrievalChannel, query: str
    ) -> Optional[RetrievedPaper]:
        title = _collapse(entry.findtext(f"{_ATOM}title") or "")
        if not title:
            return None

        raw_id = (entry.findtext(f"{_ATOM}id") or "").strip()
        arxiv_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
        # strip version suffix for the canonical id (2101.12345v2 → 2101.12345)
        canonical_id = re.sub(r"v\d+$", "", arxiv_id)

        authors = tuple(
            _collapse(author.findtext(f"{_ATOM}name") or "")
            for author in entry.findall(f"{_ATOM}author")
            if _collapse(author.findtext(f"{_ATOM}name") or "")
        )
        published = entry.findtext(f"{_ATOM}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        abstract = _collapse(entry.findtext(f"{_ATOM}summary") or "")
        doi = entry.findtext(f"{_ARXIV_NS}doi") or None

        categories = tuple(
            category.get("term", "")
            for category in entry.findall(f"{_ATOM}category")
            if category.get("term")
        )
        publication_types = ("preprint",)
        lowered = f"{title} {abstract}".lower()
        if any(hint in lowered for hint in _REVIEW_HINTS):
            publication_types = publication_types + ("review",)

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, canonical_id, doi),
            title=title,
            source=self.source,
            source_id=canonical_id,
            authors=authors,
            year=year,
            venue="arXiv",
            doi=doi,
            url=raw_id or None,
            abstract=abstract,
            citation_count=None,
            publication_types=publication_types,
            keywords=categories,
            channel=channel,
            query=query,
            extra={"arxiv_id": canonical_id, "categories": list(categories)},
        )


def _title_query(title: str) -> str:
    cleaned = title.replace('"', "").strip()
    return f'ti:"{cleaned}"'


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
