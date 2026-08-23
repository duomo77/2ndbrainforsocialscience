"""
pubmed_provider.py — PubMed (NCBI E-utilities) Provider (EPIC 09)
=================================================================
PubMed via E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils):

  * ``esearch.fcgi`` — search; returns PMID list
  * ``esummary.fcgi`` — document summaries (title, pubtype, DOI, ...)
  * ``elink.fcgi``  — related-article links (``pubmed_pubmed``)

``pubtype`` values ("Review", "Meta-Analysis", "Systematic Review", ...)
make PubMed the strongest source for review-family classification in the
biomedical literature. An optional ``api_key`` raises the rate ceiling.
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

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedProvider(LiteratureProvider):
    """NCBI E-utilities provider."""

    name: ClassVar[str] = "pubmed"
    source: ClassVar[LiteratureSource] = LiteratureSource.PUBMED

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.base_url = EUTILS_BASE_URL

    # ── contract ───────────────────────────────────────────────────────────

    def search(self, seed: SeedPaper, limit: Optional[int] = None) -> List[RetrievedPaper]:
        query = seed.search_query
        if not query:
            return []
        pmids = self._esearch(query, self._limit(limit))
        if not pmids:
            return []
        return self._esummary(pmids, RetrievalChannel.SEARCH, query)

    def resolve_doi(self, doi: str) -> Optional[RetrievedPaper]:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        pmids = self._esearch(f"{normalized}[doi]", 1)
        if not pmids:
            return None
        papers = self._esummary(pmids, RetrievalChannel.SEARCH, f"doi:{normalized}")
        return papers[0] if papers else None

    def find_related(
        self, anchor: RetrievedPaper, limit: Optional[int] = None
    ) -> List[RetrievedPaper]:
        pmid = anchor.extra.get("pmid", "")
        if not pmid:
            return []
        params = self._common_params()
        params.update(
            {
                "db": "pubmed",
                "dbfrom": "pubmed",
                "id": pmid,
                "retmode": "json",
                "linkname": "pubmed_pubmed",
            }
        )
        payload = self.transport.get_json(f"{self.base_url}/elink.fcgi", params=params)
        related_pmids: List[str] = []
        for linkset in payload.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("linkname") == "pubmed_pubmed":
                    related_pmids.extend(linksetdb.get("links", []))
        related_pmids = related_pmids[: self._limit(limit)]
        if not related_pmids:
            return []
        return self._esummary(related_pmids, RetrievalChannel.ELINK, f"elink:{pmid}")

    # ── internals ──────────────────────────────────────────────────────────

    def _common_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _esearch(self, term: str, retmax: int) -> List[str]:
        params = self._common_params()
        params.update(
            {
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": retmax,
                "sort": "relevance",
            }
        )
        payload = self.transport.get_json(f"{self.base_url}/esearch.fcgi", params=params)
        return list((payload.get("esearchresult") or {}).get("idlist", []))

    def _esummary(
        self, pmids: List[str], channel: RetrievalChannel, query: str
    ) -> List[RetrievedPaper]:
        params = self._common_params()
        params.update({"db": "pubmed", "id": ",".join(pmids), "retmode": "json"})
        payload = self.transport.get_json(f"{self.base_url}/esummary.fcgi", params=params)
        results = payload.get("result") or {}

        papers: List[RetrievedPaper] = []
        for pmid in pmids:
            record = results.get(str(pmid)) or results.get(pmid)
            if not record:
                continue
            paper = self._record_to_paper(str(pmid), record, channel, query)
            if paper is not None:
                papers.append(paper)
        return papers

    def _record_to_paper(
        self, pmid: str, record: Dict[str, Any], channel: RetrievalChannel, query: str
    ) -> Optional[RetrievedPaper]:
        title = record.get("title") or ""
        if not title:
            return None

        authors = tuple(
            author.get("name", "") for author in record.get("authors", []) if author.get("name")
        )
        article_ids = {
            entry.get("idtype"): entry.get("value")
            for entry in record.get("articleids", [])
            if isinstance(entry, dict)
        }
        doi = normalize_doi(article_ids.get("doi"))
        pubtypes = tuple(
            str(pubtype).strip() for pubtype in record.get("pubtype", []) if str(pubtype).strip()
        )
        year = _parse_year(record.get("pubdate") or "")

        return RetrievedPaper(
            paper_id=make_paper_id(self.source, pmid, doi),
            title=title,
            source=self.source,
            source_id=pmid,
            authors=authors,
            year=year,
            venue=record.get("fulljournalname") or record.get("source") or "",
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            abstract="",  # esummary omits abstracts; classification uses pubtype
            citation_count=None,
            publication_types=pubtypes,
            channel=channel,
            query=query,
            extra={"pmid": pmid, "pmc": article_ids.get("pmc")},
        )


def _parse_year(pubdate: str) -> Optional[int]:
    import re

    match = re.search(r"(18|19|20)\d{2}", pubdate or "")
    return int(match.group(0)) if match else None
