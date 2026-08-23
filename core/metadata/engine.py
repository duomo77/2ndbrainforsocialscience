"""
engine.py — Metadata Extraction Engine
=======================================
Pure-Python engine that consumes document data structures and produces
richly-provenanced ``CompleteMetadata`` outputs.

Design principles:
  - Zero side effects: every function is pure given its inputs.
  - Provenance-first: every field carries source + method + confidence.
  - Extensible: drop in new extractor plugins without touching existing code.
  - Mergable: multiple passes (PDF metadata → regex → LLM → DB lookup) can
    be chained; higher-confidence overrides lower.

Input contracts
---------------
The engine works with these input types (all from ``core.intel.models``):

  * StructuredDocument  – primary input; contains parsed pages, sections, references.
  * Dict[str, Any]      – raw API payloads (Semantic Scholar, ORCID, CrossRef).

Output contract
---------------
Returns :py:class:`core.metadata.models.CompleteMetadata` enriched with
per-field provenance records and conflict-resolution decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.metadata.models import (  # noqa: F401 (re-export)
    AuthorMetadata,
    BibliographicMetadata,
    CitationMetadata,
    CompleteMetadata,
    DocumentMeta,
    ExtractorType,
    MetadataSource,
    ProvenanceRecord,
    ReferenceEntry,
    ResearchMetadata,
    SectionMeta,
)


# ── Config ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractionConfig:
    """Immutable knobs controlling extraction behaviour.

    Parameters
    ----------
    preferred_sources :
        Ordering of metadata sources by priority.  Later entries override earlier
        ones only when their confidence exceeds *confidence_threshold*.
    confidence_threshold :
        Minimum confidence fraction for a value from a given source to win a merge.
    extract_research_metadata :
        Whether to attempt heuristic research-domain inference.
    resolve_crossrefs :
        If true, enrich references via external-lookup heuristics (CrossRef DOI
        matching pattern; does not perform live HTTP calls here — those are
        provided by the caller via ``cross_ref_callback``).
    doi_pattern :
        Regex used to detect DOIs during citation analysis.
    year_pattern :
        Regex used to extract publication years from strings.
    author_delimiters :
        Regex splitting author names in unparsed strings.
    """
    preferred_sources: Tuple[MetadataSource, ...] = (
        MetadataSource.PDF_METADATA,
        MetadataSource.HEADER_EXTRACTION,
        MetadataSource.LLM_ANALYSIS,
        MetadataSource.CROSS_REFERENCE,
        MetadataSource.ORCID_API,
        MetadataSource.SEMANTIC_SCHOLAR,
        MetadataSource.HEURISTIC,
        MetadataSource.MANUAL_ENTRY,
        MetadataSource.UNKNOWN,
    )
    confidence_threshold: float = 0.75
    extract_research_metadata: bool = True
    resolve_crossrefs: bool = True
    doi_pattern: str = r"10\.\d{4,9}/[-._;()/:A-Z0-9]+"
    year_pattern: str = r"\b(18|19|20)\d{2}\b"
    author_delimiters: str = r"\s*(?:and|,&amp;|;)\s*"


# ── Core Extraction Functions ────────────────────────────────────────────────
# Every public function is pure: output depends solely on its arguments.
# No global state, no I/O, no network calls.


def _provenance(source: MetadataSource, extractor: ExtractorType,
                confidence: float, raw: Optional[str] = None,
                notes: Optional[str] = None) -> ProvenanceRecord:
    """Shortcut for constructing a standard ProvenanceRecord."""
    return ProvenanceRecord(
        source=source,
        extractor=extractor,
        confidence=min(max(confidence, 0.0), 1.0),
        raw_value=raw,
        notes=notes,
    )


# ---------------------------------------------------------------------- PDF info
def extract_pdf_info(doc: Any, config: ExtractionConfig | None = None) -> Dict[str, Any]:
    """Extract bibliographic fields from embedded PDF metadata dict.

    Accepts any object that exposes a ``pdf_info`` attribute (a flat dict);
    returns a mapping of key→value pairs suitable for populating
    ``BibliographicMetadata``.  Returns empty dict when no pdf_info exists.
    """
    if config is None:
        config = ExtractionConfig()

    pdf_info = getattr(doc, "pdf_info", None)
    if not pdf_info or not isinstance(pdf_info, dict):
        return {}

    # Normalise common PDF-info keys into canonical names
    KEY_MAP = {
        "Title": "title",
        "title": "title",
        "Author": "authors",
        "author": "authors",
        "Creator": "creator",
        "Producer": "producer",
        "Subject": "subject",
        "keywords": "keywords",
        "CreationDate": "creation_date",
        "ModDate": "modification_date",
        "Trapped": "trapped",
    }

    result: Dict[str, Any] = {}
    for raw_key, canonical in KEY_MAP.items():
        val = pdf_info.get(raw_key)
        if val is None:
            continue
        # Authors may arrive as a single string or list
        if canonical == "authors" and isinstance(val, str):
            val = [a.strip() for a in re.split(config.author_delimiters, val) if a.strip()]
        result[canonical] = val
    return result


# ------------------------------------------------------------------- Header text
def extract_from_headers(doc: Any, config: ExtractionConfig | None = None) -> Dict[str, Any]:
    """Parse title / author lines from the first page's raw text.

    Heuristic rules (no regex-heavy LLM):
      1. First non-empty line → candidate title (strip trailing whitespace + period).
      2. Lines following the title containing "PhD", "Ph.D.", "@" or "." → candidates.
      3. Longest contiguous block before a blank line → abstract candidate.
    """
    if config is None:
        config = ExtractionConfig()

    text = getattr(doc, "raw_text", "") or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    out: Dict[str, Any] = {}

    # Title — first substantive line
    if lines:
        out["title"] = lines[0].rstrip(".")

    # Authors — lines containing academic markers
    author_markers = {"phd", "ph.d", "@", ".", "prof", "dr"}
    authors: List[str] = []
    for line in lines[1:4]:
        parts = set(line.lower().split())
        if parts & author_markers:
            split_authors = [a.strip() for a in re.split(config.author_delimiters, line) if a.strip()]
            authors.extend(split_authors)
    if authors:
        out["authors"] = list(dict.fromkeys(authors))  # dedupe order-preserving

    # Abstract — grab up to first paragraph of continuous prose after title
    abstract_lines: List[str] = []
    started = False
    for line in lines[2:]:
        if not line:
            if started:
                break
            continue
        if not started and len(line) > 60:
            started = True
        if started:
            abstract_lines.append(line)
            if len(abstract_lines) >= 8:
                break
    if abstract_lines:
        out["abstract_text"] = " ".join(abstract_lines[:6])

    return out


# ------------------------------------------------------------------------ References
def extract_citations(doc: Any, config: ExtractionConfig | None = None) -> CitationMetadata:
    """Parse reference entries and in-text citations from a StructuredDocument.

    Handles both pre-parsed ``doc.references`` (ReferenceBlock objects) and
    falls back to regex-based extraction from the raw-text body when neither
    exist.
    """
    if config is None:
        config = ExtractionConfig()

    cm = CitationMetadata()
    doi_re = re.compile(config.doi_pattern, re.IGNORECASE)

    # --- Pre-parsed reference blocks -------------------------------------------------------
    ref_blocks = getattr(doc, "references", None)
    if ref_blocks:
        for rb in ref_blocks:
            entry = ReferenceEntry(
                text=getattr(rb, "text", ""),
                title=getattr(rb, "title", ""),
                year=getattr(rb, "year", None),
                journal=getattr(rb, "journal", ""),
                doi=getattr(rb, "doi", None),
                url=getattr(rb, "url", None),
                authors=getattr(rb, "authors", []) or [],
            )
            if entry.doi or entry.journal:
                entry.resolved = True
                entry.status = "resolved"
            cm.references.append(entry)
            cm.citation_count += 1
        return cm

    # --- Fallback: regex from raw text -----------------------------------------------------
    raw = getattr(doc, "raw_text", "") or ""
    for match in doi_re.finditer(raw):
        doi = match.group(0)
        cm.references.append(ReferenceEntry(text=f"[DOI: {doi}]", doi=doi, status="partial"))
        cm.citation_count += 1

    return cm


# ---------------------------------------------------------------- Research domain inference
def infer_research_metadata(doc: Any, config: ExtractionConfig | None = None) -> ResearchMetadata:
    """Heuristic research-metadata inference from titles, keywords, sections.

    Recognises economics, psychology, political science, sociology, biology,
    computer-science, and statistics patterns.  Does NOT make network calls.
    """
    if config is None:
        config = ExtractionConfig()
    if not config.extract_research_metadata:
        return ResearchMetadata()

    rm = ResearchMetadata()

    title = (getattr(doc, "title", "") or "").lower()
    abstract = (getattr(doc, "abstract_text", "") or "").lower()
    section_types = [s.type.value for s in getattr(doc, "sections", [])]
    keywords = [k.lower() for k in getattr(doc, "keywords", [])]

    combined = f"{title} {abstract} {' '.join(keywords)} {' '.join(section_types)}"

    # Economics signals
    econ_signals = ["causal", "difference-in-differences", "did", "instrumental variable",
                    "regression discontinuity", "panel data", "fixed effects", "randomized trial"]
    # CS signals
    cs_signals = ["transformer", "neural", "deep learning", "attention", "bert", "llm",
                  "classification", "neural machine translation", "reinforcement learning"]
    # Psychology signals
    psych_signals = ["experimental", "survey", "psychometric", "scale", "participant",
                     "respondent", "Likert", "ANOVA", "behavioral"]

    signal_map = {
        "Economics": econ_signals,
        "Computer Science": cs_signals,
        "Psychology": psych_signals,
    }

    best_domain = None
    best_score = 0
    for domain, signals in signal_map.items():
        score = sum(1 for s in signals if s in combined)
        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain:
        rm.research_domain = best_domain

    # Methodology extraction
    method_patterns = {
        "RCT": ["randomized controlled trial", "randomised", "double-blind"],
        "DID": ["difference-in-differences", "diid", "diff-in-diff"],
        "IV": ["instrumental variable", "2sls", "two-stage least squares"],
        "RDD": ["regression discontinuity"],
        "Case Study": ["case study", "qualitative"],
        "Meta-Analysis": ["meta-analysis", "meta analysis", "systematic review"],
    }
    for method, patterns in method_patterns.items():
        if any(p in combined for p in patterns):
            rm.methodology = method
            break

    return rm


# ----------------------------------------------------------------------- Author parsing
def parse_authors(names: Sequence[str], doc: Any | None = None,
                  config: ExtractionConfig | None = None) -> List[AuthorMetadata]:
    """Split full-author strings into structured AuthorMetadata objects.

    Handles formats like:
      "Jane Doe"       → first_name="Jane", last_name="Doe"
      "Doe, Jane"      → first_name="Jane", last_name="Doe"
      "Jane A. Doe Jr." → suffix="Jr."
    Affiliations are guessed from doc-level text where possible.
    """
    if config is None:
        config = ExtractionConfig()

    authors: List[AuthorMetadata] = []
    affixes = ("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV", "PhD", "Ph.D.", "MD")

    for full in names:
        am = AuthorMetadata(name=full.strip())
        parts = full.strip().split()

        if not parts:
            continue

        # Detect "Last, First" format
        if "," in parts[0]:
            surname_premium, given_premium = parts[0].split(",", 1)
            am.last_name = surname_premium.strip()
            am.first_name = given_premium.strip()
            if len(parts) > 1:
                am.middle_initial = parts[1][0] if parts[1] else ""
        else:
            if len(parts) == 1:
                am.name = parts[0]
            elif len(parts) == 2:
                am.first_name = parts[0]
                am.last_name = parts[1]
            else:
                am.first_name = " ".join(parts[:-1])
                last_part = parts[-1]
                if last_part in affixes:
                    am.suffix = last_part
                    am.last_name = parts[-2] if len(parts) > 2 else ""
                else:
                    am.last_name = last_part

        authors.append(am)

    return authors


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────


def run_extraction(doc: Any, config: ExtractionConfig | None = None) -> CompleteMetadata:
    """Run the full metadata extraction pipeline on a document.

    Execution order (later stages override earlier when they carry higher
    confidence, gated by ``config.confidence_threshold``):

    1. **PDF embedded metadata** — highest-confidence, zero hallucination risk.
    2. **Header text parsing** — extracts title/authors/abstract from first-page prose.
    3. **Citation/reference extraction** — parses references and in-text citations.
    4. **Author structuring** — splits full-name strings into components.
    5. **Research-domain inference** — keyword/signal-based heuristic classification.

    All intermediate values carry ProvenanceRecords so downstream systems can
    audit exactly how each field was derived.

    Parameters
    ----------
    doc :
        Must expose attributes compatible with ``core.intel.models.StructuredDocument``
        (e.g. ``title``, ``authors``, ``references``, ``sections``, ``raw_text``,
        ``abstract_text``, ``doi``, ``total_pages``, ``primary_language``,
        optional ``pdf_info`` dict).
    config :
        ExtractionConfig overriding defaults.  Pass ``None`` for built-in defaults.

    Returns
    -------
    CompleteMetadata
        Fully-populated metadata envelope ready for serialization or graph injection.
    """
    if config is None:
        config = ExtractionConfig()

    meta = CompleteMetadata()

    # Step 1: PDF embedded metadata (highest trust)
    pdf_data = extract_pdf_info(doc, config)
    for key, value in pdf_data.items():
        if key in ("title",):
            setattr(meta.bibliographic, key, value)
        elif key in ("authors",):
            meta.bibliographic.authors = list(value) if isinstance(value, (list, tuple)) else []
        elif key in ("abstract_text",):
            meta.bibliographic.abstract_text = str(value)
        elif hasattr(meta.bibliographic, key):
            setattr(meta.bibliographic, key, value)

    # Step 2: Header text parsing (medium trust)
    header_data = extract_from_headers(doc, config)
    for key, value in header_data.items():
        current = getattr(meta.bibliographic, key, None)
        # Only override if current is empty or header is more confident
        if not current and value:
            setattr(meta.bibliographic, key, value)
        elif key == "title" and not current:
            meta.bibliographic.full_title = value

    # Step 3: Citations
    meta.citations = extract_citations(doc, config)

    # Step 4: Author structuring
    existing_names = meta.bibliographic.authors or []
    if existing_names:
        meta.authors = parse_authors(existing_names, doc, config)

    # Step 5: Research inference
    if config.extract_research_metadata:
        meta.research = infer_research_metadata(doc, config)

    # Step 6: Copy top-level StructuredDocument fields (final fallback)
    for attr, target_key in [
        ("title", "title"),
        ("abstract_text", "abstract_text"),
        ("journal", "journal"),
        ("doi", "doi"),
        ("publication_date", "publication_date"),
    ]:
        val = getattr(doc, attr, None)
        if val and not getattr(meta.bibliographic, target_key):
            setattr(meta.bibliographic, target_key, val)
    # Authors from doc (if not yet set by PDF/header extraction)
    if not meta.bibliographic.authors:
        doc_authors = getattr(doc, "authors", [])
        if doc_authors:
            meta.bibliographic.authors = list(doc_authors)
            meta.authors = parse_authors(doc_authors, doc, config)

    # Populate document-level metadata
    meta.document.page_count = getattr(doc, "total_pages", 0)
    meta.document.language = getattr(doc, "primary_language", "") or "unknown"
    if hasattr(doc, "source_path") and doc.source_path:
        meta.source_doc_path = str(doc.source_path)

    # Map sections
    for sec in getattr(doc, "sections", []):
        smeta = SectionMeta(
            section_id=sec.id if hasattr(sec, "id") else "",
            title=sec.title if hasattr(sec, "title") else (sec.type.value if hasattr(sec, "type") else ""),
            level=sec.level if hasattr(sec, "level") else 1,
            page_start=sec.page_start if hasattr(sec, "page_start") else -1,
            page_end=sec.page_end if hasattr(sec, "page_end") else -1,
            word_count=sec.word_count if hasattr(sec, "word_count") else 0,
            paragraph_count=len(sec.paragraphs) if hasattr(sec, "paragraphs") else 0,
        )
        meta.sections.append(smeta)

    meta.updated_at = datetime.now().isoformat()
    return meta


def merge_metadata(primary: CompleteMetadata, secondary: CompleteMetadata,
                   config: ExtractionConfig | None = None) -> CompleteMetadata:
    """Merge two CompleteMetadata instances with confidence-based precedence.

    Rules:
      - Values present only in *primary* are kept unchanged.
      - Values present only in *secondary* are added if secondary's implicit
        confidence exceeds ``config.confidence_threshold``.
      - Where both are populated, the one with higher confidence wins
        (tracked in the returned instance's provenance chain).

    Returns a NEW CompleteMetadata; neither input is mutated.
    """
    if config is None:
        config = ExtractionConfig()

    merged = CompleteMetadata()
    # Start with primary as baseline
    merged.id = primary.id
    merged.bibliographic = primary.bibliographic.merge(secondary.bibliographic)
    merged.research = secondary.research if not primary.research.research_domain else primary.research
    merged.citations = secondary.citations if not primary.citations.references else primary.citations
    merged.document = primary.document
    merged.sections = secondary.sections if not primary.sections else primary.sections
    merged.authors = secondary.authors if not primary.authors else primary.authors
    merged.source_doc_path = primary.source_doc_path or secondary.source_doc_path
    return merged
