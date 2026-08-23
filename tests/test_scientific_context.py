"""
test_scientific_context.py — EPIC 09 Scientific Knowledge Expansion
===================================================================
Network-free coverage for the literature package:

  * provider payload parsing (OpenAlex, Semantic Scholar, Crossref,
    PubMed, arXiv Atom XML, SSRN scoping) via fake transports
  * registry pluggability
  * context classification, evidence scoring, dedup + provenance
  * SCIENTIFIC_CONTEXT.md rendering + atomic outputs
  * knowledge graph mutation
  * document-import seed heuristics and post-import hook
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from core.knowledge_graph import (
    KnowledgeGraphService,
    KnowledgeGraphStore,
    NodeType,
    RelationshipType,
)
from literature.search.arxiv_provider import ArXivProvider
from literature.search.base import LiteratureProvider
from literature.search.crossref_provider import CrossrefProvider
from literature.search.models import (
    LiteratureSource,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    normalize_doi,
)
from literature.search.openalex_provider import OpenAlexProvider, reconstruct_abstract
from literature.search.pubmed_provider import PubMedProvider
from literature.search.registry import LiteratureProviderRegistry, default_registry
from literature.search.semantic_scholar_provider import SemanticScholarProvider
from literature.search.ssrn_provider import SSRNProvider
from literature.search.transport import TransportError

from literature.context.classifier import ContextClassifier, title_overlap
from literature.context.engine import (
    ContextExpansionConfig,
    ScientificContextEngine,
    extract_doi_from_text,
    slugify_title,
)
from literature.context.evidence import EvidenceStrengthScorer
from literature.context.graph import build_graph_mutation
from literature.context.importer import attach_scientific_context, seed_from_document
from literature.context.markdown import render_scientific_context, write_outputs
from literature.context.models import (
    ContextCategory,
    EvidenceLevel,
    ScientificContext,
)


# ── fake transport ────────────────────────────────────────────────────────────


class FakeTransport:
    """Replays canned JSON/text payloads keyed by URL substring."""

    def __init__(self, json_routes: Optional[Dict[str, Any]] = None,
                 text_routes: Optional[Dict[str, str]] = None,
                 errors: Optional[Dict[str, Exception]] = None):
        self.json_routes = json_routes or {}
        self.text_routes = text_routes or {}
        self.errors = errors or {}
        self.calls: List[str] = []

    def _route(self, url: str, params: Optional[Dict[str, Any]]) -> str:
        query = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
        self.calls.append(f"{url}?{query}")
        for key, error in self.errors.items():
            if key in url or key in query:
                raise error
        for key in self.json_routes:
            if key in url or key in query:
                return key
        for key in self.text_routes:
            if key in url or key in query:
                return key
        raise AssertionError(f"unrouted request: {url}?{query}")

    def get_json(self, url, params=None, headers=None):
        return self.json_routes[self._route(url, params)]

    def get_text(self, url, params=None, headers=None):
        return self.text_routes[self._route(url, params)]


SEED = SeedPaper(
    title="Minimum Wages and Employment: A Case Study",
    doi="10.2307/2118030",
    authors=("David Card", "Alan Krueger"),
    year=1994,
)


# ── provider parsing ─────────────────────────────────────────────────────────


def test_openalex_search_parses_work_fields():
    transport = FakeTransport(json_routes={
        "search=Minimum Wages": {"results": [{
            "id": "https://openalex.org/W111",
            "display_name": "Minimum Wage Effects Revisited",
            "doi": "https://doi.org/10.1000/xyz",
            "publication_year": 2015,
            "type": "article",
            "cited_by_count": 321,
            "authorships": [{"author": {"display_name": "Jane Doe"}}],
            "primary_location": {"source": {"display_name": "AER"}},
            "abstract_inverted_index": {"wage": [0], "effects": [1]},
            "related_works": ["https://openalex.org/W222"],
            "referenced_works": ["https://openalex.org/W333"],
        }]},
    })
    provider = OpenAlexProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.title == "Minimum Wage Effects Revisited"
    assert paper.doi == "10.1000/xyz"
    assert paper.year == 2015
    assert paper.citation_count == 321
    assert paper.authors == ("Jane Doe",)
    assert paper.venue == "AER"
    assert paper.publication_types == ("article",)
    assert paper.abstract == "wage effects"
    assert paper.extra["openalex_id"] == "W111"
    assert paper.source == LiteratureSource.OPENALEX


def test_openalex_citing_and_related_channels():
    transport = FakeTransport(json_routes={
        "cites:W111": {"results": [{
            "id": "https://openalex.org/W555", "display_name": "Newer Follow-Up",
            "publication_year": 2020, "cited_by_count": 5,
        }]},
        "openalex:W222": {"results": [{
            "id": "https://openalex.org/W222", "display_name": "Related Work",
            "publication_year": 1999,
        }]},
        "/works/https://doi.org/": {
            "id": "https://openalex.org/W111", "display_name": "Seed",
            "related_works": ["https://openalex.org/W222"], "referenced_works": [],
        },
    })
    provider = OpenAlexProvider(transport=transport)

    anchor = provider.resolve_doi("10.2307/2118030")
    citing = provider.find_citing(anchor, limit=5)
    related = provider.find_related(anchor, limit=5)

    assert anchor is not None and anchor.extra["openalex_id"] == "W111"
    assert citing and citing[0].channel == RetrievalChannel.CITATIONS
    assert related and related[0].channel == RetrievalChannel.RELATED


def test_reconstruct_abstract_handles_missing_index():
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract({"b": [1], "a": [0]}) == "a b"


def test_semantic_scholar_parses_publication_types():
    transport = FakeTransport(json_routes={
        "/paper/search": {"total": 1, "data": [{
            "paperId": "abc123",
            "title": "Meta-Analysis of Minimum Wage",
            "year": 2019,
            "citationCount": 88,
            "venue": "JEP",
            "authors": [{"name": "Alan Roe"}],
            "externalIds": {"DOI": "10.2139/ssrn.99"},
            "publicationTypes": ["MetaAnalysis", "JournalArticle"],
        }]},
    })
    provider = SemanticScholarProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.publication_types == ("MetaAnalysis", "JournalArticle")
    assert paper.doi == "10.2139/ssrn.99"
    assert paper.extra["s2_paper_id"] == "abc123"
    assert paper.citation_count == 88


def test_semantic_scholar_citations_unwrap_citing_paper():
    transport = FakeTransport(json_routes={
        "/citations": {"data": [{"citingPaper": {
            "paperId": "c1", "title": "Citing Work", "year": 2021,
        }}]},
    })
    provider = SemanticScholarProvider(transport=transport)
    anchor = RetrievedPaper(
        paper_id="semantic_scholar:abc", title="Seed", source=LiteratureSource.SEMANTIC_SCHOLAR,
        source_id="abc", extra={"s2_paper_id": "abc"},
    )

    citing = provider.find_citing(anchor, limit=5)

    assert citing and citing[0].title == "Citing Work"
    assert citing[0].channel == RetrievalChannel.CITATIONS


def test_crossref_parses_items():
    transport = FakeTransport(json_routes={
        "/works": {"message": {"items": [{
            "DOI": "10.1257/aer.123",
            "title": ["Minimum Wages and Employment"],
            "author": [{"given": "David", "family": "Card"}],
            "container-title": ["American Economic Review"],
            "type": "journal-article",
            "is-referenced-by-count": 700,
            "published-print": {"date-parts": [[1994, 9]]},
            "abstract": "<jats:p>Hello world</jats:p>",
        }]}},
    })
    provider = CrossrefProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.doi == "10.1257/aer.123"
    assert paper.authors == ("David Card",)
    assert paper.venue == "American Economic Review"
    assert paper.year == 1994
    assert paper.citation_count == 700
    assert paper.publication_types == ("journal-article",)
    assert paper.abstract == "Hello world"


def test_pubmed_search_and_pubtype():
    transport = FakeTransport(json_routes={
        "esearch.fcgi": {"esearchresult": {"idlist": ["123"]}},
        "esummary.fcgi": {"result": {"123": {
            "title": "Systematic Review of Minimum Wage",
            "authors": [{"name": "P Reviewer"}],
            "fulljournalname": "Lancet",
            "pubdate": "2022 Jan",
            "pubtype": ["Journal Article", "Review", "Systematic Review"],
            "articleids": [{"idtype": "doi", "value": "10.1016/abc"}],
        }}},
    })
    provider = PubMedProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    paper = papers[0]
    assert "Review" in paper.publication_types
    assert "Systematic Review" in paper.publication_types
    assert paper.year == 2022
    assert paper.doi == "10.1016/abc"
    assert paper.extra["pmid"] == "123"


ARXIV_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2101.12345v2</id>
    <title>  A Survey of Minimum Wage
      Estimators  </title>
    <summary> We survey estimators. </summary>
    <published>2021-01-29T00:00:00Z</published>
    <author><name>Ann Author</name></author>
    <category term="econ.GN"/>
  </entry>
</feed>
"""


def test_arxiv_parses_atom_feed():
    transport = FakeTransport(text_routes={"export.arxiv.org": ARXIV_FEED})
    provider = ArXivProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.title == "A Survey of Minimum Wage Estimators"
    assert paper.source_id == "2101.12345"
    assert paper.year == 2021
    assert paper.venue == "arXiv"
    assert "preprint" in paper.publication_types
    assert "review" in paper.publication_types  # survey keyword heuristic
    assert paper.keywords == ("econ.GN",)


def test_ssrn_scopes_to_ssrn_source():
    transport = FakeTransport(json_routes={
        "filter=primary_location.source.id:S4210172589": {"results": [{
            "id": "https://openalex.org/W900",
            "display_name": "SSRN Working Paper on Wages",
            "publication_year": 2023,
            "doi": "https://doi.org/10.2139/ssrn.123",
            "cited_by_count": 3,
        }]},
    })
    provider = SSRNProvider(transport=transport)

    papers = provider.search(SEED, limit=5)

    assert len(papers) == 1
    assert papers[0].source == LiteratureSource.SSRN
    assert papers[0].venue == "SSRN"
    assert "working_paper" in papers[0].publication_types
    assert papers[0].extra["via"] == "openalex"
    # the issued query must scope to the SSRN Electronic Journal source
    assert any("primary_location.source.id:S4210172589" in call for call in transport.calls)


# ── registry ─────────────────────────────────────────────────────────────────


def test_default_registry_wires_all_six_sources():
    registry = default_registry(transport_factory=lambda: FakeTransport())
    assert sorted(registry.names()) == sorted(
        ["openalex", "semantic_scholar", "crossref", "pubmed", "arxiv", "ssrn"]
    )
    assert len(registry.available()) == 6


def test_registry_enable_whitelist_and_replace():
    registry = default_registry(
        enabled=("openalex", "crossref"), transport_factory=lambda: FakeTransport()
    )
    assert registry.names() == ["openalex", "crossref"]

    replacement = OpenAlexProvider(transport=FakeTransport())
    with pytest.raises(ValueError):
        registry.register(replacement)
    registry.register(replacement, replace=True)
    assert registry.get("openalex") is replacement

    assert registry.unregister("crossref") is not None
    assert "crossref" not in registry


def test_registry_accepts_custom_provider():
    class StubProvider(LiteratureProvider):
        name = "stub"
        source = LiteratureSource.UNKNOWN

        def search(self, seed, limit=None):
            return []

    registry = LiteratureProviderRegistry([StubProvider(transport=FakeTransport())])
    assert "stub" in registry
    assert registry.get("stub").is_configured()


# ── classifier ───────────────────────────────────────────────────────────────


def _paper(title: str, **overrides: Any) -> RetrievedPaper:
    defaults = dict(
        paper_id=f"test:{title[:10]}",
        title=title,
        source=LiteratureSource.OPENALEX,
    )
    defaults.update(overrides)
    return RetrievedPaper(**defaults)


def test_classifier_detects_review_family():
    classifier = ContextClassifier()

    meta = classifier.classify(
        _paper("A Meta-Analysis of Minimum Wage Effects",
               publication_types=("MetaAnalysis",)), SEED)
    assert ContextCategory.META_ANALYSIS in meta.categories
    assert meta.primary_category == ContextCategory.META_ANALYSIS

    systematic = classifier.classify(
        _paper("The Minimum Wage Literature", publication_types=("Review",),
               abstract="We conduct a systematic review of the evidence."), SEED)
    assert ContextCategory.SYSTEMATIC_REVIEW in systematic.categories
    assert ContextCategory.REVIEW in systematic.categories

    survey = classifier.classify(_paper("A Survey of Minimum Wage Estimators"), SEED)
    assert ContextCategory.REVIEW in survey.categories


def test_classifier_detects_replication_and_contradiction():
    classifier = ContextClassifier()

    replication = classifier.classify(
        _paper("A Replication of the Card-Krueger Study"), SEED)
    assert ContextCategory.REPLICATION in replication.categories

    contradiction = classifier.classify(
        _paper("Minimum Wages Reconsidered",
               abstract="The evidence does not support the original finding; "
                        "we fail to replicate the result."), SEED)
    assert ContextCategory.CONTRADICTORY in contradiction.categories
    assert contradiction.primary_category == ContextCategory.CONTRADICTORY


def test_classifier_influential_and_follow_up():
    classifier = ContextClassifier()

    influential = classifier.classify(
        _paper("Foundational Labor Economics", citation_count=900, year=1990), SEED)
    assert ContextCategory.INFLUENTIAL in influential.categories

    follow_up = classifier.classify(
        _paper("Minimum Wages and Employment: A Case Study Update", year=2020),
        SEED, channels=("citations",))
    assert ContextCategory.FOLLOW_UP in follow_up.categories


def test_title_overlap():
    assert title_overlap("Minimum Wages and Employment", "Minimum Wages and Employment") == pytest.approx(1.0)
    assert title_overlap("Minimum Wages and Employment", "Quantum Gravity Basics") == 0.0


# ── engine orchestration ─────────────────────────────────────────────────────


class FixtureProvider(LiteratureProvider):
    """Deterministic provider returning canned papers per channel."""

    name = "fixture"
    source = LiteratureSource.OPENALEX

    def __init__(self, papers_by_call: List[RetrievedPaper], fail_search: bool = False):
        super().__init__(transport=FakeTransport())
        self.papers = papers_by_call
        self.fail_search = fail_search
        self.calls: List[str] = []

    def search(self, seed, limit=None):
        self.calls.append("search")
        if self.fail_search:
            raise TransportError("boom", status_code=500)
        return list(self.papers)

    def resolve_doi(self, doi):
        self.calls.append("resolve_doi")
        return None

    def find_related(self, anchor, limit=None):
        self.calls.append("find_related")
        return []


class SecondaryProvider(FixtureProvider):
    name = "secondary"
    source = LiteratureSource.SEMANTIC_SCHOLAR


def test_engine_dedupes_across_providers_and_records_provenance():
    from dataclasses import replace as dc_replace

    shared = _paper("Shared Finding Across Sources", doi="10.5555/shared",
                    citation_count=10)
    shared_b = dc_replace(shared, source=LiteratureSource.SEMANTIC_SCHOLAR,
                          source_id="s2-shared")
    unique_a = _paper("Only In Fixture A", doi="10.5555/aaa")
    unique_b = _paper("Only In Fixture B", doi="10.5555/bbb",
                      source=LiteratureSource.SEMANTIC_SCHOLAR)

    registry = LiteratureProviderRegistry([
        FixtureProvider([shared, unique_a]),
        SecondaryProvider([shared_b, unique_b]),
    ])
    engine = ScientificContextEngine(registry=registry)

    result = engine.expand(SEED)

    assert result.ok
    context = result.value
    # shared paper merged once; two uniques; seed itself excluded
    assert context.total_papers == 3
    merged = next(cp for cp in context.papers if cp.title == "Shared Finding Across Sources")
    assert set(merged.sources) == {"openalex", "semantic_scholar"}
    assert merged.paper.citation_count == 10

    statuses = {prov.provider: prov.status for prov in context.provider_provenance}
    assert statuses == {"fixture": "ok", "secondary": "ok"}
    assert all(prov.retrieved == 2 for prov in context.provider_provenance)


def test_engine_captures_provider_errors_in_provenance():
    registry = LiteratureProviderRegistry([
        FixtureProvider([], fail_search=True),
        SecondaryProvider([_paper("Survivor Paper", doi="10.5555/ok")]),
    ])
    engine = ScientificContextEngine(registry=registry)

    result = engine.expand(SEED)

    assert result.ok
    context = result.value
    by_provider = {prov.provider: prov for prov in context.provider_provenance}
    assert by_provider["fixture"].status == "error"
    assert "boom" in by_provider["fixture"].error
    assert by_provider["secondary"].status == "ok"
    assert context.total_papers == 1


def test_engine_rejects_empty_seed():
    engine = ScientificContextEngine(registry=LiteratureProviderRegistry())
    result = engine.expand(SeedPaper())
    assert not result.ok
    assert result.error == "empty_seed"


def test_engine_merges_same_title_with_different_dois():
    nber = _paper("Wages and Jobs: The Fast Food Study", doi="10.3386/w4509",
                  citation_count=1970)
    repec = _paper("Wages and Jobs: The Fast Food Study", doi="10.5555/repec-copy",
                   citation_count=238)
    engine = ScientificContextEngine(
        registry=LiteratureProviderRegistry([FixtureProvider([nber, repec])])
    )

    result = engine.expand(SEED)

    assert result.ok
    assert result.value.total_papers == 1
    merged = result.value.papers[0]
    assert merged.paper.citation_count == 1970  # max wins


def test_engine_excludes_seed_paper_itself():
    self_match = _paper("Minimum Wages and Employment: A Case Study", doi="10.2307/2118030")
    engine = ScientificContextEngine(registry=LiteratureProviderRegistry([FixtureProvider([self_match])]))

    result = engine.expand(SEED)

    assert result.ok
    assert result.value.total_papers == 0


def test_engine_buckets_fill_and_cap():
    papers = [
        _paper(f"Related Paper Number {i}", doi=f"10.6666/r{i}", year=1995 + i)
        for i in range(20)
    ]
    config = ContextExpansionConfig(max_papers_per_category=5)
    engine = ScientificContextEngine(
        registry=LiteratureProviderRegistry([FixtureProvider(papers)]), config=config
    )

    result = engine.expand(SEED)

    assert result.ok
    assert len(result.value.related) == 5
    assert result.value.total_papers == 20  # bucket cap does not drop papers


# ── evidence strength ────────────────────────────────────────────────────────


def _context_paper(title: str, categories: List[ContextCategory], relevance: float = 0.6):
    from literature.context.models import ContextPaper

    return ContextPaper(
        paper=_paper(title),
        categories=categories,
        primary_category=categories[0],
        relevance=relevance,
    )


def test_evidence_strong_with_meta_analysis():
    scorer = EvidenceStrengthScorer()
    papers = [
        _context_paper("MA 1", [ContextCategory.META_ANALYSIS]),
        _context_paper("R 1", [ContextCategory.REVIEW]),
        _context_paper("Rel 1", [ContextCategory.RELATED]),
        _context_paper("Rel 2", [ContextCategory.RELATED]),
    ]
    assessment = scorer.assess(papers)
    assert assessment.level == EvidenceLevel.STRONG
    assert assessment.signals["meta_analysis"] == 1


def test_evidence_contested_with_contradictions():
    scorer = EvidenceStrengthScorer()
    papers = [
        _context_paper("C 1", [ContextCategory.CONTRADICTORY]),
        _context_paper("C 2", [ContextCategory.CONTRADICTORY]),
        _context_paper("Rel 1", [ContextCategory.RELATED]),
    ]
    assert scorer.assess(papers).level == EvidenceLevel.CONTESTED


def test_evidence_insufficient_when_thin():
    scorer = EvidenceStrengthScorer()
    papers = [_context_paper("Only 1", [ContextCategory.RELATED])]
    assert scorer.assess(papers).level == EvidenceLevel.INSUFFICIENT


# ── markdown + persistence ───────────────────────────────────────────────────


def _full_context() -> ScientificContext:
    registry = LiteratureProviderRegistry([
        FixtureProvider([
            _paper("A Meta-Analysis of Minimum Wage", doi="10.7777/ma",
                   publication_types=("MetaAnalysis",), citation_count=150, year=2010),
            _paper("Replication Attempt Fails", doi="10.7777/repl", year=2018,
                   abstract="We fail to replicate the original result."),
            _paper("Related Study on Wages", doi="10.7777/rel", year=1996, citation_count=40),
        ]),
    ])
    engine = ScientificContextEngine(registry=registry)
    result = engine.expand(SEED)
    assert result.ok
    return result.value


def test_markdown_contains_all_required_sections():
    context = _full_context()
    markdown = render_scientific_context(context)

    for section in (
        "## Source Paper",
        "## Evidence Strength",
        "## Related Papers",
        "## Influential Papers",
        "## Review Papers",
        "## Systematic Reviews",
        "## Meta-Analyses",
        "## Replication Papers",
        "## Contradictory Papers",
        "## Newer Follow-Up Work",
        "## Retrieval Provenance",
    ):
        assert section in markdown
    assert "type: scientific_context" in markdown
    assert "[[A Meta-Analysis of Minimum Wage]]" in markdown


def test_markdown_wikilinks_are_sanitized():
    context = _full_context()
    context.papers[0].paper = _paper("Bad [Title] With|Pipe #Here", doi="10.8888/x")
    markdown = render_scientific_context(context)
    # unsafe chars are stripped from the wikilink target; the link survives
    assert "Bad [Title]" not in markdown
    assert "[[Bad Title With Pipe Here]]" in markdown


def test_write_outputs_atomic(tmp_path):
    context = _full_context()
    md_path, json_path = write_outputs(context, tmp_path)

    assert md_path.exists() and json_path.exists()
    assert md_path.name.endswith(".SCIENTIFIC_CONTEXT.md")

    restored = ScientificContext.from_json(json_path.read_text(encoding="utf-8"))
    assert restored.total_papers == context.total_papers
    assert restored.seed.doi == SEED.doi
    assert restored.evidence.level == context.evidence.level


def test_context_json_roundtrip_preserves_provenance():
    context = _full_context()
    restored = ScientificContext.from_json(context.to_json())

    original = context.papers[0]
    copy = next(cp for cp in restored.papers if cp.title == original.title)
    assert copy.sources == original.sources
    assert copy.provenance is not None
    assert copy.provenance.extractor.value == "database_lookup"


# ── knowledge graph ──────────────────────────────────────────────────────────


def test_graph_mutation_types_contradictions_and_follow_ups():
    context = _full_context()
    mutation = build_graph_mutation(context, source_ref="seed.md")

    relationships = {edge.relationship for edge in mutation.edges}
    assert RelationshipType.CONTRADICTS in relationships
    nodes_by_name = {node.name: node for node in mutation.nodes}
    assert nodes_by_name[SEED.title].node_type == NodeType.SOURCE


def test_graph_ingestion_idempotent(tmp_path):
    service = KnowledgeGraphService(KnowledgeGraphStore(tmp_path / "graph.json"))
    context = _full_context()

    from literature.context.graph import ingest_scientific_context

    first = ingest_scientific_context(service, context, source_ref="seed.md")
    second = ingest_scientific_context(service, context, source_ref="seed.md")

    assert first["nodes_upserted"] == second["nodes_upserted"]
    assert service.store.stats()["total_nodes"] == first["total_nodes"]


# ── importer integration ─────────────────────────────────────────────────────


@dataclass
class StubDocument:
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def record_warning(self, message: str) -> None:
        self.warnings.append(message)


def test_seed_from_document_uses_metadata_then_text():
    document = StubDocument(metadata={
        "title": "Minimum Wages and Employment: A Case Study",
        "doi": "https://doi.org/10.2307/2118030",
        "authors": ["David Card", "Alan Krueger"],
        "parsed_text": "Some abstract text here.",
    })
    seed = seed_from_document(document)

    assert seed.title == "Minimum Wages and Employment: A Case Study"
    assert seed.doi == "10.2307/2118030"
    assert seed.authors == ("David Card", "Alan Krueger")


def test_seed_from_document_falls_back_to_text_heuristics():
    document = StubDocument(metadata={
        "parsed_text": "Deep Learning for Tabular Data\n\nWe present 10.1234/abc.def and results.",
    })
    seed = seed_from_document(document)

    assert seed.title == "Deep Learning for Tabular Data"
    assert seed.doi == "10.1234/abc.def"


def test_attach_scientific_context_records_paths(tmp_path):
    document = StubDocument(metadata={"title": "A Study of Something Important"})
    engine = ScientificContextEngine(
        registry=LiteratureProviderRegistry([FixtureProvider([
            _paper("A Related Paper", doi="10.9999/rel"),
        ])]),
        config=ContextExpansionConfig(output_dir=tmp_path),
    )

    result_doc = attach_scientific_context(document, engine=engine, output_dir=tmp_path)

    record = result_doc.metadata["scientific_context"]
    assert record["status"] == "ok"
    assert record["paper_count"] == 1
    assert "markdown_path" in record and record["markdown_path"].endswith(".SCIENTIFIC_CONTEXT.md")
    import os
    assert os.path.exists(record["markdown_path"])


def test_attach_scientific_context_warns_on_empty_seed():
    document = StubDocument(metadata={})
    engine = ScientificContextEngine(registry=LiteratureProviderRegistry())

    result_doc = attach_scientific_context(document, engine=engine)

    assert any("skipped" in warning for warning in result_doc.warnings)
    assert "scientific_context" not in result_doc.metadata


def test_extract_doi_and_slugify():
    assert extract_doi_from_text("See 10.1257/aer.90.5 for details") == "10.1257/aer.90.5"
    assert extract_doi_from_text("no doi here") is None
    assert slugify_title("Minimum Wages & Employment: A Study!") == "minimum-wages-employment-a-study"
    assert normalize_doi("https://doi.org/10.1000/XYZ") == "10.1000/xyz"
