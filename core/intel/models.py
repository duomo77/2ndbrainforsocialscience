"""
intel/models.py — Structured Document Data Models
===================================================
Canonical schema for all processed documents. Every object has a stable ID,
relationships to parent/child objects, and optional spatial coordinates.

This is the unified output that downstream components consume:
    Metadata Engine → Citation Analysis → Knowledge Graph → Embeddings → AI Agents
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


# ── Enums ────────────────────────────────────────────────────────────────────

class DocumentCategory(Enum):
    """High-level document category."""
    RESEARCH_PAPER = "research_paper"
    BOOK = "book"
    REPORT = "report"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    TECHNICAL_DOCUMENT = "technical_document"
    LEGAL = "legal"
    MEDICAL = "medical"
    CODE = "code"
    TRANSCRIPT = "transcript"
    EMAIL = "email"
    NEWS_ARTICLE = "news_article"
    UNKNOWN = "unknown"


class PDFType(Enum):
    """Specific PDF rendering type."""
    DIGITAL = "digital"           # Native digital text
    SCANNED = "scanned"           # All pages are images needing OCR
    HYBRID = "hybrid"             # Mix of native text and scanned pages
    TEXT_ONLY = "text_only"       # Same as digital but no embedded fonts
    IMAGE_ONLY = "image_only"     # Entirely images, even if not from scanner


class SectionType(Enum):
    """Logical section types in academic/professional documents."""
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    BACKGROUND = "background"
    LITERATURE_REVIEW = "literature_review"
    METHODOLOGY = "methodology"
    METHODS = "methods"
    DATA = "data"
    RESULTS = "results"
    FINDINGS = "findings"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    ACKNOWLEDGMENTS = "acknowledgments"
    REFERENCES = "references"
    APPENDIX = "appendix"
    SUPPLEMENTARY = "supplementary_material"
    FIGURE_CAPTION = "figure_caption"
    TABLE_CAPTION = "table_caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"
    GENERAL = "general"          # Doesn't match any canonical section


class LanguageDirection(Enum):
    """Text writing direction."""
    LTR = "ltr"      # Left-to-right (English, most European languages)
    RTL = "rtl"      # Right-to-left (Arabic, Hebrew)
    TTB = "ttb"      # Top-to-bottom (Traditional Chinese vertical)


# ── Quality Assessment ───────────────────────────────────────────────────────

@dataclass
class QualityMetric:
    """Single quality measurement."""
    name: str
    score: float                   # 0.0–1.0
    confidence: float              # How confident we are in the score
    details: Optional[str] = None
    severity: str = "info"         # "info", "warning", "error"

    @property
    def passes(self) -> bool:
        return self.score >= 0.5


@dataclass
class QualityReport:
    """Aggregate quality assessment of extracted content."""
    overall_score: float = 0.0
    ocr_confidence: Optional[float] = None
    parser_confidence: float = 1.0
    layout_confidence: float = 0.8
    completeness_ratio: float = 1.0   # Fraction of expected content found
    missing_pages: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: List[QualityMetric] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        """True if quality meets minimum threshold for downstream use."""
        return self.overall_score >= 0.3 and len(self.errors) == 0

    def add_metric(self, name: str, score: float, confidence: float = 1.0,
                   details: Optional[str] = None, severity: str = "info") -> None:
        m = QualityMetric(name=name, score=score, confidence=confidence,
                          details=details, severity=severity)
        self.metrics.append(m)
        if m.severity == "error":
            self.errors.append(f"{name}: {m.details or 'quality check failed'}")
        elif m.severity == "warning":
            self.warnings.append(f"{name}: {m.details or 'potential issue'}")


# ── Layout Elements ──────────────────────────────────────────────────────────

@dataclass
class Paragraph:
    """A block of continuous prose on a page."""
    id: str = field(default_factory=lambda: f"para-{uuid.uuid4().hex[:8]}")
    text: str = ""
    page_number: int = -1
    top: int = -1
    left: int = -1
    width: int = -1
    height: int = -1
    style: str = "normal"    # "normal", "heading", "caption", "footnote", "citation"
    language: str = ""
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableBlock:
    """A table extracted from a document page."""
    id: str = field(default_factory=lambda: f"table-{uuid.uuid4().hex[:8]}")
    cells: List[List[str]] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    row_count: int = 0
    col_count: int = 0
    page_number: int = -1
    top: int = -1
    left: int = -1
    caption: str = ""
    merged_cells: List[tuple] = field(default_factory=list)  # (r1,c1,r2,c2)
    format: str = "grid"        # "grid", "list", "matrix"
    export_formats: List[str] = field(default_factory=lambda: ["json", "csv", "markdown"])
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableCell:
    """A single cell in a table (for detailed extraction)."""
    row: int = 0
    col: int = 0
    rowspan: int = 1
    colspan: int = 1
    text: str = ""
    is_header: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FigureBlock:
    """An image/chart/graphic detected on a page."""
    id: str = field(default_factory=lambda: f"fig-{uuid.uuid4().hex[:8]}")
    kind: str = "image"            # "image", "chart", "graph", "diagram", "equation", "photo"
    page_number: int = -1
    top: int = -1
    left: int = -1
    width: int = -1
    height: int = -1
    caption: str = ""
    alt_text: str = ""
    reference_count: int = 0      # How many times referenced in text
    image_bytes: Optional[bytes] = None   # Raw bytes for multimodal processing
    image_path: Optional[Path] = None     # Saved path if extracted
    bounding_box: Optional[tuple] = None  # (top, left, bottom, right)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EquationBlock:
    """A mathematical expression extracted from a document."""
    id: str = field(default_factory=lambda: f"eqn-{uuid.uuid4().hex[:8]}")
    latex: str = ""               # LaTeX representation (if available)
    raw_latex: str = ""           # Original recognized LaTeX before any normalization
    normalized_latex: str = ""    # Parser-normalized LaTeX, if available
    plain_text: str = ""          # Plain text fallback
    image_bytes: Optional[bytes] = None   # Visual representation
    page_number: int = -1
    top: int = -1
    left: int = -1
    context_before: str = ""      # Text immediately before equation
    context_after: str = ""       # Text immediately after equation
    reference_id: Optional[str] = None   # e.g., "(Eq. 3)" for cross-references
    type: str = "inline"          # "inline", "display", "numbered", "unnumbered"
    confidence: float = 0.0
    verification_status: str = "RAW_OCR"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceBlock:
    """A bibliographic reference entry."""
    id: str = field(default_factory=lambda: f"ref-{uuid.uuid4().hex[:8]}")
    text: str = ""                # Full citation text
    authors: List[str] = field(default_factory=list)
    title: str = ""
    year: Optional[int] = None
    journal: str = ""
    doi: Optional[str] = None
    url: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    citation_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Page & Section ───────────────────────────────────────────────────────────

@dataclass
class Page:
    """A single page from the source document."""
    page_number: int
    text: str = ""
    paragraphs: List[Paragraph] = field(default_factory=list)
    tables: List[TableBlock] = field(default_factory=list)
    figures: List[FigureBlock] = field(default_factory=list)
    equations: List[EquationBlock] = field(default_factory=list)
    references: List[ReferenceBlock] = field(default_factory=list)
    has_ocr: bool = False
    ocr_confidence: float = 0.0
    is_blank: bool = False
    is_scanned: bool = False
    reading_order: List[str] = field(default_factory=list)  # IDs of elements in reading order
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    """A logical section spanning one or more pages."""
    id: str = field(default_factory=lambda: f"sec-{uuid.uuid4().hex[:8]}")
    type: SectionType = SectionType.GENERAL
    title: str = ""
    level: int = 1               # Heading depth (1 = top-level)
    page_start: int = -1
    page_end: int = -1
    paragraphs: List[Paragraph] = field(default_factory=list)
    subsections: List["Section"] = field(default_factory=list)
    tables: List[TableBlock] = field(default_factory=list)
    figures: List[FigureBlock] = field(default_factory=list)
    equations: List[EquationBlock] = field(default_factory=list)
    word_count: int = 0
    character_count: int = 0
    language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        return bool(
            self.paragraphs or self.subsections or self.tables
            or self.figures or self.equations or self.title
        )


# ── Structured Document ─────────────────────────────────────────────────────

@dataclass
class StructuredDocument:
    """
    Canonical output of the Document Intelligence Engine.

    Every processed document becomes this unified schema regardless of input format.
    This is the single source of truth for: Metadata Engine, Citation Analysis,
    Knowledge Graph, Entity Extraction, Embedding, Hybrid Search, AI Agents.
    """
    id: str = field(default_factory=lambda: f"doc-{uuid.uuid4().hex[:8]}")
    source_path: Optional[Path] = None
    original_filename: str = ""

    # Metadata
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract_text: str = ""
    publication_date: Optional[str] = None
    journal: str = ""
    doi: Optional[str] = None
    category: DocumentCategory = DocumentCategory.UNKNOWN
    pdf_type: Optional[PDFType] = None
    total_pages: int = 0

    # Content structure
    sections: List[Section] = field(default_factory=list)
    tables: List[TableBlock] = field(default_factory=list)
    figures: List[FigureBlock] = field(default_factory=list)
    equations: List[EquationBlock] = field(default_factory=list)
    pages: List[Page] = field(default_factory=list)
    references: List[ReferenceBlock] = field(default_factory=list)
    appendices: List[Section] = field(default_factory=list)

    # Cross-document links
    cited_by: List[str] = field(default_factory=list)      # Other doc IDs citing this
    cites: List[str] = field(default_factory=list)         # Other doc IDs referenced by this

    # Language
    primary_language: str = ""
    secondary_languages: List[str] = field(default_factory=list)
    writing_direction: LanguageDirection = LanguageDirection.LTR

    # Quality
    quality: QualityReport = field(default_factory=QualityReport)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Raw pipeline artifacts (for debugging / re-processing)
    raw_text: str = ""
    parser_used: str = ""
    ocr_engine: Optional[str] = None
    processing_time_ms: float = 0.0

    def summarize(self) -> str:
        """Human-readable summary of document contents."""
        table_count = len(self.tables) or sum(len(s.tables) for s in self.sections)
        figure_count = len(self.figures) or sum(len(s.figures) for s in self.sections)
        equation_count = len(self.equations) or sum(len(s.equations) for s in self.sections)
        parts = [
            f"[StructuredDoc {self.id}] Filename: {self.original_filename}",
            f"Pages: {self.total_pages}, Sections: {len(self.sections)}",
            f"Tables: {table_count}, Figures: {figure_count}, Equations: {equation_count}",
            f"References: {len(self.references)}",
            f"Language: {self.primary_language or 'unknown'}",
            f"Quality: {'PASS' if self.quality.is_acceptable else 'FAIL'} "
            f"(overall={self.quality.overall_score:.2f})",
        ]
        return "\n".join(parts)


# ── Classification Result ────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Result of automatic document classification."""
    category: DocumentCategory = DocumentCategory.UNKNOWN
    pdf_type: Optional[PDFType] = None
    confidence: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)
    detected_sections: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Language Detection ───────────────────────────────────────────────────────

@dataclass
class LanguageResult:
    """Result of language detection with confidence scores."""
    primary_language: str = ""              # ISO 639-1 code
    primary_confidence: float = 0.0
    secondary_languages: List[str] = field(default_factory=list)
    secondary_confidences: Dict[str, float] = field(default_factory=dict)
    encoding: str = "utf-8"
    writing_direction: LanguageDirection = LanguageDirection.LTR
    is_mixed: bool = False                  # Contains multiple languages
    sample_size: int = 0
