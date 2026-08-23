# DOCUMENT_PIPELINE.md — Document Processing Pipeline

**Date**: 2026-07-31
**Version**: 1.0.0

---

## Overview

The Document Processing Pipeline is a modular, extensible system for ingesting, validating, identifying, parsing, cleaning, and storing documents in multiple formats. It is designed to serve as the ingestion foundation for all downstream ROS features: OCR, metadata extraction, knowledge graph generation, embedding, AI agents, and search.

---

## Architecture

```
                          ┌──────────────────┐
                          │   USER / SYSTEM   │
                          └────────┬─────────┘
                                   │ file_path
                                   ▼
                          ┌──────────────────┐
                          │  DOCUMENT MANAGER │  ← Register, track, query
                          └────────┬─────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        PROCESSING PIPELINE                            │
│                                                                       │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐      │
│  │VALIDATION│──▶│IDENTIFICATION│──▶│ PARSING  │──▶│   OCR    │      │
│  │          │   │              │   │          │   │(optional)│      │
│  └──────────┘   └──────────────┘   └──────────┘   └─────┬────┘      │
│       │                                                  │           │
│       ▼                                                  ▼           │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────────┐     │
│  │ CLEANING │──▶│NORMALIZATION │──▶│        STORAGE           │     │
│  │          │   │              │   │  raw/processed/metadata/  │     │
│  └──────────┘   └──────────────┘   │  cache/temporary/         │     │
│                                    └──────────────────────────┘     │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                   ERROR RECOVERY (all stages)                │    │
│  │  • Retry with exponential backoff                           │    │
│  │  • Graceful degradation (skip vs. fail)                     │    │
│  │  • Error logging and categorization                         │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  DOWNSTREAM APPS  │
                          │  • Knowledge Graph│
                          │  • Embedding      │
                          │  • AI Agents      │
                          │  • Search         │
                          └──────────────────┘
```

---

## Pipeline Stages

### 1. Validation (`core/pipeline/validator.py`)

Checks:
- File exists and is readable
- Extension is in the supported list (20+ extensions)
- File size is within limits (configurable per type)
- File is not empty
- MIME type is detected
- Content hash is computed (SHA-256)
- Duplicate detection via content hash

**Implementation**: `DocumentValidatorImpl`

### 2. Identification (`core/pipeline/identifier.py`)

Detects:
- Document type (PDF, DOCX, TXT, HTML, EPUB, PPTX, CSV, Excel, Images)
- MIME type
- Language (en, ko, zh, ja, fr, de, es) via pattern matching
- Encoding (UTF-8, UTF-16, Latin-1, etc.) via BOM detection
- Estimated page count
- Whether OCR is required

**Implementation**: `DocumentIdentifierImpl`

### 3. Parsing (`core/pipeline/parsers.py`)

Extracts text using format-specific parsers:
- **PDF** → delegates to existing `core.parsers.parse_pdf()` (PyMuPDF)
- **TXT/Markdown** → direct file read with encoding detection
- **HTML** → built-in HTMLParser with script/style tag skipping
- **DOCX** → `python-docx` (optional dependency)
- **PPTX** → `python-pptx` (optional dependency)
- **EPUB** → `ebooklib` (optional dependency)
- **CSV/Excel** → delegates to existing `core.parsers.parse_dataset()` (pandas)

Parser selection via `ParserRegistry` — new parsers registered with `registry.register(DocumentType, parser)`.

### 4. OCR (Optional)

Placeholder for future OCR implementation. Currently passes through parser output.

### 5. Cleaning (`core/pipeline/cleaner.py`)

Operations:
- Remove null bytes and control characters
- Fix encoding artifacts (curly quotes, dashes, ligatures)
- Normalize line endings
- Unify quotation marks
- Remove excessive blank lines
- Type-specific cleaning (OCR, HTML, CSV)

**Implementation**: `DocumentCleanerImpl`

### 6. Normalization

Unicode NFC normalization for consistent downstream processing.

### 7. Storage (`core/pipeline/file_storage.py`)

Organizes files in a structured directory:
```
documents/
├── raw/            Original uploaded files
├── processed/      Extracted text files (.txt)
├── metadata/       JSON metadata files (.json)
├── cache/          Intermediate computation cache
└── temporary/      Temporary processing files
```

---

## Extension Points

### Adding a New Document Type

1. **Add to models.py**: Register extension and MIME type mappings
```python
# In EXTENSION_TO_DOC_TYPE
".newfmt": DocumentType.NEW_FMT,

# In MIME_TO_DOC_TYPE
"application/new-format": DocumentType.NEW_FMT,
```

2. **Create a parser**: Implement `DocumentParser` interface
```python
class NewFormatParser(DocumentParser):
    def parse(self, file_path: Path, **options) -> ParseResult: ...
    def supported_types(self) -> List[str]: return ["new_fmt"]
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]: ...
```

3. **Register the parser**:
```python
registry.register(DocumentType.NEW_FMT, NewFormatParser())
```

### Adding a New Pipeline Stage

1. Create a class implementing `PipelineStage` or a standalone function
2. Add the stage call in `DocumentPipeline.process()`
3. Configure retry behavior in `ErrorRecoveryManager.MAX_RETRIES`

---

## Error Handling

### Error Recovery (`core/pipeline/error_recovery.py`)

- **Retry with exponential backoff**: Base 1s, max 30s, configurable per stage
- **Max retries per stage**: Validation (3), Parser (2), OCR (2), others (2-3)
- **Graceful degradation**: Non-critical stages can be skipped on failure
- **Fatal stages**: Validation and Identification failures abort the pipeline
- **Comprehensive logging**: Every failure logged with document ID, stage, attempt number

### Failure Modes

| Stage | Fatal? | Retries | On Exhaustion |
|-------|--------|---------|---------------|
| Validation | YES | 3 | Mark document FAILED |
| Identification | YES | 3 | Mark document FAILED |
| Parsing | YES | 2 | Mark document FAILED |
| OCR | No | 2 | Skip stage, continue |
| Cleaning | No | 2 | Skip stage, continue |
| Normalizing | No | 2 | Skip stage, continue |
| Storage | YES | 3 | Mark document FAILED |

---

## Document Manager (`core/pipeline/doc_manager.py`)

Central service for document lifecycle:

- **register(file_path)** — Create a Document, copy raw file to storage
- **get(doc_id)** — Retrieve by ID
- **retry(doc_id)** — Reset failed document for reprocessing
- **cancel(doc_id)** — Cancel processing
- **query(status, type, since)** — Filter documents
- **get_history(doc_id)** — Retrieve processing history
- **get_stats()** — Aggregate statistics

---

## Logging

All pipeline stages log via `LogCategory.PARSER`:
- **pipeline_started/pipeline_completed**: Document-level events
- **stage_completed**: Per-stage with duration
- **stage_skipped**: When non-fatal stage is skipped
- **pipeline_failed**: Fatal failures
- **document_registered/document_retry**: Lifecycle events

---

## Backward Compatibility

- **Existing parsers unchanged**: `core/parsers.py`, `core/pdf_parser.py` continue to work
- **PDF/CSV/Excel parsing**: Pipeline delegates to existing parsers — no behavior change
- **API preservation**: All existing `analyze_paper()`, `analyze_dataset()`, etc. remain functional
- **Coexistence**: Pipeline runs alongside existing code without interference

---

## Future Improvements

1. **OCR Integration**: Implement actual OCR with Tesseract/Cloud Vision API
2. **Streaming Pipeline**: Process large documents in chunks
3. **Parallel Processing**: Process multiple documents simultaneously using `orchestration.py`
4. **Metadata Extraction**: Structured extraction of authors, DOIs, citations using LLM
5. **Format-specific chunking**: Smart document chunking for embedding (by section, by slide)
6. **Incremental Processing**: Only re-process changed documents
7. **Queue Integration**: Async processing via Celery/RQ for API server use