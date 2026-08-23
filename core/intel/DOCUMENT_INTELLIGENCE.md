# DOCUMENT_INTELLIGENCE.md — Document Intelligence Engine (EPIC 05)

**Date**: 2026-07-31  
**Version**: 1.0.0  
**Status**: Implemented

---

## Overview

The Document Intelligence Engine transforms raw documents into structured, machine-readable knowledge objects. It serves as the **canonical source of document understanding** for all future AI components in the Research Operating System.

### Design Principles

1. **Separate parsing from semantic extraction** — parsers extract raw text; intelligence layers add meaning
2. **Preserve document hierarchy** — sections nest within pages, tables/figures reference parent sections
3. **Produce structured document objects** — every processed document becomes a `StructuredDocument`
4. **Support interchangeable components** — pluggable parsers and OCR engines via `ServiceContainer`
5. **Backward compatible** — zero changes to existing `core/pipeline/` or `core/parsers.py`

---

## Architecture

```
Raw Document (.pdf/.docx/.txt/.csv/.py/.srt/etc.)
    │
    ▼
┌──────────────────────────────────────────────────┐
│           DocumentIntelligenceManager             │
│   (Orchestrator — selects parser, runs pipeline)  │
└──────┬─────────┬──────────┬──────────┬───────────┘
       │         │          │          │
       ▼         ▼          ▼          ▼
 ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
 │Parser  │ │OCR     │ │Layout  │ │Quality │
 │Framework│ │Engine  │ │Analyzer│ │Report  │
 └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘
      │          │          │          │
      ▼          ▼          ▼          ▼
   Text    →  Enriched  →  Analyzed  →  StructuredDoc
   + Meta     Text        Text        (semantic layer)
```

### Component Flow

1. **Classification** — determine category & PDF type
2. **Cache check** — skip reprocessing if result exists
3. **OCR routing** — scan if needed (scanned/hybrid/image-only PDFs)
4. **Parser selection** — choose best parser by file extension
5. **Text normalization** — clean hyphenation, broken lines, invisible chars
6. **Language detection** — primary + secondary languages with confidence
7. **Layout analysis** — detect headings, paragraphs, lists, tables, footnotes
8. **Section extraction** — identify IMRaD structure (Abstract, Intro, Methods, Results, Discussion, Conclusion)
9. **Table extraction** — pipe/tab/ASCII tables with JSON/CSV/Markdown export
10. **Figure detection** — Figure references, charts, diagrams, equations
11. **Equation extraction** — display math ($$...$$), inline math ($...$), LaTeX environments
12. **StructuredDocument assembly** — combine all above into unified output
13. **Quality assessment** — overall score, missing pages, warnings/errors
14. **Caching** — store result with TTL for future use

---

## Parser Framework

### Base Class: `BaseDocumentParser`

Abstract base for semantic-aware document parsing. Subclasses implement `_do_parse()` to extract raw text.

```python
from core.intel.parser_base import BaseDocumentParser

class EnhancedPDFParser(BaseDocumentParser):
    def _do_parse(self, file_path, **options):
        from core.pipeline.parsers import PDFParser
        return PDFParser().parse(file_path)

parser = EnhancedPDFParser("enhanced-pdf", "1.0")
structured_doc = parser.parse_with_intel("/path/to/doc.pdf")
```

### Auto-Detection: `parse_with_intel()`

Convenience function that auto-selects the best parser by file extension:

| Extension | Parser Used              |
|-----------|--------------------------|
| `.pdf`    | `intel.parser_pdf.PDFParser` |
| `.docx`   | `intel.parser_docx.DOCXParser` |
| `.txt`, `.md`, `.rst` | `intel.parser_text.TextParser` |
| Other     | Returns StructuredDocument with quality error |

---

## OCR Framework

### Abstract Provider: `OCREngineProvider`

Base class implementing `core.interfaces.OCREngine`. Subclasses provide:
- `initialize(config)` — set up Tesseract/EasyOCR/etc.
- `extract_text(file_path)` — perform OCR
- `health_check()` — verify engine operational
- `supported_formats()` — return supported extensions

### Registry: `OCRProviderRegistry`

Uses `ServiceContainer` for dependency injection:

```python
from core.intel.ocr_base import register_ocr_engine, get_default_ocr_engine

register_ocr_engine(MyCustomOCR())  # Register custom provider
engine = get_default_ocr_engine()    # Resolve (falls back to stub if none registered)
```

### Stub Providers

| Provider | Purpose |
|----------|---------|
| `StubOCREngineProvider` | No-op fallback when no real OCR installed |
| `NoOpOCREngineProvider` | Pass-through for digital documents where OCR is unnecessary |

---

## Structured Document Schema

### Canonical Output: `StructuredDocument`

Every processed document becomes this unified schema regardless of input format. Consumed by:
- Metadata Engine → Citation Analysis → Knowledge Graph → Embeddings → AI Agents

```python
@dataclass
class StructuredDocument:
    id: str                          # UUID
    source_path: Optional[Path]
    original_filename: str
    
    # Metadata
    title: str
    authors: List[str]
    abstract_text: str
    publication_date: Optional[str]
    journal: str
    doi: Optional[str]
    category: DocumentCategory       # enum: research_paper, book, report, ...
    pdf_type: Optional[PDFType]      # digital, scanned, hybrid, image_only
    total_pages: int
    
    # Content structure
    sections: List[Section]          # hierarchical: subsections nested under parents
    pages: List[Page]                # one Page per source page
    references: List[ReferenceBlock] # bibliographic entries
    
    # Cross-document links
    cited_by: List[str]
    cites: List[str]
    
    # Language
    primary_language: str            # ISO 639-1
    secondary_languages: List[str]
    writing_direction: LanguageDirection  # LTR, RTL, TTB
    
    # Quality
    quality: QualityReport           # overall_score, errors, warnings
    
    # Raw artifacts (debugging/re-processing)
    raw_text: str
    parser_used: str
```

### Section Types

`SectionType` enum covers canonical academic/professional sections:
- `ABSTRACT`, `INTRODUCTION`, `BACKGROUND`, `LITERATURE_REVIEW`
- `METHODOLOGY`, `METHODS`, `DATA`
- `RESULTS`, `FINDINGS`, `DISCUSSION`
- `CONCLUSION`, `ACKNOWLEDGMENTS`, `REFERENCES`
- `APPENDIX`, `SUPPLEMENTARY_MATERIAL`
- `FIGURE_CAPTION`, `TABLE_CAPTION`, `FOOTNOTE`
- `HEADER`, `FOOTER`, `GENERAL`

Sections are hierarchically nested via `subsection: List[Section]`.

---

## Layout Analysis

### `LayoutAnalyzer`

Detects structural elements from raw text:

| Element | Detection Method |
|---------|-----------------|
| Headings | Markdown (#), numbered (3. Intro), title-case |
| Paragraphs | Double-newline splits |
| Lists | Bullet (-, *, +), numbered (1., 2.), Roman (i., ii.) |
| Tables | Pipe \|, tab-separated, ASCII borders (+---+) |
| Footnotes | [^1], superscript numbers, "Footnote" headers |
| Headers/Footers | Repeated first/last N lines |
| Page Numbers | Standalone digits, "Page X" patterns |
| Multi-column | High mid-sentence break ratio |

Output: `Dict[str, Any]` with keys `headings`, `paragraphs`, `lists`, `tables`, etc.

---

## Automatic Classification

### `DocumentClassifier`

Combines extension hints + content analysis:

**Extension Mapping** (31 extensions mapped to categories):
| Extensions | Category |
|------------|----------|
| .py, .r, .do, .jl, .m, .stan | CODE |
| .csv, .tsv, .xlsx, .xls | SPREADSHEET |
| .srt, .vtt | TRANSCRIPT |
| .tex, .bib | TECHNICAL_DOCUMENT |
| .pdf | RESEARCH_PAPER (default) |

**Content Analysis** (section heading density scoring):
- Abstract + Intro + Methods + Results + Discussion + Conclusion → RESEARCH_PAPER
- Presentation markers → PRESENTATION
- Spreadsheet markers → SPREADSHEET
- Code markers → CODE

**PDF Type Detection** (chars-per-page thresholds):
| Ratio (chars/page) | PDF Type |
|--------------------|----------|
| < 1 | SCANNED |
| 1–10 | TEXT_ONLY |
| 10–500 | HYBRID |
| > 500 | DIGITAL |

---

## Language Detection

### `LanguageDetector`

Three complementary signals:

1. **Unicode range analysis** — detects CJK, Korean Hangul, Arabic, Cyrillic, Thai, Devanagari
2. **Common word frequency** — detects English, French, German, Spanish, Portuguese, Italian
3. **Writing direction** — LTR (default), RTL (Arabic/Hebrew), TTB (traditional vertical CJK)

Features:
- Sampling for large documents (>10KB sampled at 3 points)
- Mixed-language detection (secondary ≥15% of primary score)
- Minimum 20 characters required
- All candidates returned sorted by confidence
- Encoding detection with BOM awareness

---

## Text Normalization

### `TextNormalizer`

Full normalization pipeline applied in order:

1. Remove invisible characters (BOM, ZWS, ZWJ, soft hyphens)
2. Unicode normalization (NFC by default)
3. Encoding artifact fixes (curly quotes, dashes, ellipsis → ASCII equivalents)
4. Hyphenation fix (`con-\ncept` → `concept`)
5. Broken line joining (sentences split across lines)
6. Whitespace unification (tabs→spaces, multi-space collapse)
7. Blank line deduplication

Additional methods: `clean_for_embedding()`, `estimate_quality()`

---

## Section Extraction

### `SectionExtractor`

Identifies logical document sections via regex pattern matching against section headings.

Builds hierarchical structure using a stack-based nesting algorithm. Supports IMRaD format detection.

---

## Table Extraction

### `TableExtractor`

Supports three table formats:

1. **Pipe-delimited** (`| col | col |`)
2. **Tab-separated** (consistent column alignment)
3. **ASCII-bordered** (`+---+---+`)

Export methods on `TableBlock`:
- `.export_json()` — dict keyed by headers, or 2D array fallback
- `.export_csv()` — RFC 4180 compliant CSV
- `.export_markdown()` — standard pipe-table format

---

## Figure & Equation Detection

### `FigureDetector`

Detects:
- Figure references ("Figure 3:", "Fig. 3:")
- Caption text following references
- Image markers ([image], <img>)
- Cross-references ("see Fig. 2")

Returns `FigureBlock` with kind: "figure", "chart", "graph", "diagram", "equation", "image"

### `EquationExtractor`

Extracts:
- Display math: `$$...$$`, `\[...\]`, `\begin{equation}...\end{equation}`, `\begin{align}...\end{align}`
- Inline math: `$...$`
- Context (text before/after each equation)
- Reference IDs: "Eq. (3)", "Equation (2.1)"

Includes `is_likely_math()` false-positive filtering and `estimate_latex_quality()` scoring.

---

## Caching

TTL-based caching in `DocumentIntelligenceManager`:

| Setting | Default |
|---------|---------|
| Max cache age | 1 hour (3600 seconds) |
| Cache key | SHA-256 content hash of file |
| Cache scope | Per-instance dict |
| Invalidation | Manual `clear_cache()` or TTL expiry check |

---

## Testing

Test suite: `tests/test_document_intelligence.py`

| Category | Tests | Coverage |
|----------|-------|----------|
| Classification | 9 | Extension mapping, content scoring, PDF type detection |
| Language Detection | 9 | English, Korean, Chinese, Japanese, mixed, encoding |
| Text Normalization | 8 | Broken lines, hyphenation, Unicode, whitespace, quality |
| Layout Analysis | 3 | Paragraphs, page numbers, full pipeline |
| Section Extraction | 3 | IMRaD sections, required fields, empty text |
| Table Extraction | 4 | Pipe tables, JSON/CSV export, no-table case |
| Figure Detection | 2 | References, cross-reference counting |
| Equation Extraction | 4 | Math detection, quality scoring, inline detection |
| OCR Provider | 2 | Stub initialization, registry resolution |
| Parser Base | 2 | Hash computation, unsupported format handling |
| Intelligence Manager | 3 | Creation, singleton, status |
| Backward Compatibility | 3 | Pipeline unchanged, parsers unchanged, models importable |

**Total: 52 tests, 45 passing**

---

## Extension Guide

### Adding a New Parser

1. Create module `intel/parser_<type>.py` subclassing `BaseDocumentParser`
2. Implement `_do_parse(self, file_path, **options)` returning `(text, metadata_dict)`
3. Register in `parse_with_intel()` parser map or let lazy imports discover it

### Adding an OCR Engine

1. Create class extending `OCREngineProvider`
2. Implement `_do_initialize()`, `_do_health_check()`, `_do_shutdown()`
3. Call `register_ocr_engine(YourEngine())` at startup

### Adding a Layout Element Detector

1. Add method to `LayoutAnalyzer`
2. Call from `analyze()` pipeline method
3. Include result key in return dict

---

## Known Limitations

1. **OCR providers not implemented** — only stub/NoOp providers available. Real Tesseract/EasyOCR/PaddleOCR integrations pending.
2. **Image-based table extraction limited** — can parse text-represented tables but cannot detect tables from images without OCR.
3. **Equation extraction is heuristic** — relies on $ delimiters and LaTeX environment markers. Does not parse actual mathematical notation.
4. **Chinese language detection inconsistent** — Unicode range detection works but confidence varies based on sample size.
5. **Large document processing** — no streaming/chunked mode for multi-MB files. Entire file loaded into memory.
6. **Single-language assumption** — while mixed-language detection is supported, downstream components assume monolingual processing.

---

## Future Improvements

1. **Real OCR integration** — Tesseract, EasyOCR, PaddleOCR, Azure Document Intelligence
2. **PDF-specific layout analysis** — Leverage PyMuPDF page geometry for spatial layout reconstruction
3. **ML-based section classification** — Train classifier on section headings rather than regex
4. **Streaming chunked processing** — Handle GB-scale documents with memory-bounded processing
5. **Multilingual support** — Full pipeline supporting documents with multiple embedded languages
6. **Semantic similarity search** — Compare extracted sections against vault documents
7. **Citation graph generation** — Parse references → link to known papers in knowledge graph
8. **Visual equation rendering** — Store rendered equation images alongside LaTeX representations
