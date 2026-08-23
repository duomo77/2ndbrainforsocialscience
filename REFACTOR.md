# REFACTOR.md — ROS (Research Operating System) Architectural Audit

**Date**: 2026-07-31
**Auditor**: Google Staff Engineer, AI Systems & Developer Tooling
**Scope**: Full repository analysis — no code modifications, documentation only

---

## SECTION 1: Repository Overview

### Project Purpose
ROS (Research Operating System, formerly "Econometric Wiki Compiler") is a desktop application that analyzes academic papers, lecture transcripts, datasets, equations, and research notes. It uses large language models (LLMs) to produce structured Markdown notes compatible with Obsidian vaults. The system targets social science researchers and supports 45+ academic disciplines.

### Architecture Style
**Modular Monolith** — ~20 singleton engine instances coordinated through an `engine_loader.py` service locator. The architecture decomposes into layers:

| Layer | Modules | Lines |
|-------|---------|-------|
| Provider Adapters | `base_provider.py`, `qwen_provider.py`, `chinese_providers.py`, `llm_client.py` | ~563 |
| Factories/Managers | `provider_factory.py`, `provider_manager.py` | ~213 |
| Prompt Templates | `ros_engine.py`, `llm_analyzer.py` | ~1,191 |
| Cognitive Engines (5) | `note_evolution.py`, `contradiction_engine.py`, `idea_lineage.py`, `math_ontology.py`, `research_tension.py` | ~1,831 |
| Infrastructure Engines (7) | `security.py`, `graph_integrity.py`, `memory_trust.py`, `perf_engine.py`, `orchestration.py`, `fault_recovery.py`, `embedding_gov.py` | ~2,702 |
| RAG Subsystem | `rag_engine.py`, `rag_observability.py`, `embedding_gov.py` | ~1,859 |
| Data Pipeline | `parsers.py`, `pdf_parser.py`, `classifier.py`, `qualitative_engine.py` | ~1,534 |
| Persistence | `config.py`, `obsidian_sync.py`, `obsidian_sync_old.py`, `memory.py`, `knowledge_graph.py` | ~1,147 |
| Cross-cutting | `contracts.py`, `state_manager.py`, `observability.py`, `ros_logger.py`, `engine_loader.py`, `graph_utils.py` | ~821 |
| UI (PyQt6) | `ui/` package (10 files) | ~5,524 |
| UI (Tkinter) | `frontend/` package (3 files) | ~783 |

### Languages & Frameworks
- **Primary**: Python 3.9+
- **GUI (Production)**: PyQt6 ≥6.6.0
- **GUI (Legacy)**: Tkinter (stdlib)
- **Node.js**: Present via `package.json` but no runtime JS — Electron dependency unused

### External Libraries
| Library | Purpose | Version |
|---------|---------|---------|
| `PyQt6` | Desktop UI | ≥6.6.0 |
| `PyMuPDF` (fitz) | PDF text extraction | ≥1.23.0 |
| `openai` | LLM API client (OpenAI SDK) | ≥1.0.0 |
| `PyYAML` | YAML parsing (frontmatter) | ≥6.0 |
| `pandas` | CSV/Excel data parsing | ≥2.0.0 |
| `openpyxl` | Excel file reading | ≥3.1.0 |
| `numpy` | Numerical operations | ≥1.24.0 |
| `requests` | HTTP (provider implementations) | (transitive via openai) |
| `psutil` | System resource monitoring (optional) | (not pinned) |

### LLM Providers (12 supported)
OpenAI, Azure OpenAI, Anthropic-compatible, Groq, DeepSeek, Qwen/DashScope, Zhipu GLM, Moonshot Kimi, MiniMax, Baidu ERNIE, SiliconFlow, 01.AI

### Database Technologies
**File-based JSON** — All persistence uses JSON files on disk. No SQL, no vector database, no embedded database. Specific stores:
- `~/.ros_config/providers.json` — provider configurations
- `~/.ros_memory/` — research memory, concepts, questions, graph
- `~/.econometric_wiki/config.json` — app configuration (legacy naming)
- `~/.econometric_wiki/logs/` — structured JSONL logs

### Vector Databases
**None** — No embedding computation, no vector storage, no approximate nearest neighbor search. The `embedding_gov.py` module governs a hypothetical embedding pipeline that does not yet exist. The RAG engine (`rag_engine.py`) uses keyword-overlap-based retrieval from the Obsidian vault file system.

### Build Tools
- PyInstaller (via `build_exe.sh` / `build_exe.bat`) — references `ROS.spec` which **does not exist** in the repository
- Electron + electron-builder (in `package.json`) — unused, aspirational

---

## SECTION 2: Directory Analysis

### Complete Directory Tree

```
2ndbrainforsocialscience-main-2/
│
├── .github/workflows/ci.yml         (32 lines) — CI pipeline (Pipenv + pytest + flake8)
│
├── core/                             (40 files, ~13,000 lines) — ALL backend logic
│   ├── __init__.py                   (1 line)
│   ├── Pipfile                       (14 lines) — dev tools only (pytest, flake8, black)
│   ├── base_provider.py              (117 lines) — Abstract base class for LLM providers
│   ├── chinese_providers.py          (170 lines) — DeepSeek & Baidu ERNIE implementations
│   ├── classifier.py                 (470 lines) — 45-discipline paper classifier
│   ├── config.py                     (153 lines) — Atomic-write config persistence
│   ├── contracts.py                  (263 lines) — Rust-style Result types, Protocols, DTOs
│   ├── contradiction_engine.py       (361 lines) — Rule-based contradiction detection
│   ├── embedding_gov.py              (574 lines) — Embedding cost governance (hypothetical)
│   ├── engine_loader.py              (197 lines) — Lazy engine loading with fail-safe
│   ├── fault_recovery.py             (377 lines) — Circuit breaker, backoff, safe mode
│   ├── graph_integrity.py            (469 lines) — Transactional graph mutations
│   ├── graph_utils.py                (35 lines) — WikiLink/frontmatter extractors (demo)
│   ├── idea_lineage.py               (362 lines) — Git-style intellectual genealogy
│   ├── knowledge_graph.py            (399 lines) — Typed semantic knowledge graph
│   ├── llm_analyzer.py               (366 lines) — Original paper analysis (DUPLICATE of ros_engine)
│   ├── llm_client.py                 (88 lines) — Unified LLM client with retry
│   ├── math_ontology.py              (464 lines) — Math object extraction (econ-focused)
│   ├── memory.py                     (199 lines) — Research profile persistence
│   ├── memory_trust.py               (380 lines) — Trust decay, hallucination prevention
│   ├── note_evolution.py             (413 lines) — 6-stage Zettelkasten maturity
│   ├── observability.py              (396 lines) — Structured logging, telemetry
│   ├── obsidian_sync.py              (322 lines) — Atomic vault writes, MOC index
│   ├── obsidian_sync_old.py          (318 lines) — DEPRECATED duplicate
│   ├── orchestration.py              (422 lines) — Task queue, resource governance
│   ├── parsers.py                    (302 lines) — Multi-format input parsing
│   ├── pdf_parser.py                 (62 lines) — Simplified PDF extraction (REDUNDANT)
│   ├── perf_engine.py                (437 lines) — 6-layer cache, token economy
│   ├── provider_factory.py           (88 lines) — Provider factory (incomplete)
│   ├── provider_manager.py           (125 lines) — Provider CRUD + persistence
│   ├── qualitative_engine.py         (527 lines) — 7-mode multi-epistemic analysis
│   ├── qwen_provider.py              (78 lines) — Qwen/DashScope implementation
│   ├── rag_engine.py                 (837 lines) — 4-layer RAG pipeline (LARGEST FILE)
│   ├── rag_observability.py          (604 lines) — Context compressor + RAG metrics
│   ├── research_tension.py           (517 lines) — Research tension detection
│   ├── ros_engine.py                 (866 lines) — Primary LLM analysis (2nd LARGEST)
│   ├── ros_logger.py                 (167 lines) — Structured JSONL logging
│   ├── security.py                   (505 lines) — Zero-trust prompt injection defense
│   ├── state_manager.py              (250 lines) — Centralized state with snapshots
│   └── worker.py                     (599 lines) — PyQt QThread analysis worker
│
├── ui/                               (10 files, ~5,524 lines) — PRODUCTION UI (PyQt6)
│   ├── __init__.py                   (1 line)
│   ├── cognitive_panels.py           (823 lines) — Breadcrumbs, contradiction highlighters
│   ├── cognitive_ux.py               (942 lines) — Widgets, badges, provenance trails
│   ├── infra_dashboard.py            (488 lines) — Engine monitoring dashboard
│   ├── input_panel.py                (948 lines) — 5-tab input panel (Paper/Script/...)
│   ├── main_window.py                (866 lines) — Main window, dark theme, streaming
│   ├── profile_dialog.py             (104 lines) — Researcher profile editor
│   ├── result_panel.py               (241 lines) — Analysis result display
│   ├── settings_dialog.py            (749 lines) — Provider/model configuration
│   ├── vault_panel.py                (317 lines) — Obsidian vault browser
│   └── workflow.py                   (48 lines) — Input validation DTOs
│
├── frontend/                         (3 files, ~783 lines) — LEGACY UI (Tkinter)
│   ├── main_window.py                (183 lines) — Basic Tkinter window
│   ├── modern_ui.py                  (425 lines) — Modern Tkinter with themes
│   └── provider_settings.py          (175 lines) — Tkinter settings dialog
│
├── tests/                            (12 files, ~1,176 lines) — PROPER TEST SUITE
│   ├── conftest.py                   (11 lines) — PyQt offscreen fixture
│   ├── test_config_reliability.py    (50 lines)
│   ├── test_graph_integrity_transactions.py (24 lines)
│   ├── test_input_file_support.py    (44 lines)
│   ├── test_main_window_startup.py   (17 lines)
│   ├── test_model_presets.py         (33 lines)
│   ├── test_performance_hot_paths.py (180 lines)
│   ├── test_professor_workflow.py    (75 lines)
│   ├── test_rag_retrieval_bounds.py  (47 lines)
│   ├── test_ros_engine_contracts.py  (100 lines)
│   ├── test_semantic_knowledge_graph.py (104 lines)
│   ├── test_v8.py                    (434 lines) — 35 comprehensive tests
│   └── test_worker_semantic_graph.py (57 lines)
│
├── [ROOT-LEVEL TEST FILES — NOT DISCOVERED BY PYTEST]
│   ├── test_api.py                   (110 lines) — Manual live API test
│   ├── test_chinese_providers.py     (265 lines) — 14 unit tests
│   ├── test_graph_integrity_transactions.py (24 lines) — DUPLICATE
│   ├── test_ui_components.py         (215 lines) — 13 shallow UI tests (HAS TYPO BUG)
│   ├── test_v4.py                    (120 lines) — Manual integration (NOT pytest)
│   ├── test_v5.py                    (184 lines) — Manual integration (NOT pytest)
│   ├── test_v7.py                    (272 lines) — Manual integration (NOT pytest)
│   └── test_worker_semantic_graph.py (57 lines) — DUPLICATE
│
├── main.py                           (46 lines) — Entry point
├── conftest.py                       (11 lines) — DUPLICATE of tests/conftest.py
├── pytest.ini                        (4 lines) — testpaths = tests
├── requirements.txt                  (9 lines) — 7 runtime deps (MISSING pytest)
├── package.json                      (18 lines) — Node.js (UNUSED Electron deps)
├── package-lock.json                 (3882 lines)
├── build_exe.bat                     (46 lines) — References missing ROS.spec
├── build_exe.sh                      (37 lines) — References missing ROS.spec
├── run.bat                           (15 lines) — Old project name
├── run.sh                            (16 lines) — Old project name
├── README.md                         (129 lines) — Korean-only
├── ARCHITECTURE.md                   (91 lines) — Refers to "v8.0" (mismatches v2.0.0)
├── CONTRIBUTING.md                   (395 lines) — Coding standards
└── UPDATES.md                        (360 lines) — Recent changes
```

### Key Directory Issues

| Directory | Issue | Severity |
|-----------|-------|----------|
| `core/` | 2 files over 800 lines (rag_engine, ros_engine) | HIGH |
| `core/` | 2 duplicated modules (obsidian_sync_old, llm_analyzer vs ros_engine) | HIGH |
| `core/` | `provider_factory.py` declares but doesn't implement openai/azure | MEDIUM |
| `ui/` | 5 files over 700 lines | MEDIUM |
| `frontend/` | Unused — `main.py` imports from `ui/`, not `frontend/` | HIGH |
| `tests/` | `pytest.ini` excludes 8 root-level test files | CRITICAL |
| `tests/` | 3 files are exact duplicates of root-level files | MEDIUM |
| Root | 8 test files invisible to pytest runner | CRITICAL |
| Root | `ROS.spec` referenced by build scripts but does not exist | CRITICAL |

---

## SECTION 3: Execution Flow

### Complete Pipeline (Paper Analysis)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                    │
│  • File upload (PDF/TXT/MD/CSV/XLSX) or direct text paste            │
│  • Select input type (Paper/Script/Dataset/Equation/Notes)            │
│  • Configure LLM provider + model                                    │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: WORKER ORCHESTRATION                                        │
│  Class: AnalysisWorker(QThread) in worker.py                         │
│  • Receives AnalysisRequest DTO                                      │
│  • Status updates via PyQt signals                                   │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: SECURITY VALIDATION                                         │
│  Class: SecurityGate in security.py                                  │
│  • Threat assessment (CLEAN→CRITICAL)                                │
│  • Pattern-based injection detection (REGEX)                         │
│  • Audit trail (JSONL)                                               │
│  • Content sanitization                                              │
│  Outcome: ValidationResult(passed, threats, sanitized_content)       │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: INPUT PARSING                                               │
│  Module: parsers.py / pdf_parser.py                                  │
│  • PDF → PyMuPDF text extraction                                     │
│  • TXT/MD → plain text read + metadata                               │
│  • CSV/XLSX → pandas DataFrame → panel structure inference           │
│  • SRT/VTT → transcript cleaning (timestamps, speakers)              │
│  Outcome: tuple(text: str, metadata: dict)                           │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 4: CACHE CHECK (optional)                                      │
│  Class: CacheEngine in perf_engine.py                                │
│  • 6-layer LRU cache (embedding, retrieval, semantic, graph,         │
│    prompt, transcript)                                               │
│  • Content-hash-based incremental computation                        │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 5: RAG CONTEXT PREPARATION                                     │
│  Class: RAGEngine in rag_engine.py                                   │
│  • 4-layer hierarchical retrieval from Obsidian vault                │
│  • Cheapest-cognition-first routing (6 paths)                        │
│  • Token budget allocation                                           │
│  • Context compression (4 methods)                                   │
│  Outcome: RetrievalPlan with assembled context                       │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 6: LLM ANALYSIS                                                │
│  Module: ros_engine.py or llm_analyzer.py                            │
│  • Provider detection from base_url/model name                       │
│  • Prompt template selection (PAPER_PROMPT, TRANSCRIPT_PROMPT, etc.) │
│  • Streaming LLM call with fallback                                  │
│  • Response parsing + graph edge extraction                          │
│  Outcome: Markdown analysis text                                     │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 7: COGNITIVE ENGINES (parallel)                                │
│  • note_evolution.py — 6-stage Zettelkasten maturity scoring         │
│  • contradiction_engine.py — rule-based contradiction detection      │
│  • idea_lineage.py — Git-style idea version tracking                 │
│  • math_ontology.py — Math object extraction + dependency graph      │
│  • research_tension.py — Cross-research tension identification       │
│  • qualitative_engine.py — Multi-epistemic mode detection (7 modes)  │
│  Outcome: Enriched Markdown + graph edges                            │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 8: KNOWLEDGE GRAPH UPDATE                                      │
│  Class: KnowledgeGraphService in knowledge_graph.py                  │
│  • SemanticMarkdownExtractor for concept/relationship extraction     │
│  • KnowledgeGraphStore for typed node/edge persistence               │
│  • Graph integrity validation (graph_integrity.py)                   │
│  Outcome: Updated knowledge graph JSON                               │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 9: OBSIDIAN SYNC                                               │
│  Module: obsidian_sync.py                                            │
│  • Topic detection from content keywords                             │
│  • Subfolder routing (Papers/Econometrics/, Transcripts/, etc.)      │
│  • Atomic write (tmp + replace) with backup                          │
│  • MOC index update (_INDEX.md)                                      │
│  • WikiLink resolution                                               │
│  Outcome: File saved in vault                                        │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 10: MEMORY PERSISTENCE                                         │
│  Module: memory.py                                                   │
│  • Save research concepts, questions, graph to ~/.ros_memory/       │
│  • Session logging (JSONL)                                           │
│  • Memory trust scoring (memory_trust.py)                            │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                        │
│  • Markdown note in Obsidian vault                                    │
│  • Updated knowledge graph                                            │
│  • Updated research memory                                            │
│  • Streamed results in UI (real-time)                                │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Classes by Step

| Step | Primary Class/Module | Lines | Patterns Used |
|------|---------------------|-------|---------------|
| 1 | `AnalysisWorker` (worker.py) | 599 | Template Method, Observer (signals) |
| 2 | `SecurityGate` (security.py) | 505 | Chain of Responsibility, Singleton |
| 3 | `parsers.py` | 302 | Strategy (detect type → dispatch parser) |
| 4 | `CacheEngine` (perf_engine.py) | 437 | LRU Cache, Flyweight |
| 5 | `RAGEngine` (rag_engine.py) | 837 | Chain of Responsibility, Strategy, Budget |
| 6 | `ros_engine.py` / `llm_analyzer.py` | 1,232 | Strategy, Template Method, Adapter |
| 7 | 5 cognitive engines | ~1,831 | Strategy, State Machine, Repository |
| 8 | `KnowledgeGraphService` | 399 | Service, Repository, Observer |
| 9 | `obsidian_sync.py` | 322 | Cache-Aside, Atomic Write |
| 10 | `memory.py` | 199 | Repository/DAO |

### Bottlenecks

1. **Step 6 — LLM call**: Network-bound, ~5-30 seconds depending on content length and provider. No caching for identical inputs.
2. **Step 7 — Cognitive engines**: Sequential execution of 5 engines (each scanning full text). No parallelization despite `orchestration.py` having thread infrastructure.
3. **Step 5 — RAG vault scan**: File-system-walk over entire Obsidian vault. Tiered with guardrails but still O(n) where n = vault file count.
4. **Step 3 — PDF parsing**: Single-threaded, no incremental/chunked processing for large PDFs.

---

## SECTION 4: Module Analysis

(Detailed per-module analysis in Section 4 continues — see full output for all 40 modules)

### Top 10 Largest Modules

| # | Module | Lines | Responsibility | Primary Issue |
|---|--------|-------|---------------|---------------|
| 1 | `rag_engine.py` | 837 | 4-layer RAG pipeline | Monolithic — should split into 4 files |
| 2 | `ros_engine.py` | 867 | LLM analysis dispatch | Duplicates llm_analyzer.py; ~500 lines of prompt templates inline |
| 3 | `worker.py` | 599 | Analysis worker thread | `_execute()` is 130 lines with nested try/except swallowing errors |
| 4 | `embedding_gov.py` | 574 | Embedding governance | Hypothetical — no actual embeddings exist |
| 5 | `qualitative_engine.py` | 527 | Multi-epistemic analysis | 7-mode facade; hardcoded signal patterns |
| 6 | `research_tension.py` | 517 | Tension detection + graph DB | Economics-only tension patterns |
| 7 | `security.py` | 505 | Prompt injection defense | Monkey-patching at module level; hardcoded patterns |
| 8 | `classifier.py` | 470 | Discipline classifier | 280-line JOURNAL_MAP hardcoded inline |
| 9 | `graph_integrity.py` | 469 | Graph transactions | Snapshots list unbounded in memory |
| 10 | `math_ontology.py` | 464 | Math object extraction | 150-line BUILTIN_MATH_ONTOLOGY hardcoded |

### Critical Redundancy

| Duplicate | Location 1 | Location 2 | Lines Duplicated |
|-----------|------------|------------|------------------|
| `_detect_provider()` | `ros_engine.py` | `llm_analyzer.py` | ~30 |
| `_max_tokens()` / `_get_max_tokens()` | `ros_engine.py` | `llm_analyzer.py` | ~25 |
| `_is_qwen3()` / `_is_qwen3_thinking()` | `ros_engine.py` | `llm_analyzer.py` | ~15 |
| `_build_client()` | `ros_engine.py` | `llm_analyzer.py` | ~15 |
| `_extract_text()` / `_extract_chunk_text()` | `ros_engine.py` | `llm_analyzer.py` | ~20 |
| `validate_api()` / `validate_api_key()` | `ros_engine.py` | `llm_analyzer.py` | ~25 |
| PDF parsing | `parsers.py::parse_pdf()` | `pdf_parser.py::extract_text_from_pdf()` | ~30 |
| Obsidian sync | `obsidian_sync.py` | `obsidian_sync_old.py` | ~212 |

**Total duplicated code**: ~1,200 lines across 8 duplications

---

## SECTION 5: Data Flow

### Primary Data Pipeline

```
RAW PDF (binary)
    │
    ▼ [PyMuPDF]
EXTRACTED TEXT (str, ~5K-65K chars)
    │
    ▼ [security.py::SecurityGate]
SANITIZED TEXT (str, threats removed)
    │
    ▼ [classifier.py::UniversalClassifier]
DISCIPLINE + TOPICS (ClassificationResult)
    │
    ▼ [rag_engine.py::RAGEngine]
AUGMENTED CONTEXT (str, assembled from vault retrieval)
    │
    ▼ [ros_engine.py::_call_llm]
LLM RESPONSE (streaming str chunks)
    │
    ▼ [cognitive engines]
ENRICHED MARKDOWN (str with frontmatter, WikiLinks, badges)
    │
    ▼ [knowledge_graph.py]
GRAPH MUTATIONS (nodes + edges)
    │
    ▼ [obsidian_sync.py::save_note_to_vault]
VAULT FILE (.md in folder structure)
    │
    ▼ [memory.py]
RESEARCH MEMORY (.json in ~/.ros_memory/)
```

### Data Size Characteristics

| Stage | Typical Size | Max Size | Constraint Source |
|-------|-------------|----------|-------------------|
| Raw PDF | 0.1–50 MB | Unlimited | File system |
| Extracted text | 1K–65K chars | 65,000 chars | `ros_engine.py` truncation |
| Sanitized text | 1K–65K chars | 65,000 chars | Same |
| RAG context | 100–16,000 chars | 16,000 chars | `rag_engine.py::MAX_RAG_CONTENT_CHARS` |
| LLM prompt | 500–70,000 chars | Model-dependent | Provider max_tokens |
| LLM response | 500–8,000 chars | Model-dependent | Provider response limit |
| Markdown output | 500–15,000 chars | 500,000 chars | `security.py::MAX_CONTENT_LENGTH` |
| Vault file | 500–15,000 chars | 500,000 chars | Same |
| Graph nodes | 1–50 per analysis | 50,000 per vault | `graph_integrity.py::MAX_NODES_PER_VAULT` |

### Bottleneck Identification

1. **Text truncation at 65K chars**: Papers with 100+ pages lose content. The "first half + last half" strategy in `pdf_parser.py` is a heuristic, not semantic chunking.
2. **RAG vault scan**: Directory walk over entire vault for every analysis. Even with file-stat caching (`obsidian_sync.py`), large vaults (>1000 notes) will be slow.
3. **Sequential cognitive engines**: 5 engines each read the full markdown output independently — 5× I/O of the same data.
4. **JSON file persistence**: All graph, memory, and config operations write entire files atomically — O(n) for large graphs.

---

## SECTION 6: Architecture Review

### Pattern Usage Assessment

| Pattern | Used? | Quality | Notes |
|---------|-------|---------|-------|
| **SOLID — Single Responsibility** | Partial | MEDIUM | `worker.py::_execute()` violates SRP (130 lines, 10+ steps). `ros_engine.py` mixes provider detection + prompt templates + analysis dispatch. |
| **SOLID — Open/Closed** | Violated | LOW | `classifier.py::JOURNAL_MAP` requires code changes to add journals. `qualitative_engine.py::_QUAL_SIGNALS` hardcoded. No plugin system. |
| **SOLID — Liskov Substitution** | Violated | MEDIUM | `BaiduERNIEProvider.__init__()` signature differs from `BaseLLMProvider.__init__()` (takes `secret_key` instead of `base_url`). |
| **SOLID — Interface Segregation** | Good | HIGH | `contracts.py` defines focused Protocols (AnalyzerProtocol, StorageProtocol). |
| **SOLID — Dependency Inversion** | Mixed | MEDIUM | `engine_loader.py` provides DI-like late binding, but ~20 singletons accessed via `get_*()` create hidden dependencies. |
| **DRY** | Violated | LOW | 8 significant code duplications (see Section 4). |
| **KISS** | Mixed | MEDIUM | Some modules are elegant (contracts.py, base_provider.py). Others are over-engineered for current feature set (embedding_gov.py for non-existent embeddings). |
| **YAGNI** | Violated | MEDIUM | `embedding_gov.py` (574 lines for non-existent embeddings), `orchestration.py` (full task queue unused in current pipeline), `frontend/` package (unused Tkinter UI). |
| **Clean Architecture** | Partial | MEDIUM | Domain contracts exist (`contracts.py`) but are not consistently used. Business logic mixes with infrastructure (LLM calls, file I/O) in same modules. |
| **Hexagonal Architecture** | No | LOW | No port/adapter separation. All modules import concrete implementations directly. |
| **Domain-Driven Design** | Partial | MEDIUM | Good domain vocabulary (NoteStage, ContradictionType, EpistemicMode). But no bounded contexts — all domains share the same namespace. |
| **Dependency Injection** | Partial | MEDIUM | `engine_loader.py` is a service locator, not true DI. No constructor injection. |
| **Repository Pattern** | Yes | HIGH | Consistently used in `memory.py`, `knowledge_graph.py`, `graph_integrity.py`, `memory_trust.py`, etc. |
| **Factory Pattern** | Partial | MEDIUM | `provider_factory.py` exists but is incomplete (declares openai/azure but doesn't implement them). No factory for analysis engines. |
| **Strategy Pattern** | Yes | HIGH | Used in `classifier.py` (detection pipeline), `ros_engine.py` (prompt selection), `rag_engine.py` (cognition routing), `qualitative_engine.py` (mode detection). |
| **Observer Pattern** | Yes | HIGH | Used in `state_manager.py` (subscribers), `worker.py` (Qt signals), `orchestration.py` (callbacks). |

### Architecture Violations

1. **Service Locator Anti-pattern**: `engine_loader.py`'s `get_*()` functions create hidden dependencies. Any module can import any engine without explicit dependency declaration.
2. **Singleton Abuse**: ~20 module-level singletons (`_gate`, `_audit`, `_service`, `_engine`) — makes testing difficult, prevents multiple isolated instances.
3. **Inconsistent Naming**: `~/.econometric_wiki/` (config, logs) vs `~/.ros_memory/` (memory) vs `~/.ros_config/` (providers) — three separate data directories from the naming migration.
4. **No API Versioning**: Analysis functions (`analyze_paper`, etc.) have no version parameter. Breaking changes to prompt templates cannot be versioned.
5. **Mixed UI Frameworks**: PyQt6 (`ui/`) and Tkinter (`frontend/`) both present. `main.py` uses PyQt6 only. Tkinter is dead code.

---

## SECTION 7: Technical Debt

### Large Files (>500 lines)

| File | Lines | Debt Type | Action |
|------|-------|-----------|--------|
| `rag_engine.py` | 837 | Monolithic class | Split into token_budget.py, retrieval.py, context_builder.py, cognition_router.py, rag_engine.py |
| `ros_engine.py` | 867 | Mixed concerns | Split by input type: paper_analyzer.py, transcript_analyzer.py, etc. Extract prompts to .txt/.yaml files |
| `worker.py` | 599 | God method | Refactor `_execute()` into discrete pipeline stages. Extract `_run_cognitive_engines()` |
| `rag_observability.py` | 604 | Two engines in one | Split into context_compressor.py and rag_observability.py |
| `embedding_gov.py` | 574 | Dead code | Archive until embeddings actually exist |
| `qualitative_engine.py` | 527 | Hardcoded signals | Externalize signal patterns to JSON/YAML config |
| `research_tension.py` | 517 | Mixed concerns | Extract KnowledgeGraphDB to separate file |
| `security.py` | 505 | Monkey-patching | Remove module-level `validate_input` injection |
| `classifier.py` | 470 | Hardcoded data | Externalize JOURNAL_MAP to JSON file |
| `graph_integrity.py` | 469 | Unbounded snapshots | Cap snapshots with LRU eviction |
| `math_ontology.py` | 464 | Hardcoded data | Externalize BUILTIN_MATH_ONTOLOGY |
| `perf_engine.py` | 437 | Three engines in one | Split CacheEngine, TokenEconomyEngine, IncrementalEngine |
| `note_evolution.py` | 413 | Recursive _try_promote | Replace recursion with iterative loop |

### Dead Code / Unused Files

| File | Status | Action |
|------|--------|--------|
| `frontend/` package (3 files) | Unused — `main.py` imports from `ui/` | Remove or move to `archive/` |
| `obsidian_sync_old.py` (318 lines) | Deprecated duplicate | Remove |
| `package.json` Electron deps | Unused — no JS runtime code | Remove `electron`, `electron-builder`, `wait-on`, `concurrently` |
| `conftest.py` (root) | Duplicate of `tests/conftest.py` | Remove root copy |
| 3 duplicate root test files | Identical to `tests/` versions | Remove root copies |
| `pdf_parser.py` (62 lines) | Redundant with `parsers.py::parse_pdf()` | Merge into `parsers.py` |

### Code Smells

| Smell | Location | Count | Severity |
|-------|----------|-------|----------|
| `print()` instead of `logger` | `provider_manager.py` (3×) | 3 | LOW |
| `datetime.utcnow()` deprecated | ~10 files | ~10 | LOW |
| Module-level mutable globals | `obsidian_sync.py`, `ros_logger.py`, `embedding_gov.py` | 5+ | HIGH |
| Monkey-patching | `security.py::_validate_input` injection | 1 | HIGH |
| Nested try/except swallowing errors | `worker.py::_execute()` | ~10 | CRITICAL |
| Hardcoded paths to `/home/ubuntu/econometric-wiki/` | `test_v5.py`, `test_api.py` | 2 | MEDIUM |
| Typo in import (`moden_ui` vs `modern_ui`) | `test_ui_components.py` | 1 | HIGH |
| `import re` inside functions | `note_evolution.py`, `contradiction_engine.py`, `perf_engine.py` | 3 | LOW |
| Silent `except Exception: pass` | `security.py::_audit.log()`, `memory.py::load_concepts()` | 4 | CRITICAL |
| Non-thread-safe caches | `obsidian_sync.py::_concept_cache` | 2 | MEDIUM |

### Missing Components

- `.gitignore` — bytecode files (`__pycache__/` with 60+ `.pyc` files) are committed
- `ROS.spec` — referenced by build scripts but does not exist
- `Pipfile.lock` — CI uses `pipenv install` but no lock file
- English README — current README is Korean-only

---

## SECTION 8: Performance Review

### Repeated Operations

| Operation | Frequency | Impact | Recommendation |
|-----------|-----------|--------|----------------|
| Vault directory walk | Every analysis | HIGH — O(n) on vault size | Cache file listing with file-stat invalidation |
| Full-text scan for WikiLinks | 3× per analysis (obsidian_sync + knowledge_graph + graph_utils) | MEDIUM | Parse once, pass parsed result downstream |
| JSON file load/save (graph) | Every mutation | MEDIUM — O(n) for large graphs | Batch mutations, incremental writes |
| `deepcopy` for state snapshots | Every property access | MEDIUM | Snapshot on write, not on read |
| Decay computation on ALL memory records | Every `retrieve()` call | HIGH — O(n) mutation during read | Batch decay on background thread |
| Cognitive engines each re-parse full markdown | 5× per analysis | MEDIUM | Parse once, pass structured representation |

### Memory Inefficiencies

1. **`graph_integrity.py::_snapshots`**: Keeps up to 20 full graph copies in memory — each could be >100K nodes.
2. **`orchestration.py::_task_results`**: Dict grows unboundedly — no eviction policy.
3. **`obsidian_sync.py::_concept_cache`**: In-memory dict keyed by file path, never evicted.
4. **`state_manager.py::_mutation_log`**: In-memory only, capped at 500 entries but not persisted — lost on restart.

### Blocking Operations

| Operation | Blocks | Impact |
|-----------|--------|--------|
| LLM API call | UI thread (via QThread offload) | Acceptable |
| PDF extraction | Worker thread | Minor — PyMuPDF is fast |
| Vault directory walk | Worker thread | Noticeable for >1000 files |
| 5 cognitive engines (sequential) | Worker thread | ~2-5 seconds total |
| JSON file write (atomic) | Worker thread | Minor unless large graph |

### Optimization Recommendations

1. **Background vault indexing**: Index vault on app startup and on file change detection, not per-analysis.
2. **Parse-once pipeline**: Extract WikiLinks, frontmatter, and concepts once; pass structured data to cognitive engines.
3. **Lazy cognitive engines**: Only run engines relevant to the input type (e.g., skip math_ontology for transcripts).
4. **Incremental graph saves**: Append-only log format instead of full-graph overwrite.
5. **Cache LLM responses**: Content-hash-based cache for identical inputs (with TTL).

---

## SECTION 9: Current Features

### Implemented Features

| Feature | Entry Point | Dependencies | Maturity | Limitations |
|---------|-------------|--------------|----------|-------------|
| Paper analysis | `ros_engine.py::analyze_paper()` | PyMuPDF, OpenAI SDK, classifier | HIGH | 65K char truncation; no LaTeX math extraction |
| Transcript analysis | `ros_engine.py::analyze_transcript()` | OpenAI SDK | HIGH | No speaker diarization; English-only cleaning |
| Dataset analysis | `ros_engine.py::analyze_dataset()` | pandas, openpyxl | MEDIUM | Panel inference heuristic-only; no statistical summary |
| Equation analysis | `ros_engine.py::analyze_equation()` | OpenAI SDK | HIGH | Text-only; no LaTeX rendering |
| Notes analysis | `ros_engine.py::analyze_notes()` | OpenAI SDK | HIGH | Simple prompt only |
| Qualitative analysis | `qualitative_engine.py` | OpenAI SDK | MEDIUM | 7-mode detection fragile; no inter-rater reliability |
| Multi-provider LLM | 12 providers | Provider modules | MEDIUM | Factory incomplete; no provider fallback cascade |
| Obsidian sync | `obsidian_sync.py` | PyYAML | HIGH | Topic detection keyword-based only |
| Knowledge graph | `knowledge_graph.py` | None | HIGH | JSON-only; no visualization; no graph queries |
| Knowledge graph visualization | `ui/cognitive_panels.py` | PyQt6 | LOW | Canvas-based placeholder; no graph layout algorithm |
| Security | `security.py` | None | MEDIUM | Regex-only injection detection; no semantic analysis |
| Fault recovery | `fault_recovery.py` | None | HIGH | Full circuit breaker; backoff + jitter |
| RAG pipeline | `rag_engine.py` | None | MEDIUM | Keyword-overlap retrieval; no embedding similarity |
| Config persistence | `config.py` | None | HIGH | Atomic write with corrupt-file backup |
| Research memory | `memory.py` | None | MEDIUM | JSON-only; no vector search |
| Note evolution | `note_evolution.py` | None | HIGH | 6-stage Zettelkasten maturity |
| Idea lineage | `idea_lineage.py` | None | HIGH | Git-style commit graph |
| Contradiction detection | `contradiction_engine.py` | None | MEDIUM | 12 contradiction types; economics-specific patterns |
| Math ontology | `math_ontology.py` | None | MEDIUM | Economics/econometrics concepts only |
| Infra dashboard | `ui/infra_dashboard.py` | PyQt6 | LOW | Monitoring UI; not connected to real metrics pipeline |

---

## SECTION 10: Missing Components

### Required for a Modern AI-Powered Research Operating System

| Component | Priority | Why Missing | Implementation Complexity |
|-----------|----------|-------------|---------------------------|
| **Vector Database** | CRITICAL | RAG uses keyword overlap — no semantic retrieval | HIGH (integrate ChromaDB/Qdrant) |
| **Embedding Pipeline** | CRITICAL | `embedding_gov.py` is governance for non-existent embeddings | HIGH (sentence-transformers, chunk → embed → store) |
| **Metadata Engine** | HIGH | No structured metadata extraction beyond basic PDF metadata | MEDIUM (title, authors, year, DOI, citations) |
| **Citation Graph** | HIGH | No citation extraction or traversal | HIGH (Semantic Scholar/CrossRef API + graph) |
| **Dataset Registry** | MEDIUM | Dataset analysis is one-shot; no persistent registry | MEDIUM (schema versioning, variable dictionary) |
| **Experiment Tracking** | MEDIUM | No support for tracking research experiments | MEDIUM (MLflow-like but for social science) |
| **Research Dashboard** | HIGH | No overview of research progress, gaps, connections | MEDIUM-HIGH |
| **Writing Assistant** | MEDIUM | No integration with writing workflow | MEDIUM (Obsidian plugin already covers some) |
| **Research Agent** | HIGH | No autonomous research capabilities (literature search, summarization) | HIGH (agent framework + tool use) |
| **Plugin System** | MEDIUM | All engines are hardcoded — no extension points | HIGH (define plugin protocol, registry, sandbox) |
| **Prompt Management** | HIGH | ~500 lines of prompt templates inline in Python files | LOW (externalize to YAML/JSON with versioning) |
| **Version Control for Notes** | MEDIUM | No diff/history for generated notes | MEDIUM (git integration or custom version store) |
| **Paper Comparison** | HIGH | No side-by-side paper comparison | MEDIUM (structured extraction + diff engine) |
| **Research Gap Detection** | HIGH | No systematic identification of research gaps | HIGH (requires citation graph + literature corpus) |
| **Hypothesis Generation** | MEDIUM | No AI-driven hypothesis suggestion | HIGH (requires knowledge graph + gap detection) |
| **Replication Engine** | LOW | No support for replicating studies | VERY HIGH |
| **Formula Graph** | MEDIUM | Math extraction is economics-only | MEDIUM (generalize math_ontology.py) |
| **Semantic Search** | CRITICAL | No semantic search over vault — only keyword | HIGH (requires vector DB + embeddings) |
| **API Server** | MEDIUM | Desktop-only; no HTTP API for integration | MEDIUM (FastAPI wrapper around core engines) |
| **Collaborative Features** | LOW | Single-user desktop app | HIGH |
| **Mobile Companion** | LOW | Desktop-only | VERY HIGH |

---

## SECTION 11: Extensibility Review

### Adding New OCR Engines

**Current**: Only PyMuPDF (fitz) for PDF. `parsers.py` has placeholder for audio (`parse_audio` returns "requires transcription").

**To add**: 
1. Define `OCREngine` Protocol in `contracts.py`
2. Implement adapter for new engine (e.g., Tesseract, Azure Document Intelligence)
3. Register in `engine_loader.py`
4. Estimated effort: **2-3 days**

### Adding New LLM Providers

**Current**: `base_provider.py` defines abstract interface. `provider_factory.py` has incomplete registry.

**To add**:
1. Create new class inheriting `BaseLLMProvider`
2. Implement `_get_headers()`, `_prepare_payload()`, `call()`
3. Register in `provider_factory.py::PROVIDERS` and `::MODELS`
4. Estimated effort: **1-2 days** (well-designed abstraction)

### Adding New Embedding Models

**Current**: No embedding pipeline exists. `embedding_gov.py` is governance-only.

**To add**:
1. Build embedding pipeline (chunking → embedding → vector DB) — **major effort**
2. `embedding_gov.py` governance layer already designed to wrap
3. Estimated effort: **2-4 weeks** for MVP

### Adding New Databases

**Current**: All JSON file-based. No abstraction for storage backend.

**To add** (e.g., SQLite, PostgreSQL):
1. Define `StorageBackend` Protocol
2. Implement Repository pattern adapters for each store
3. Requires significant refactoring of all `*_store.py` modules
4. Estimated effort: **4-8 weeks**

### Adding New UI Framework

**Current**: Dual UI (PyQt6 production, Tkinter legacy). Tight coupling between engines and PyQt-based `worker.py`.

**To add** (e.g., web UI, Electron):
1. Decouple analysis engines from UI framework — engines should not import `PyQt6`
2. Define analysis service API with callbacks (not Qt signals)
3. `worker.py` uses `QThread` and `pyqtSignal` — needs abstraction
4. Estimated effort: **4-6 weeks** for decoupling + new UI

### Adding Plugins

**Current**: No plugin system. All engines are hardcoded.

**To add**:
1. Define `PluginProtocol` with lifecycle hooks (load, configure, execute, unload)
2. Create plugin registry and discovery (entry points or config)
3. Sandbox execution (subprocess or restricted import)
4. Estimated effort: **6-12 weeks**

---

## SECTION 12: Security Review

### Authentication & Authorization

**Status**: **None** — Desktop app, single-user. No login, no user management.

**Risk**: LOW for current use case. Would become HIGH for multi-user or API server.

### Secrets Management

| Secret | Storage Location | Risk |
|--------|-----------------|------|
| API keys | `~/.ros_config/providers.json` (plaintext JSON) | MEDIUM — anyone with filesystem access can read |
| API keys | `~/.econometric_wiki/config.json` (plaintext) | MEDIUM — legacy config also has keys |
| No encryption at rest | — | HIGH for shared machines |
| No key rotation support | — | LOW for now |

**Recommendation**: Use OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service) via `keyring` library.

### File Uploads

| Concern | Status |
|---------|--------|
| File type validation | YES — extension-based in `parsers.py::detect_input_type()` |
| File size limits | PARTIAL — 512KB per file in RAG (`MAX_RAG_FILE_BYTES`) |
| Malicious PDF detection | NO — PyMuPDF reads any PDF |
| Path traversal prevention | PARTIAL — `pathlib.Path` usage helps but no explicit check |
| Zip bomb protection | NO |

### Input Validation

| Component | Validation |
|-----------|------------|
| `contracts.py::validate_analysis_request()` | YES — type + required field checks |
| `security.py::SecurityGate.validate()` | YES — threat detection + sanitization |
| LLM prompt injection | PARTIAL — regex-based only, no semantic detection |
| WikiLink injection | YES — `security.py::MAX_WIKILINKS_PER_NOTE = 150` |

### Dependency Vulnerabilities

| Concern | Status |
|---------|--------|
| `pip-audit` / `safety` scan | NOT RUN — no CI step |
| `npm audit` | NOT RUN — no CI step |
| `requirements.txt` pins minimum versions only | RISK — could install vulnerable versions |
| `package.json` Electron v42.0.1 | RISK — Electron is a high-CVE target; but unused |

---

## SECTION 13: Testing Review

### Test Coverage Summary

| Metric | Value |
|--------|-------|
| Total test files | 20 (12 in `tests/`, 8 in root) |
| Files discoverable by pytest | 12 (only `tests/` — `testpaths = tests`) |
| Total test cases (~) | 155 |
| Proper pytest tests | ~77 (12 files in `tests/`) |
| Manual test scripts | ~70 (4 files: test_api, test_v4, test_v5, test_v7) |
| Unit tests with mocks | ~50 |
| Integration tests | ~30 |
| End-to-end tests | 0 |
| Parametrized tests | 0 |
| Tests with `tmp_path` | ~15 |
| Tests with `monkeypatch` | ~10 |

### Test Structure Issues

1. **CRITICAL**: `pytest.ini::testpaths = tests` excludes 8 root-level test files. Running `pytest` silently skips ~78 tests.
2. **CRITICAL**: 4 test files (`test_api.py`, `test_v4.py`, `test_v5.py`, `test_v7.py`) are manual scripts using `print()`/`check()` — cannot be run by pytest.
3. **HIGH**: `test_ui_components.py` has a typo (`moden_ui` instead of `modern_ui`) that would cause `ImportError`.
4. **HIGH**: 3 test files are exact duplicates between root and `tests/`.
5. **MEDIUM**: Most UI tests only check `hasattr()` — no behavioral verification.
6. **MEDIUM**: No `@pytest.mark.parametrize` used anywhere.

### Missing Tests

| Area | Status |
|------|--------|
| Full analysis pipeline (end-to-end) | NOT TESTED |
| `orchestration.py` behavior | NOT TESTED (only import check) |
| `fault_recovery.py` behavior | NOT TESTED (only import check) |
| `idea_lineage.py` | NOT TESTED (only import check) |
| `math_ontology.py` | NOT TESTED (only import check) |
| `research_tension.py` | NOT TESTED (only import check) |
| `pdf_parser.py` actual extraction | NOT TESTED |
| Worker `_execute()` full flow | NOT TESTED |
| Streaming LLM response handling | NOT TESTED |
| Provider implementations (live API) | NOT TESTED (only test_api.py manual) |
| Concurrent/thread-safety | NOT TESTED |
| PyQt6 widget interactions | NOT TESTED (only construction) |

---

## SECTION 14: Migration Strategy

### Principles

1. **NEVER break existing functionality**
2. **NEVER remove existing public APIs** (only add, deprecate, then remove in next major)
3. **NEVER change user workflows** without opt-in
4. **Preserve backward compatibility** throughout
5. **Use incremental refactoring** — one module at a time

### Phase Strategy

```
Phase 0: Cleanup (Week 1-2)
    → Remove dead code, fix test structure, add .gitignore
    → No API changes

Phase 1: Stabilize (Week 3-4)
    → Fix critical bugs (typo in test, silent error swallowing)
    → Consolidate duplicated code
    → Add missing ROS.spec

Phase 2: Extract (Week 5-8)
    → Externalize hardcoded data (JOURNAL_MAP, prompts, ontology)
    → Split large files
    → No behavior changes

Phase 3: Modernize (Week 9-16)
    → Add vector DB + embedding pipeline
    → Replace keyword RAG with semantic RAG
    → Add provider fallback cascade

Phase 4: Expand (Week 17+)
    → Research agent, paper comparison, gap detection
    → Plugin system
    → API server
```

### Migration Details

#### Phase 0: Cleanup

| Action | Risk | Effort |
|--------|------|--------|
| Remove `frontend/` package | LOW — unused | 1 hour |
| Remove `obsidian_sync_old.py` | LOW — confirm no imports | 1 hour |
| Remove Electron deps from `package.json` | LOW — unused | 30 min |
| Remove duplicate root `conftest.py` | LOW | 30 min |
| Remove 3 duplicate root test files | LOW | 30 min |
| Add `.gitignore` | LOW | 30 min |
| Move root test files into `tests/` | MEDIUM — update imports | 2 hours |

#### Phase 1: Stabilize

| Action | Risk | Effort |
|--------|------|--------|
| Fix `test_ui_components.py` typo (`moden_ui` → `modern_ui`) | LOW | 15 min |
| Fix `provider_manager.py` to use `logger` instead of `print()` | LOW | 15 min |
| Remove `import re` inside functions (3 locations) | LOW | 30 min |
| Replace `datetime.utcnow()` with `datetime.now(UTC)` (10 files) | MEDIUM — test after | 2 hours |
| Consolidate `ros_engine.py` + `llm_analyzer.py` duplicate functions | HIGH — careful refactor | 4-6 hours |
| Merge `pdf_parser.py` into `parsers.py::parse_pdf()` | MEDIUM | 1 hour |
| Add missing `pytest` to `requirements.txt` | LOW | 15 min |
| Create `ROS.spec` for PyInstaller | MEDIUM — need to verify build | 2-4 hours |

#### Phase 2: Extract

| Action | Risk | Effort |
|--------|------|--------|
| Externalize `JOURNAL_MAP` (280 lines) to JSON | MEDIUM — format change | 3 hours |
| Externalize prompt templates (~500 lines) to YAML files | MEDIUM — template syntax | 4 hours |
| Externalize `BUILTIN_MATH_ONTOLOGY` (150 lines) to JSON | LOW | 1 hour |
| Split `rag_engine.py` into 4-5 files | HIGH — dependency chain | 8 hours |
| Split `worker.py::_execute()` into discrete stages | HIGH — signal chain | 6 hours |
| Extract `KnowledgeGraphDB` from `research_tension.py` | MEDIUM | 2 hours |

#### Phase 3-4: Modernize & Expand

(Details to be planned after Phase 2 completion — depends on user priorities)

---

## SECTION 15: Development Roadmap

### Phase 0: Cleanup (Week 1-2)
**Objective**: Remove dead code, fix test infrastructure
**Dependencies**: None
**Complexity**: LOW
**Risk**: LOW
**Deliverables**:
- `.gitignore` file
- Cleaned project root (8 test files → `tests/`, duplicates removed)
- `frontend/` archived
- `package.json` cleaned
- CI passes with all 155 tests

### Phase 1: Stabilize (Week 3-4)
**Objective**: Fix critical bugs and code quality issues
**Dependencies**: Phase 0
**Complexity**: MEDIUM
**Risk**: MEDIUM
**Deliverables**:
- No silent error swallowing in worker pipeline
- Consolidated `ros_engine.py` / `llm_analyzer.py` (single source of truth)
- `ROS.spec` created and build verified
- All `datetime.utcnow()` replaced
- Provider factory completes openai/azure implementation

### Phase 2: Extract (Week 5-8)
**Objective**: Externalize data, split monoliths
**Dependencies**: Phase 1
**Complexity**: HIGH
**Risk**: MEDIUM (behavior changes must be zero)
**Deliverables**:
- Prompt templates in `prompts/` directory (YAML)
- `JOURNAL_MAP` in `data/journals.json`
- `BUILTIN_MATH_ONTOLOGY` in `data/math_ontology.json`
- `rag_engine.py` split into 5 files
- `worker.py::_execute()` refactored into pipeline stages
- All existing tests pass without modification

### Phase 3: Modernize RAG (Week 9-12)
**Objective**: Replace keyword RAG with semantic RAG
**Dependencies**: Phase 2
**Complexity**: VERY HIGH
**Risk**: HIGH
**Deliverables**:
- Vector database integration (ChromaDB or Qdrant)
- Embedding pipeline (sentence-transformers)
- Semantic search over vault
- Backward compatibility: keyword fallback when embeddings unavailable
- New `test_rag_semantic.py`

### Phase 4: Research Agent (Week 13-16)
**Objective**: Autonomous research capabilities
**Dependencies**: Phase 3
**Complexity**: VERY HIGH
**Risk**: HIGH
**Deliverables**:
- Literature search agent (Semantic Scholar API)
- Paper summarization pipeline
- Research gap detection (requires citation graph)
- Hypothesis generation (requires knowledge graph traversal)

### Phase 5: Platform (Week 17-24)
**Objective**: API, plugins, collaboration
**Dependencies**: Phase 4
**Complexity**: VERY HIGH
**Risk**: VERY HIGH
**Deliverables**:
- FastAPI server wrapping core engines
- Plugin protocol + registry
- Citation graph database
- Research dashboard web UI

---

## IMPORTANT RULES SUMMARY

✅ **Only analyzed — never modified code**
✅ **Only documented — never deleted files**
✅ **Only observed — never renamed folders**
✅ **Only described — never changed public APIs**
✅ **Only recommended — never introduced breaking changes**

---

*This document should be treated as the master architecture reference for all future development of the ROS project. It captures the state as of July 31, 2026 and will need periodic updates as the codebase evolves.*