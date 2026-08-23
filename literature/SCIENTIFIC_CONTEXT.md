# SCIENTIFIC_CONTEXT.md — Scientific Knowledge Expansion (EPIC 09)

**Date**: 2026-08-19
**Version**: 1.0.0
**Status**: Implemented

---

## Overview

The Scientific Knowledge Expansion engine automatically expands every imported
document into its surrounding scientific context. Given one research paper, it
retrieves and classifies:

- **Related Papers** — topically similar work
- **Influential Papers** — high-citation works and the seed's own references
- **Review Papers** — narrative reviews and surveys
- **Systematic Reviews** — systematic literature reviews
- **Meta-Analyses** — quantitative syntheses
- **Replication Papers** — replication and reproducibility studies
- **Contradictory Papers** — findings that challenge or fail to replicate the seed
- **Newer Follow-Up Work** — papers citing or extending the seed after publication

It then scores the overall **Evidence Strength** of the retrieved base and
records **provenance for every retrieved document and every provider call**.

### Design Principles

1. **Provider-pluggable** — one `LiteratureProvider` contract + a registry; new sources are drop-in additions
2. **Provenance-first** — every paper carries source, channel, query, and a standard ROS `ProvenanceRecord`
3. **Deterministic classification** — transparent publication-type + keyword rules with recorded rationales; no LLM in the loop
4. **Fault-isolated** — provider failures become provenance records, never crashes; optional circuit breaking via `core.fault_recovery`
5. **Backward compatible** — zero behavior change to existing pipelines unless expansion is explicitly opted into

---

## Architecture

```
Seed Paper (title / DOI / authors / year)
    │
    ▼
┌────────────────────────────────────────────────────────┐
│               ScientificContextEngine                   │
│  1. anchor resolution by DOI      4. dedup + merge      │
│  2. provider fan-out              5. classification     │
│  3. collect + provenance          6. evidence scoring   │
└───┬────────┬────────┬────────┬────────┬────────┬───────┘
    │        │        │        │        │        │
    ▼        ▼        ▼        ▼        ▼        ▼
 OpenAlex  Semantic  Crossref  PubMed   ArXiv    SSRN
           Scholar                     (Atom)  (via OpenAlex
                                                SSRN index)
    │
    ▼
ScientificContext
 ├── related / influential / reviews / systematic_reviews
 ├── meta_analyses / replications / contradictory / follow_ups
 ├── evidence: EvidenceAssessment (level, score, rationale)
 └── provider_provenance: per-provider status, queries, latency
    │
    ▼
<slug>.SCIENTIFIC_CONTEXT.md  +  <slug>.scientific_context.json
    │                                   │
    ▼                                   ▼
Knowledge Graph mutation        JSON snapshot (round-trippable)
(seed → typed edges)
```

### Component Flow

1. **Anchor resolution** — the seed DOI is resolved through each provider to
   obtain provider-native identifiers (OpenAlex W-id, S2 paperId, PMID, ...)
2. **Fan-out retrieval** — per provider: bibliographic `search`, plus
   provider-native `find_related` / `find_citing` / `find_referenced`
3. **Normalization** — native payloads mapped onto `RetrievedPaper`
   (title, authors, year, venue, DOI, abstract, citations, publication types)
4. **Deduplication** — merge by DOI key, then normalized-title cross-check
   (working-paper vs published variants); channels and sources are unioned
5. **Classification** — `ContextClassifier` assigns categories, primary
   category, relevance score, and rationale
6. **Evidence scoring** — `EvidenceStrengthScorer` aggregates category counts
   into STRONG / MODERATE / LIMITED / CONTESTED / EMERGING / INSUFFICIENT
7. **Rendering** — Obsidian-ready Markdown with `[[WikiLinks]]` and a
   retrieval provenance table; atomic `.tmp → os.replace` writes
8. **Graph lift** — `build_graph_mutation` maps categories to typed edges
   (CONTRADICTS, EXTENDS, INSPIRED_BY, SUPPORTS, RELATED_TO)

---

## Module Layout

```
literature/
├── __init__.py                       # public API
├── SCIENTIFIC_CONTEXT.md             # this document
├── search/
│   ├── models.py                     # SeedPaper, RetrievedPaper, LiteratureSource
│   ├── transport.py                  # retrying HTTP transport (429/5xx backoff, pacing)
│   ├── base.py                       # LiteratureProvider contract
│   ├── openalex_provider.py          # works search, DOI, cites:, related/referenced batches
│   ├── semantic_scholar_provider.py  # search, DOI:, recommendations, citations
│   ├── crossref_provider.py          # bibliographic search, DOI resolution
│   ├── pubmed_provider.py            # esearch + esummary + elink related articles
│   ├── arxiv_provider.py             # Atom feed parsing, 3 s courtesy pacing
│   ├── ssrn_provider.py              # SSRN via OpenAlex index (S4210172589)
│   └── registry.py                   # LiteratureProviderRegistry, default_registry()
└── context/
    ├── models.py                     # ContextCategory, ContextPaper, ScientificContext,
    │                                 # EvidenceAssessment, ProviderProvenance
    ├── classifier.py                 # deterministic categorization rules
    ├── evidence.py                   # evidence strength scoring rubric
    ├── engine.py                     # ScientificContextEngine orchestration
    ├── markdown.py                   # SCIENTIFIC_CONTEXT.md renderer + atomic writer
    ├── graph.py                      # knowledge graph mutation + ingestion
    └── importer.py                   # document pipeline integration hooks
```

---

## Sources

| Provider | Endpoints used | Signals contributed | Auth |
|---|---|---|---|
| **OpenAlex** | `works` search; `works/doi:`; `filter=cites:`; `filter=openalex:` batches | type, citations, related/referenced work URLs, inverted abstract | none (polite `mailto`) |
| **Semantic Scholar** | `/paper/search`; `/paper/DOI:`; `/paper/{id}/recommendations`; `/paper/{id}/citations` | `publicationTypes` (Review / MetaAnalysis / SystematicReview), citation counts | optional `x-api-key` |
| **Crossref** | `works` bibliographic search; `works/{doi}` | authoritative DOI metadata, `type`, `is-referenced-by-count` | none (polite `mailto`) |
| **PubMed** | `esearch.fcgi`; `esummary.fcgi`; `elink.fcgi` (`pubmed_pubmed`) | `pubtype` (Review / Meta-Analysis / Systematic Review), related-article links | optional `api_key` |
| **ArXiv** | Atom `query` API | preprints, survey/review heuristics, categories | none (3 s pacing) |
| **SSRN** | OpenAlex works filtered to source `S4210172589` (SSRN Electronic Journal) | social-science working papers; `via: openalex` recorded in provenance | none |

> SSRN exposes no stable public search API; indexing through OpenAlex is
> recorded transparently in each paper's provenance. The provider contract is
> unchanged, so a native SSRN client can replace the transport later.

### Adding a provider

```python
from literature.search import LiteratureProvider, LiteratureSource

class RePEcProvider(LiteratureProvider):
    name = "repec"
    source = LiteratureSource.UNKNOWN

    def search(self, seed, limit=None):
        ...  # return list[RetrievedPaper]

registry.register(RePEcProvider(transport=my_transport))
```

---

## Classification Rules

| Category | Primary signals |
|---|---|
| SYSTEMATIC_REVIEW | S2 `SystematicReview` / PubMed `Systematic Review` / "systematic review" phrases |
| META_ANALYSIS | S2 `MetaAnalysis` / PubMed `Meta-Analysis` / "meta-analysis" phrases |
| REVIEW | OpenAlex/Crossref `review` types / PubMed `Review` / survey phrases |
| REPLICATION | "replicate/replication/reproducib/registered report" patterns |
| CONTRADICTORY | "contradict", "fail(s) to replicate", "does not support", "no evidence of", "reconsider", "cast doubt", ... |
| INFLUENTIAL | citations ≥ 500 (strong) / ≥ 100 (moderate) / surfaced via the seed's references |
| FOLLOW_UP | retrieved through citing channels, or newer year + title-topic overlap ≥ 0.30 |
| RELATED | baseline category for every retained candidate |

Primary-category precedence:
`contradictory > meta_analysis > systematic_review > review > replication >
influential > follow_up > related`.

Relevance blends channel diversity, title overlap with the seed, citation
weight, and recency; each decision is recorded in `rationale` and
`matched_signals` for audit.

---

## Evidence Strength Rubric

| Level | Condition |
|---|---|
| STRONG | ≥ 1 meta-analysis or systematic review, zero contradictions |
| MODERATE | ≥ 1 review, or ≥ 5 corroborating related papers without contradictions |
| CONTESTED | ≥ 2 contradictions (or ≥ 1 with no synthesis-level support) |
| EMERGING | mostly newer follow-up work, no synthesis yet |
| LIMITED | thin context, no synthesis |
| INSUFFICIENT | fewer than 3 context papers |

---

## Provenance

Two layers, both persisted in outputs:

1. **Per paper** — a standard `core.metadata.models.ProvenanceRecord`
   (`source` = provider-mapped `MetadataSource`, `extractor` = `database_lookup`,
   `confidence` = relevance, `raw_value` = canonical paper id,
   `notes` = providers + channels + query), plus merged `sources` / `channels`.
2. **Per provider call** — `ProviderProvenance`: status (`ok` / `error` /
   `skipped`), queries issued, papers retrieved, latency, timestamp, error text.

---

## Integration

### Standalone

```python
from literature import ScientificContextEngine, seed_from_fields, write_outputs

seed = seed_from_fields(title="...", doi="10.2307/2118030", year=1994)
result = ScientificContextEngine().expand(seed)          # Ok(ScientificContext) | Err
if result.ok:
    md_path, json_path = write_outputs(result.value)     # ~/.ros_memory/scientific_context/
```

### Document import (opt-in)

```python
from core.pipeline.pipeline import process_document

document = process_document("paper.pdf", expand_scientific_context=True)
record = document.metadata["scientific_context"]
# {"status", "paper_count", "evidence_level", "markdown_path", "json_path", ...}
```

The flag defaults to `False`; the historical pipeline behavior is byte-for-byte
unchanged. Expansion runs post-import and is fault-isolated: it can only add
warnings, never fail the import.

### Engine loader

```python
from core.engine_loader import get_scientific_context_engine

engine = get_scientific_context_engine()   # lazy, failure-isolated, registry-tracked
```

### Knowledge graph

```python
from core.knowledge_graph import get_knowledge_graph_service
from literature.context.graph import ingest_scientific_context

ingest_scientific_context(get_knowledge_graph_service(), context, source_ref="seed.md")
```

Edge typing: `CONTRADICTS` (contradictory), `EXTENDS` (follow-up),
`INSPIRED_BY` (influential), `SUPPORTS` (replication), `RELATED_TO` (reviews / related).

---

## Backward Compatibility

- `core.pipeline.process_document` gained an optional kwarg only (default preserves old behavior)
- `MetadataSource` gained additive enum members (`openalex`, `crossref_api`, `pubmed_api`, `arxiv`, `ssrn`); existing values unchanged
- `core.engine_loader` gained one additive getter
- No existing module behavior was modified; all pre-existing tests pass unchanged

## Dependencies

- `requests>=2.31.0` (added to `requirements.txt`)

## Testing

`tests/test_scientific_context.py` — 36 network-free tests covering provider
payload parsing (fake transports), registry pluggability, classification,
deduplication and provenance, evidence scoring, markdown rendering, atomic
outputs, graph mutation/ingestion, and pipeline seed heuristics.

Verified live against all six sources on 2026-08-19 (Semantic Scholar's public
pool intermittently returns HTTP 429; the engine records it as provenance and
continues — by design).
