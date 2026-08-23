"""
models.py — Metadata Extraction Data Models
=============================================
Rich metadata schemas for academic and professional documents.

Every field carries a ``ProvenanceRecord`` for auditability. Designed for
indexing, search, citation analysis, knowledge-graph generation, AI agents.

Wraps / enriches ``core.intel.models.StructuredDocument`` with provenance,
confidence scores, and cross-referencing capabilities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class MetadataSource(Enum):
    PDF_METADATA = "pdf_metadata"
    HEADER_EXTRACTION = "header_extraction"
    LLM_ANALYSIS = "llm_analysis"
    CROSS_REFERENCE = "cross_reference"
    ORCID_API = "orcid_api"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    # EPIC 09 — scientific literature providers (additive; backward compatible)
    OPENALEX = "openalex"
    CROSSREF_API = "crossref_api"
    PUBMED_API = "pubmed_api"
    ARXIV = "arxiv"
    SSRN = "ssrn"
    MANUAL_ENTRY = "manual_entry"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"

class ExtractorType(Enum):
    REGEX = "regex"
    PATTERN_MATCHING = "pattern_matching"
    STRUCTURED_PARSING = "structured_parsing"
    LLM_INFERENCE = "llm_inference"
    DATABASE_LOOKUP = "database_lookup"
    HEURISTIC_RULES = "heuristic_rules"

class ValidationSeverity(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

# ── Provenance ────────────────────────────────────────────────────────────────

@dataclass
class ProvenanceRecord:
    source: MetadataSource
    extractor: ExtractorType
    confidence: float                     # 0.0–1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_version: str = "1.0.0"
    manual_override: bool = False
    raw_value: Optional[str] = None       # Original unprocessed token
    notes: Optional[str] = None           # Human-readable context

@dataclass
class MetadataField:
    key: str
    value: Any
    provenance: ProvenanceRecord
    normalized: bool = False
    override_source: Optional[MetadataSource] = None

# ── Bibliographic Metadata ───────────────────────────────────────────────────

@dataclass
class BibliographicMetadata:
    """Bibliographic fields mapped from ``core.intel.models.StructuredDocument``
    plus subtitle, ISSN, language codes, license, keywords.
    """
    title: Optional[str] = None
    subtitle: Optional[str] = None
    full_title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    affiliations: List[str] = field(default_factory=list)
    publisher: Optional[str] = None
    journal: Optional[str] = None
    conference: Optional[str] = None
    book_title: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    edition: Optional[int] = None
    pages: Optional[str] = None
    publication_date: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    issn: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None        # ISO 639-1
    license: Optional[str] = None
    abstract_text: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def merge(self, other: BibliographicMetadata) -> BibliographicMetadata:
        return BibliographicMetadata(**{
            k: getattr(other, k) if getattr(other, k) not in (None, []) else getattr(self, k)
            for k in self.__dataclass_fields__
        })

    def to_dict(self, include_provenance: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {k: v for k, v in self.__dict__.items()}
        if include_provenance:
            d["_provenance"] = {}
        return d


# ── Research Metadata ─────────────────────────────────────────────────────────
@dataclass
class ResearchMetadata:
    research_domain: Optional[str] = None
    subfield: Optional[str] = None
    research_questions: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    methodology: Optional[str] = None
    data_source: Optional[str] = None
    dataset_name: Optional[str] = None
    study_population: Optional[str] = None
    country: Optional[str] = None         # ISO 3166-1 alpha-2
    region: Optional[str] = None
    time_period: Optional[str] = None
    variables: Dict[str, List[str]] = field(default_factory=dict)
    outcome_variables: List[str] = field(default_factory=list)
    treatment_variables: List[str] = field(default_factory=list)
    control_variables: List[str] = field(default_factory=list)
    identification_strategy: Optional[str] = None
    robustness_checks: List[str] = field(default_factory=list)


# ── Citation Metadata ─────────────────────────────────────────────────────────
@dataclass
class ReferenceEntry:
    text: str
    authors: List[str] = field(default_factory=list)
    title: str = ""
    year: Optional[int] = None
    journal: str = ""
    doi: Optional[str] = None
    url: Optional[str] = None
    resolved: bool = False
    status: str = "unresolved"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationInstance:
    author: str = ""
    year: Optional[str] = None
    page: Optional[int] = None
    context_before: str = ""
    context_after: str = ""
    paragraph_index: int = -1
    is_narrative: bool = False


@dataclass
class CitationMetadata:
    references: List[ReferenceEntry] = field(default_factory=list)
    in_text_citations: List[CitationInstance] = field(default_factory=list)
    citation_count: int = 0
    bibliography_style: Optional[str] = None

    @property
    def resolution_rate(self) -> float:
        total = len(self.references)
        return sum(1 for r in self.references if r.resolved) / max(total, 1)


# ── Author / Document / Section ───────────────────────────────────────────────
@dataclass
class AuthorMetadata:
    name: str = ""
    first_name: str = ""
    middle_initial: str = ""
    last_name: str = ""
    suffix: str = ""
    orcid: Optional[str] = None
    email: Optional[str] = None
    affiliation: str = ""
    institution: str = ""
    country: Optional[str] = None
    department: str = ""
    research_interests: List[str] = field(default_factory=list)


@dataclass
class DocumentMeta:
    document_type: str = "unknown"
    page_count: int = 0
    word_count: int = 0
    character_count: int = 0
    language: str = "unknown"
    reading_time_minutes: float = 0.0
    file_size_bytes: int = 0
    ocr_confidence: float = 0.0
    parser_version: str = "1.0.0"
    pipeline_version: str = "1.0.0"
    processing_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SectionMeta:
    """Per-section element counts; mirrors ``core.intel.models.Section``."""
    section_id: str = ""
    title: str = ""
    level: int = 1
    parent_section_id: Optional[str] = None
    page_start: int = -1
    page_end: int = -1
    paragraph_count: int = 0
    table_count: int = 0
    figure_count: int = 0
    equation_count: int = 0
    word_count: int = 0
    character_count: int = 0
    language: str = "unknown"


# ── Complete Metadata Envelope ────────────────────────────────────────────────


@dataclass
class CompleteMetadata:
    """Canonical output wrapping all sub-type models.

    Consumed by downstream systems (indexing, search, KG, embeddings, AI agents).
    Built from ``core.intel.models.StructuredDocument`` via
    ``from_structured_document()`` or populated manually.
    """
    id: str = field(default_factory=lambda: f"meta-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(datetime.now().isoformat()) % 10000:04d}")

    bibliographic: BibliographicMetadata = field(default_factory=BibliographicMetadata)
    research: ResearchMetadata = field(default_factory=ResearchMetadata)
    citations: CitationMetadata = field(default_factory=CitationMetadata)
    document: DocumentMeta = field(default_factory=DocumentMeta)
    sections: List[SectionMeta] = field(default_factory=list)
    authors: List[AuthorMetadata] = field(default_factory=list)

    source_doc_path: Optional[str] = None
    validated: bool = False
    validation_report: Optional[Any] = None

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_structured_document(cls, doc: Any) -> 'CompleteMetadata':
        """Assemble metadata from ``core.intel.models.StructuredDocument``."""
        meta = cls(source_doc_path=str(doc.source_path) if doc.source_path else None)
        meta.bibliographic.title = doc.title or ""
        meta.bibliographic.abstract_text = doc.abstract_text or ""
        meta.bibliographic.journal = doc.journal or ""
        meta.bibliographic.doi = doc.doi
        meta.bibliographic.publication_date = doc.publication_date
        meta.bibliographic.authors = list(doc.authors)
        meta.authors.extend(AuthorMetadata(name=a) for a in doc.authors)
        meta.document.page_count = doc.total_pages
        meta.document.language = doc.primary_language or "unknown"
        meta.sections = [
            SectionMeta(section_id=getattr(s, "id", ""),
                        title=getattr(s.type, "value", "") if hasattr(s, "type") else "",
                        level=getattr(s, "level", 1),
                        page_start=getattr(s, "page_start", -1),
                        page_end=getattr(s, "page_end", -1),
                        word_count=getattr(s, "word_count", 0),
                        paragraph_count=len(getattr(s, "paragraphs", [])))
            for s in doc.sections
        ]
        meta.citations.references = [
            ReferenceEntry(text=getattr(r, "text", ""), title=getattr(r, "title", ""),
                           year=getattr(r, "year"), doi=getattr(r, "doi"),
                           journal=getattr(r, "journal", ""),
                           authors=getattr(r, "authors", []))
            for r in doc.references
        ]
        qual = getattr(doc, "quality", None)
        if qual:
            meta.document.ocr_confidence = getattr(qual, "ocr_confidence", 0.0) or 0.0
        return meta

    def to_json(self, indent: int = 2) -> str:
        payload = {
            "id": self.id,
            "bibliographic": self._sd(self.bibliographic),
            "research": self._sd(self.research),
            "citations": {
                "references": [self._sd(r) for r in self.citations.references],
                "citation_count": self.citations.citation_count,
                "bibliography_style": self.citations.bibliography_style,
            },
            "document": self._sd(self.document),
            "sections": [self._sd(s) for s in self.sections],
            "authors": [self._sd(a) for a in self.authors],
            "source_doc_path": self.source_doc_path,
            "validated": self.validated,
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)

    @staticmethod
    def _sd(obj: Any) -> Any:
        if not hasattr(obj, '__dataclass_fields__'):
            return obj
        out: Dict[str, Any] = {}
        for fn, fv in obj.__dict__.items():
            if isinstance(fv, list):
                out[fn] = [i.__dict__ if hasattr(i, '__dataclass_fields__') else i for i in fv]
            elif hasattr(fv, '__dataclass_fields__'):
                out[fn] = CompleteMetadata._sd(fv)
            else:
                out[fn] = fv
        return out

    @classmethod
    def from_json(cls, json_str: str) -> 'CompleteMetadata':
        data = json.loads(json_str)
        meta = cls()
        meta.id = data.get("id", meta.id)
        meta.source_doc_path = data.get("source_doc_path")
        meta.validated = data.get("validated", False)
        return meta


# ── Validation ────────────────────────────────────────────────────────────────
@dataclass
class ValidationResult:
    is_valid: bool = True
    issues: List[Dict[str, Any]] = field(default_factory=list)
    fields_checked: int = 0
    errors_found: int = 0
    warnings_found: int = 0

    def add_issue(self, severity: ValidationSeverity, field_name: str, message: str) -> None:
        self.issues.append({
            "severity": severity.name,
            "field": field_name,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })
        if severity.value >= ValidationSeverity.ERROR.value:
            self.errors_found += 1
            self.is_valid = False
        else:
            self.warnings_found += 1
