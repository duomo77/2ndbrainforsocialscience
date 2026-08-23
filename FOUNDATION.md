# FOUNDATION.md — ROS Foundation Architecture

**Date**: 2026-07-31
**Version**: 1.0.0
**Status**: Foundation Layer Established

---

## Overview

This document describes the new foundation architecture established for the Research Operating System (ROS). The foundation was created as a purely additive layer — **no existing code was modified, no APIs were changed, no functionality was removed**. All existing modules in `core/`, `ui/`, and `frontend/` continue to work exactly as before.

---

## New Directory Structure

```
2ndbrainforsocialscience-main-2/
│
├── brain/           ← Research agent coordination & reasoning engines
├── processed/       ← Intermediate pipeline artifacts & provenance
├── datasets/        ← Dataset registry, schemas, variable dictionaries
├── projects/        ← Research project organization and metadata
├── experiments/     ← Experiment tracking (hypothesis → result)
├── agents/          ← Pluggable research agent implementations
├── graphs/          ← Knowledge/citation/concept graph storage
├── vectors/         ← Vector database & similarity search
├── embeddings/      ← Embedding models, pipelines, chunkers
├── literature/      ← Literature discovery, review, citation analysis
├── writing/         ← AI-assisted academic writing tools
├── dashboard/       ← Research dashboard & visualization
├── plugins/         ← Plugin system (protocol, registry, SDK)
├── logs/            ← Centralized logging per component category
├── config/          ← Centralized configuration management
├── cache/           ← Computation cache (LLM, embeddings, OCR, etc.)
│
├── core/            ← EXISTING — untouched, all APIs preserved
│   ├── utils/       ← NEW — shared utility functions
│   ├── exceptions.py← NEW — structured exception hierarchy
│   ├── constants.py ← NEW — centralized constants & magic values
│   └── interfaces.py← NEW — abstract base classes for all swappable components
│
├── ui/              ← EXISTING — untouched (PyQt6 production UI)
├── frontend/        ← EXISTING — untouched (Tkinter legacy UI)
└── tests/           ← EXISTING — untouched
```

Each new directory contains a `README.md` describing its purpose, responsibilities, expected contents, and future expansion plans.

---

## Configuration System

### Location: `config/app_config.py`

**What it does**: Provides a unified, layered configuration system with clear priority:

```
1. Runtime overrides (programmatic set())
2. Environment variables (ROS_* prefix)
3. config.json (user-saved configuration)
4. DEFAULT_CONFIG (hardcoded fallbacks)
```

**Key Features**:
- Environment variable support via `ROS_` prefix (e.g., `ROS_API_KEY`, `ROS_MODEL`)
- Type-safe getters for common config values (`api_key`, `base_url`, `model`, etc.)
- Validation methods (`ConfigSchema.validate_api_key()`, `validate_model_name()`, `validate_vault_path()`)
- Boolean/int helper methods (`get_bool_env()`, `get_int_env()`)

**Backward Compatibility**: `config/app_config.py` re-exports all symbols from `core/config.py`. The existing `Config` class, `load_config()`, `save_config()`, and `DEFAULT_CONFIG` continue to work identically.

**Usage**:
```python
from config.app_config import AppConfig, get_app_config

config = get_app_config()
api_key = config.api_key           # Resolves from env, file, or default
debug = config.debug_mode          # ROS_DEBUG=true
model = config.get("model", "gpt-4o")  # With explicit default
```

---

## Logging Architecture

### Location: `logs/log_manager.py`

**What it does**: Centralizes all logging with per-category configuration, rotation, and structured event logging.

**Log Categories**:

| Category | Logger Name | Log File | Purpose |
|----------|-------------|----------|---------|
| APP | `ros.app` | `ros.log` | General application events |
| OCR | `ros.ocr` | `ros_ocr.log` | PDF/image processing |
| EMBEDDING | `ros.embedding` | `ros_embedding.log` | Embedding generation |
| PARSER | `ros.parser` | `ros_parser.log` | Document parsing |
| LLM | `ros.llm` | `ros_llm.log` | LLM API calls |
| SEARCH | `ros.search` | `ros_search.log` | Search queries |
| AGENT | `ros.agent` | `ros_agent.log` | Research agent execution |
| ERROR | `ros.error` | `ros_error.log` | All errors aggregated |
| AUDIT | `ros.audit` | `ros_audit.log` | Security/access audit |
| PERF | `ros.perf` | `ros_perf.log` | Performance profiling |

**Features**:
- Rotating file handlers (5MB × 3 backups per category)
- Console output when `ROS_DEBUG=1` is set
- Structured event logging via `log_event(category, event_type, message)`
- Automatic error aggregation to the ERROR category

**Backward Compatibility**: `logs/log_manager.py` re-exports `get_logger()`, `timed()`, and `StructuredLogger` from `core/ros_logger.py`. All existing logging code continues to work.

**Usage**:
```python
from logs.log_manager import LogManager, LogCategory, get_log_manager

lm = get_log_manager()
logger = lm.get(LogCategory.LLM)
logger.info("LLM call started", extra={"model": "qwen-max"})

lm.log_error(LogCategory.PARSER, exception, context="PDF extraction")
```

---

## Shared Utilities

### Location: `core/utils/`

Seven utility modules providing reusable, pure functions extracted from patterns observed across the codebase:

| Module | Functions | Key Exports |
|--------|-----------|-------------|
| `file_utils.py` | Atomic writes, backups, safe reads | `atomic_write()`, `backup_file()`, `safe_read_text()` |
| `hash_utils.py` | Content hashing, stable IDs | `content_hash()`, `file_hash()`, `stable_id()` |
| `text_utils.py` | Truncation, cleaning, token estimation | `truncate_middle()`, `clean_whitespace()`, `estimated_tokens()` |
| `json_utils.py` | Safe JSON I/O, schema validation | `safe_load_json()`, `merge_configs()`, `jsonl_append()` |
| `markdown_utils.py` | Frontmatter, wikilinks, headings | `extract_frontmatter()`, `parse_wikilinks()`, `inject_frontmatter()` |
| `path_utils.py` | Path safety, vault resolution | `sanitize_filename()`, `resolve_vault_path()`, `ensure_unique_path()` |
| `validation_utils.py` | Type checking, range validation | `is_non_empty_string()`, `validate_range()`, `safe_int()` |

All utility functions are pure (no side effects beyond file I/O where documented) and have no dependencies on other ROS modules. They can be imported from anywhere without circular import risk.

**Usage**:
```python
from core.utils.file_utils import atomic_write, backup_file
from core.utils.text_utils import truncate_middle, word_count
from core.utils.markdown_utils import extract_frontmatter, parse_wikilinks
```

---

## Exception Hierarchy

### Location: `core/exceptions.py`

A structured exception hierarchy with machine-readable error codes, human-readable messages, and serialization support:

```
ROSException (base, code: ROS_000)
├── ConfigurationError (CFG_001)
│   ├── MissingAPIKeyError (CFG_002)
│   ├── InvalidModelError (CFG_003)
│   └── InvalidVaultPathError (CFG_004)
├── ProviderError (PRV_001)
│   ├── APIKeyInvalidError (PRV_002)
│   ├── APIRateLimitError (PRV_003) [recoverable]
│   ├── APITimeoutError (PRV_004) [recoverable]
│   └── APIResponseError (PRV_005)
├── ParsingError (PAR_001)
│   ├── UnsupportedFileTypeError (PAR_002)
│   ├── PDFExtractionError (PAR_003)
│   └── EmptyContentError (PAR_004)
├── ValidationError (VAL_001)
│   └── ThreatDetectedError (VAL_002)
├── GraphError (GRP_001)
│   └── GraphIntegrityError (GRP_002)
├── StorageError (STO_001)
├── RAGError (RAG_001)
│   └── RetrievalError (RAG_002)
├── EmbeddingError (EMB_001)
└── SecurityError (SEC_001)
    └── PromptInjectionError (SEC_002)
```

Each exception carries:
- `message`: Human-readable description
- `code`: Machine-readable error code (e.g., `CFG_002`)
- `details`: Dictionary with contextual data (file path, provider name, etc.)
- `recoverable`: Boolean indicating automatic recovery is possible
- `to_dict()`: Serialization for logging/API responses

**Usage**:
```python
from core.exceptions import MissingAPIKeyError, APIRateLimitError

if not api_key:
    raise MissingAPIKeyError(provider="qwen")

try:
    response = provider.call(prompt)
except RateLimitExceeded as e:
    raise APIRateLimitError(provider="qwen", retry_after=e.retry_after)
```

---

## Constants

### Location: `core/constants.py`

All magic values, default settings, and named constants centralized in one location:

| Category | Examples |
|----------|----------|
| File types | `SUPPORTED_PDF_EXTENSIONS`, `SUPPORTED_DATASET_EXTENSIONS` |
| Size limits | `MAX_CONTENT_CHARS_PAPER` (65000), `MAX_RAG_FILE_BYTES` (512KB) |
| Graph limits | `MAX_NODES_PER_VAULT` (50000), `MAX_GRAPH_DEPTH` (20) |
| Cache settings | `DEFAULT_CACHE_TTL_SECONDS` (300), `DEFAULT_CACHE_SIZE_MB` (50) |
| RAG settings | `RAG_LAYERS`, `RAG_DEFAULT_TOP_K` (10) |
| Embedding | `DEFAULT_EMBEDDING_DIMENSION` (384), `DEFAULT_CHUNK_SIZE` (512) |
| OCR | `OCR_DPI` (300), `MAX_PDF_PAGES` (500) |
| LLM | `DEFAULT_TEMPERATURE` (0.7), `MAX_RETRY_ATTEMPTS` (3) |
| Model presets | `MODEL_PRESETS` (12 providers × model lists) |
| Trust & memory | `DECAY_HALF_LIFE_DAYS` (90), `MIN_TRUST_SCORE` (0.05) |

Using `Final` type annotations so IDEs and type checkers can enforce immutability.

**Usage**:
```python
from core.constants import MAX_CONTENT_CHARS_PAPER, DEFAULT_EMBEDDING_DIMENSION

if len(content) > MAX_CONTENT_CHARS_PAPER:
    content = truncate_middle(content, MAX_CONTENT_CHARS_PAPER)
```

---

## Interfaces & Abstract Base Classes

### Location: `core/interfaces.py`

Clean interfaces for all swappable components in the system. These define *contracts*, not implementations:

| Interface | Methods | Status |
|-----------|---------|--------|
| `BaseProvider` | `initialize()`, `health_check()`, `shutdown()` | Root for all providers |
| `OCREngine` | `extract_text()`, `extract_metadata()`, `supported_formats()` | For PDF/image text extraction |
| `DocumentParser` | `parse()`, `detect_type()`, `supported_formats()` | For multi-format document parsing |
| `EmbeddingProvider` | `embed()`, `embed_query()`, `dimension`, `supported_models()` | For text → vector conversion |
| `SearchProvider` | `search()`, `index()`, `delete()`, `index_size` | For semantic/keyword search |
| `StorageProvider` | `get()`, `put()`, `delete()`, `exists()`, `list_keys()` | For persistent storage backends |
| `GraphProvider` | `add_node()`, `add_edge()`, `get_node()`, `query()` | For knowledge graph operations |
| `ResearchAgent` | `execute()`, `can_handle()`, `supported_task_types()` | For autonomous research tasks |

Each interface includes:
- Input/output dataclasses (e.g., `OCRResult`, `ParseResult`, `SearchResponse`)
- Type-annotated method signatures
- Comprehensive docstrings

These are **purely additive** — no existing implementations are modified. Future modules should implement these interfaces; existing modules can be gradually adapted.

---

## Dependency Injection Preparation

### Location: `core/interfaces.py` → `ServiceContainer`

A lightweight service container that supports:

- **Service registration**: `container.register(OCREngine, implementation)`
- **Lazy factory registration**: `container.register_factory(EmbeddingProvider, lambda: create_embedder())`
- **Graceful degradation**: `resolve()` returns `None` if service not registered — caller handles fallback
- **Coexistence**: Does NOT replace existing singletons or `engine_loader.py` — it sits alongside them

**Usage pattern**:
```python
from core.interfaces import ServiceContainer, OCREngine, get_service_container

container = get_service_container()

# Register at app startup
container.register(OCREngine, PyMuPDFOCREngine())

# Resolve at call site (with fallback)
engine = container.resolve(OCREngine)
if engine is None:
    engine = get_builtin_ocr_engine()  # existing fallback

result = engine.extract_text(file_path)
```

---

## Extension Points

The foundation architecture enables future development of all components identified in the architectural audit:

| Future Component | Foundation Already In Place |
|------------------|-----------------------------|
| Vector database | `vectors/` directory + `SearchProvider` interface + `constants.py` embedding settings |
| Plugin system | `plugins/` directory + `interfaces.py` provider protocols + `ServiceContainer` |
| Research dashboard | `dashboard/` directory + `logs/` structured logging for metrics |
| Literature search | `literature/` directory + `ResearchAgent` interface |
| Writing assistant | `writing/` directory + `interfaces.py` composable agent patterns |
| Citation graph | `graphs/` directory + `GraphProvider` interface |
| Dataset registry | `datasets/` directory + `StorageProvider` interface |
| Experiment tracking | `experiments/` directory + structured exception hierarchy for error reporting |

---

## Validation

The foundation architecture was validated by:

1. **No existing imports broken**: All new modules are additive — nothing in `core/` was modified
2. **Existing `core/config.py` preserved**: `config/app_config.py` wraps it, re-exports its API
3. **Existing `core/ros_logger.py` preserved**: `logs/log_manager.py` extends it, re-exports its API
4. **All existing test files untouched**: `pytest.ini` test paths unchanged
5. **No file deletions or renames**: All original files remain in their original locations

---

## Next Steps

Based on the `REFACTOR_PLAN.md` phased roadmap:

1. **Phase 0 (Cleanup)**: Use `core/utils/` to replace duplicated helper functions across modules
2. **Phase 1 (Stabilize)**: Begin adopting `core/constants.py` to eliminate magic values; replace bare `except` with `core/exceptions.py` types
3. **Phase 2 (Extract)**: Externalize inline data using `core/utils/json_utils.py` safe loaders
4. **Phase 3 (Foundation)**: Implement `EmbeddingProvider` and `SearchProvider` interfaces with real backends; populate `vectors/` and `embeddings/`
5. **Phase 4 (Intelligence)**: Implement `ResearchAgent` for literature search; build `literature/` and `graphs/citation/`
6. **Phase 5 (Platform)**: Convert engines to plugins using `interfaces.py` protocols + `plugins/` registry