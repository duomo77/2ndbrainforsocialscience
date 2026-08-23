# REFACTOR_PLAN.md — ROS Refactoring Strategy

**Date**: 2026-07-31
**Role**: Google Staff Software Engineer
**Predecessor Document**: REFACTOR.md (Architectural Audit)
**Scope**: Documentation only — no code modifications

---

## SECTION 1: Refactoring Goals

### Long-Term Vision

Transform the existing Research Operating System (ROS) desktop application into a **modular, extensible, AI-powered Research OS** for social science researchers. The target state is:

- A **plugin-based architecture** where OCR engines, LLM providers, embedding models, parsers, and cognitive engines are swappable components
- A **semantic knowledge layer** backed by vector databases, enabling true semantic search and retrieval-augmented generation
- A **research agent framework** that can autonomously search literature, compare papers, identify research gaps, and suggest hypotheses
- A **collaborative platform** with a REST API, web dashboard, and multi-user support
- **Preserved backward compatibility** — every feature that works today must continue working throughout the migration

### Core Principles

1. **Incremental, never big-bang**: Each phase delivers a working, shippable product
2. **Backward compatibility as law**: No existing API, CLI, or user workflow may break
3. **Deprecation before deletion**: Old code gets `@deprecated` warnings for at least one phase before removal
4. **Test-first refactoring**: Every module refactored must have tests in place before changes begin
5. **Strangler Fig pattern**: New implementations run alongside old ones; routing switches gradually

---

## SECTION 2: Backward Compatibility Strategy

### API Preservation Rules

| Category | Rule | Enforcement |
|----------|------|-------------|
| Public function signatures | Add parameters with defaults only (`param: Optional[X] = None`) | Code review + type checker |
| Return types | Widen only (`str` → `str | None`), never narrow | mypy strict mode |
| Module import paths | Add new paths, deprecate old ones with re-exports | Import-time warning |
| Config file format | Add fields, never remove or rename | Migration script for reading old formats |
| CLI arguments | Add flags, never remove | argparse defaults |
| Vault file format | Add frontmatter fields, never change existing keys | Backward-compatible parser |
| Memory JSON schema | Version field + migrator for each version | Schema versioning |

### CLI & Entry Point

```
main.py — MUST remain the primary entry point
run.sh / run.bat — MUST continue to work
build_exe.sh / build_exe.bat — MUST produce working executables
```

### User Workflow Preservation

The existing 10-step pipeline (Input → Security → Parse → Cache → RAG → LLM → Cognitive Engines → Graph → Obsidian Sync → Memory) must produce identical output for identical inputs throughout the migration.

### Incremental Shipping

```
Phase N complete  →  tag release v{N+2}.0.0
Phase N+1 starts  →  new code is opt-in (feature flag or separate endpoint)
Phase N+1 stable  →  new code becomes default, old code deprecated
Phase N+2 starts  →  old code removed if no issues for 1 release cycle
```

---

## SECTION 3: Technical Debt Priority

### CRITICAL (Must Fix Before Any Feature Work)

| # | Item | Impact | Difficulty | Engineering Value | Business Value |
|---|------|--------|------------|-------------------|----------------|
| C1 | **pytest.ini excludes 8 root test files** | CI runs ~77 tests instead of ~155 — silent regression risk | LOW (2 hours) | VERY HIGH — 2× test coverage | MEDIUM — prevents undetected bugs |
| C2 | **ROS.spec missing** | Build scripts fail — cannot deploy | MEDIUM (4 hours) | HIGH — unblocks CI/CD | HIGH — enables releases |
| C3 | **worker.py error swallowing** (10+ bare excepts) | Silent failures → corrupted output, impossible to debug | MEDIUM (6 hours) | VERY HIGH — debuggability | HIGH — data integrity |
| C4 | **Code duplication ros_engine ↔ llm_analyzer** (~130 lines) | Bug fixes must be applied twice; drift already visible | HIGH (6 hours) | HIGH — single source of truth | MEDIUM — fewer bugs |
| C5 | **frontend/ package dead code** (783 lines) | Confuses new developers; import risk | LOW (1 hour) | MEDIUM — cleaner codebase | LOW — no user impact |
| C6 | **obsidian_sync_old.py dead code** (318 lines) | Same as above | LOW (1 hour) | MEDIUM | LOW |

### HIGH (Should Fix Before Architecture Changes)

| # | Item | Impact | Difficulty | Engineering Value | Business Value |
|---|------|--------|------------|-------------------|----------------|
| H1 | **~500 lines of prompt templates inline** (ros_engine) | Changing prompts requires code change + redeploy | MEDIUM (4 hours) | HIGH — enables non-dev prompt iteration | HIGH — faster prompt improvement |
| H2 | **JOURNAL_MAP 280-line inline dict** (classifier) | Adding journal/discipline requires code change | LOW (3 hours) | HIGH — data-driven configuration | MEDIUM — broader journal coverage |
| H3 | **3 separate config directories** (~/.econometric_wiki, ~/.ros_memory, ~/.ros_config) | Confusing; naming migration incomplete | MEDIUM (3 hours) | MEDIUM — consistency | LOW |
| H4 | **No .gitignore** | Bytecode committed; repo bloated | LOW (30 min) | HIGH — clean repo | LOW |
| H5 | **test_ui_components.py typo** (`moden_ui`) | Test file broken on import | LOW (15 min) | MEDIUM — test reliability | LOW |
| H6 | **datetime.utcnow() deprecated** (10+ files) | Deprecation warnings; breaks on Python 3.14+ | LOW (2 hours) | MEDIUM — future-proofing | LOW |
| H7 | **provider_manager.py uses print() not logger** | Inconsistent; no log level control | LOW (15 min) | LOW | LOW |
| H8 | **import re inside functions** (3 locations) | Minor perf hit; code smell | LOW (30 min) | LOW | LOW |

### MEDIUM (Improve During Feature Work)

| # | Item | Impact | Difficulty | Engineering Value | Business Value |
|---|------|--------|------------|-------------------|----------------|
| M1 | **rag_engine.py 837-line monolith** | Hard to test individual layers | HIGH (8 hours) | HIGH — testability | MEDIUM — fewer RAG bugs |
| M2 | **worker.py::_execute() 130-line god method** | Hard to reason about; impossible to unit-test stages | HIGH (6 hours) | HIGH — testability | MEDIUM |
| M3 | **BUILTIN_MATH_ONTOLOGY 150-line inline** | Economics-only; not extensible | LOW (1 hour) | MEDIUM — data-driven | MEDIUM — broader field support |
| M4 | **Cognitive engines sequential execution** | 5× full-text parse of same document | MEDIUM (4 hours) | MEDIUM — performance | MEDIUM — faster analysis |
| M5 | **No API key encryption at rest** | Plaintext in JSON file | LOW (2 hours, keyring lib) | MEDIUM — security | LOW — single-user desktop |
| M6 | **embedding_gov.py for non-existent embeddings** (574 lines) | Governance without governed system | MEDIUM | — | — (deprioritize until embeddings exist) |

### LOW (Nice to Have)

| # | Item | Impact | Difficulty |
|---|------|--------|------------|
| L1 | `package.json` name "econometric-wiki" → "ros" | Cosmetic | LOW |
| L2 | Korean-only README → bilingual | Accessibility | MEDIUM |
| L3 | `pytest.ini` missing `addopts = -v` | Developer experience | LOW |
| L4 | `pip install` one-by-one in run.bat/run.sh | Fragile | LOW |
| L5 | `python` vs `python3` inconsistency in docs | macOS confusion | LOW |

---

## SECTION 4: Migration Phases

### Phase 0: Cleanup & Foundation (Week 1-2)

**Goal**: Remove dead code, fix test infrastructure, establish CI reliability.

**Dependencies**: None

**Risk**: LOW — purely subtractive changes, no behavior modifications

**Complexity**: LOW

**Deliverables**:
- `.gitignore` committed (no more bytecode in repo)
- `frontend/` package documented as deprecated or moved to `archive/`
- `obsidian_sync_old.py` removed
- 3 root duplicate test files removed
- 5 remaining root test files moved into `tests/` with updated imports
- `pytest.ini` updated: `testpaths = tests` → all tests discoverable
- Root `conftest.py` removed (duplicate)
- `package.json` cleaned (Electron deps removed or documented)
- CI pipeline (`ci.yml`) verified to run all ~155 tests

**Exit criteria**: `pytest -v` runs all 20 test files and reports pass/fail correctly

---

### Phase 1: Stabilize (Week 3-4)

**Goal**: Fix critical bugs, consolidate duplicated code, add missing build artifacts.

**Dependencies**: Phase 0

**Risk**: MEDIUM — some refactoring of shared code paths

**Complexity**: MEDIUM

**Engineering Tasks**:

| Task | File(s) | Effort | Verification |
|------|---------|--------|--------------|
| 1.1 | Fix `test_ui_components.py` typo | `test_ui_components.py` | 15 min | `pytest tests/test_ui_components.py` |
| 1.2 | Replace `print()` → `logger` | `provider_manager.py` | 15 min | `grep -r "print(" core/` returns 0 results |
| 1.3 | Move `import re` to module top | `note_evolution.py`, `contradiction_engine.py`, `perf_engine.py` | 30 min | Linter pass |
| 1.4 | Replace `datetime.utcnow()` → `datetime.now(UTC)` | ~10 files | 2 hours | `grep -r "utcnow"` returns 0 results |
| 1.5 | Consolidate `_detect_provider`, `_max_tokens`, `_is_qwen3`, `_build_client`, `_extract_text`, `validate_api` | Extract from `ros_engine.py` + `llm_analyzer.py` → new `core/provider_utils.py` | 6 hours | All existing tests pass; `llm_analyzer.py` imports from `provider_utils.py` |
| 1.6 | Merge `pdf_parser.py` into `parsers.py` | `parsers.py` (add `extract_text_from_pdf`), delete `pdf_parser.py` | 1 hour | PDF tests pass; grep for `pdf_parser` import returns 0 |
| 1.7 | Create `ROS.spec` | New file | 4 hours | `build_exe.sh` succeeds on macOS |
| 1.8 | Add `pytest` to `requirements.txt` | `requirements.txt` | 15 min | Fresh venv + `pip install -r requirements.txt` → `pytest` available |
| 1.9 | Fix `provider_factory.py` — implement openai/azure | `provider_factory.py` | 2 hours | All provider factory tests pass |
| 1.10 | Replace bare `except: pass` with `logger.error()` | `security.py`, `memory.py`, etc. | 2 hours | No silent exception swallowing in hot paths |

**Exit criteria**: All 155+ tests pass, build succeeds, no silent error swallowing

---

### Phase 2: Extract & Externalize (Week 5-8)

**Goal**: Move hardcoded data and prompts out of Python source; split monoliths without behavior change.

**Dependencies**: Phase 1

**Risk**: MEDIUM-HIGH — structural changes; behavior must remain identical

**Complexity**: HIGH

**Engineering Tasks**:

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Externalize `JOURNAL_MAP` (280 lines) → `data/journals.json` | Modify `classifier.py` to load from JSON with inline fallback | 3 hours |
| 2.2 | Externalize prompt templates (~500 lines) → `prompts/` directory | Create `prompts/system.yaml`, `prompts/paper.yaml`, `prompts/transcript.yaml`, etc. Load via YAML in `ros_engine.py` with inline fallback | 4 hours |
| 2.3 | Externalize `BUILTIN_MATH_ONTOLOGY` (150 lines) → `data/math_ontology.json` | Same pattern — JSON with inline fallback | 1 hour |
| 2.4 | Externalize contradiction/detection patterns | `data/contradiction_patterns.json`, etc. | 2 hours |
| 2.5 | Split `rag_engine.py` (837 lines) | `core/rag/token_budget.py`, `core/rag/retrieval_ranker.py`, `core/rag/hierarchical_retriever.py`, `core/rag/context_builder.py`, `core/rag/engine.py`. Create `core/rag/__init__.py` re-exporting all public APIs to preserve imports | 8 hours |
| 2.6 | Split `worker.py::_execute()` into pipeline stages | Extract `_validate()`, `_parse()`, `_retrieve_context()`, `_analyze_llm()`, `_run_cognitive_engines()`, `_update_graph()`, `_sync_vault()`, `_persist_memory()` as separate methods with explicit error handling per stage | 6 hours |
| 2.7 | Consolidate 3 config directories | Migrate `~/.econometric_wiki/` → `~/.ros_config/`; `~/.ros_memory/` → `~/.ros_config/memory/`. Add migration script that copies old files if they exist | 4 hours |
| 2.8 | Extract `KnowledgeGraphDB` from `research_tension.py` | Move to `core/knowledge_graph_db.py`; `research_tension.py` imports from there | 2 hours |

**Exit criteria**: All behavior identical (verified by test suite); all hardcoded data externalized; `rag_engine.py` and `worker.py` manageable sizes

---

### Phase 3: Foundation Layer (Week 9-14)

**Goal**: Build the missing infrastructure layer — vector database, embedding pipeline, API server foundation.

**Dependencies**: Phase 2

**Risk**: HIGH — new subsystems with integration complexity

**Complexity**: VERY HIGH

**Sub-Phase 3A: Embedding Pipeline (Week 9-10)**

| Task | Description | Effort |
|------|-------------|--------|
| 3A.1 | Add `sentence-transformers` dependency | Install + pin version in `requirements.txt` | 1 hour |
| 3A.2 | Create `core/embedding/embedder.py` | `Embedder` class: chunk text → generate embeddings via sentence-transformers. Configurable model (default: `all-MiniLM-L6-v2`) | 8 hours |
| 3A.3 | Create `core/embedding/chunker.py` | `SemanticChunker`: split content by section/paragraph with overlap. Replace truncation-based approach | 6 hours |
| 3A.4 | Integrate with `embedding_gov.py` | Wire `EmbeddingGovernanceEngine.should_embed()` into the pipeline | 4 hours |

**Sub-Phase 3B: Vector Database (Week 11-12)**

| Task | Description | Effort |
|------|-------------|--------|
| 3B.1 | Add `chromadb` dependency | Install + pin version | 1 hour |
| 3B.2 | Create `core/vector/vector_store.py` | `VectorStore` abstract interface + `ChromaVectorStore` implementation. Methods: `add`, `search`, `delete`, `count` | 8 hours |
| 3B.3 | Create `core/vector/vault_indexer.py` | `VaultIndexer`: on startup, index all vault notes into vector DB. Incremental update on file change (watchdog) | 8 hours |
| 3B.4 | Replace keyword RAG with semantic RAG | Update `rag_engine.py` to use `VectorStore.search()` instead of file-system walk. Keep keyword fallback for when vector DB is unavailable | 8 hours |

**Sub-Phase 3C: API Foundation (Week 13-14)**

| Task | Description | Effort |
|------|-------------|--------|
| 3C.1 | Add `fastapi`, `uvicorn` dependencies | 1 hour |
| 3C.2 | Create `api/` package with `app.py` | FastAPI app with health check, `/analyze` endpoint (delegates to existing engines) | 8 hours |
| 3C.3 | Decouple `worker.py` from PyQt6 | Extract `AnalysisPipeline` class (no Qt dependency) that `AnalysisWorker` wraps. `AnalysisPipeline` can be called from API | 12 hours |
| 3C.4 | Create `api/models.py` | Pydantic models mirroring `contracts.py` DTOs for request/response | 4 hours |

**Exit criteria**: Semantic RAG functional (keyword-agnostic retrieval); vector DB populated and queryable; REST API serves analysis requests

---

### Phase 4: Research Intelligence (Week 15-20)

**Goal**: Add research-specific AI capabilities — citation graph, paper comparison, gap detection, hypothesis generation.

**Dependencies**: Phase 3

**Risk**: HIGH — depends on external APIs; LLM quality varies

**Complexity**: VERY HIGH

**Sub-Phase 4A: Metadata & Citation (Week 15-16)**

| Task | Description | Effort |
|------|-------------|--------|
| 4A.1 | Create `core/metadata/extractor.py` | `MetadataExtractor`: extract structured metadata (title, authors, year, DOI, abstract, journal) from PDF/text using LLM | 8 hours |
| 4A.2 | Integrate Semantic Scholar API | `core/citation/semantic_scholar.py`: fetch citation graph, paper details, references/citations by DOI | 8 hours |
| 4A.3 | Create `core/citation/citation_graph.py` | `CitationGraph`: directed graph of paper→paper relationships stored in knowledge graph DB | 8 hours |

**Sub-Phase 4B: Paper Comparison (Week 17-18)**

| Task | Description | Effort |
|------|-------------|--------|
| 4B.1 | Create `core/comparison/paper_comparer.py` | `PaperComparer`: given 2+ papers, produce structured comparison (methodology, findings, assumptions, datasets) | 12 hours |
| 4B.2 | Comparison UI integration | Add "Compare Papers" tab to `ui/input_panel.py` | 6 hours |

**Sub-Phase 4C: Gap Detection & Hypothesis (Week 19-20)**

| Task | Description | Effort |
|------|-------------|--------|
| 4C.1 | Create `core/gap_detection/gap_detector.py` | `GapDetector`: analyze citation graph + knowledge graph to identify under-explored areas | 12 hours |
| 4C.2 | Create `core/hypothesis/hypothesis_generator.py` | `HypothesisGenerator`: given research gap + researcher profile, suggest testable hypotheses | 12 hours |

**Exit criteria**: Researchers can ask "what should I study next?" and receive grounded suggestions based on the knowledge graph

---

### Phase 5: Platform (Week 21-30)

**Goal**: Plugin system, research dashboard, writing assistant, multi-user API.

**Dependencies**: Phase 4

**Risk**: VERY HIGH — architectural transformation

**Complexity**: VERY HIGH

**Sub-Phase 5A: Plugin System (Week 21-24)**

| Task | Description | Effort |
|------|-------------|--------|
| 5A.1 | Define `PluginProtocol` | Abstract base class with `name`, `version`, `initialize()`, `execute()`, `shutdown()` | 4 hours |
| 5A.2 | Create `core/plugin/registry.py` | `PluginRegistry`: discover plugins from `plugins/` directory, validate protocol compliance, manage lifecycle | 8 hours |
| 5A.3 | Convert existing engines to plugins | Refactor OCR, parser, LLM provider, embedding, and cognitive engines to implement `PluginProtocol`. Each becomes a self-contained plugin package | 40 hours |
| 5A.4 | Plugin configuration UI | Add plugin manager panel to settings dialog | 8 hours |

**Sub-Phase 5B: Research Dashboard (Week 25-27)**

| Task | Description | Effort |
|------|-------------|--------|
| 5B.1 | Create web dashboard (`dashboard/`) | React or simple HTML/JS frontend served by FastAPI | 40 hours |
| 5B.2 | Real-time metrics pipeline | Connect `observability.py` metrics to dashboard via WebSocket | 12 hours |
| 5B.3 | Research overview visualizations | Knowledge graph viz, citation network, research timeline, gap heatmap | 20 hours |

**Sub-Phase 5C: Final Polish (Week 28-30)**

| Task | Description | Effort |
|------|-------------|--------|
| 5C.1 | Writing assistant | Integrate with LLM for section-by-section paper writing, reference management | 20 hours |
| 5C.2 | Experiment tracking | Dataset registry with versioning, variable dictionary, reproduction checklist | 20 hours |
| 5C.3 | Full test coverage push | Target 85%+ line coverage across all core modules | 20 hours |
| 5C.4 | Documentation | User guide, API docs (OpenAPI), plugin development guide | 16 hours |

**Exit criteria**: Plugin ecosystem functional; dashboard provides research overview; writing assistant integrated

---

## SECTION 5: Recommended Target Architecture

### Layer Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  PyQt6   │  │  Web UI  │  │ REST API │  │   CLI (future)       │ │
│  │ Desktop  │  │ Dashboard│  │  Server  │  │                      │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │
│       │              │              │                    │            │
├───────┴──────────────┴──────────────┴────────────────────┴───────────┤
│                        SERVICE LAYER                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    AnalysisPipeline (no UI deps)                │ │
│  │  validate → parse → retrieve → analyze → enrich → persist      │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                                │                                      │
├────────────────────────────────┴─────────────────────────────────────┤
│                        DOMAIN LAYER                                   │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────────┐ │
│  │ Cognitive │ │ Research  │ │ Knowledge │ │   Research Agent   │ │
│  │ Engines   │ │ Analysis  │ │  Graph    │ │   Framework        │ │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └──────────┬─────────┘ │
│        │              │              │                   │           │
├────────┴──────────────┴──────────────┴───────────────────┴──────────┤
│                     INFRASTRUCTURE LAYER                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────────┐ │
│  │  Plugin  │ │  Vector  │ │ Embedding│ │   External APIs        │ │
│  │ Registry │ │  Store   │ │ Pipeline │ │   (LLM, Scholar, ...)  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────────┬───────────┘ │
│       │              │              │                    │           │
├───────┴──────────────┴──────────────┴────────────────────┴──────────┤
│                        DATA LAYER                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────────┐ │
│  │  Config  │ │  Memory  │ │  Graph   │ │   File System          │ │
│  │  Store   │ │  Store   │ │  Store   │ │   (Obsidian Vault)     │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Interactions

```
User Request
    │
    ▼
Presentation Layer (PyQt6 / Web / API)
    │
    ▼
AnalysisPipeline
    │
    ├──► Plugin Registry ──► OCR Plugin (PDF→text)
    │         │
    │         ├──► Parser Plugin (CSV, TSV, etc.)
    │         │
    │         └──► LLM Provider Plugin (Qwen, DeepSeek, ...)
    │
    ├──► Security Gate (no change from current)
    │
    ├──► Vector Store ◄── Embedding Pipeline
    │         │                  │
    │         │    ┌─────────────┘
    │         │    │
    │         ▼    ▼
    │      Semantic RAG (replaces keyword RAG)
    │
    ├──► LLM Analysis (uses prompt templates from data layer)
    │
    ├──► Cognitive Engines (parallel, plugin-based)
    │         ├── Note Evolution
    │         ├── Contradiction Detection
    │         ├── Idea Lineage
    │         ├── Math Ontology
    │         └── Research Tension
    │
    ├──► Knowledge Graph
    │         │
    │         ├──► Semantic Markdown Extractor
    │         ├──► Citation Graph (connected via DOI)
    │         └──► Graph Integrity (transactions, rollback)
    │
    ├──► Obsidian Sync (unchanged)
    │         │
    │         └──► Vault Indexer ──► Vector Store (incremental update)
    │
    └──► Memory Persistence (unchanged)
              │
              └──► Metadata Store (new: structured paper metadata)
              └──► Dataset Registry (new: variable dictionary, schema)
              └──► Experiment Tracker (new: hypothesis → result log)
```

### Data Layer Details

| Store | Backend (Current) | Backend (Target) | Purpose |
|-------|-------------------|------------------|---------|
| Config | `~/.ros_config/config.json` (JSON) | Same | App settings, provider configs |
| Memory | `~/.ros_config/memory/` (JSON) | SQLite | Research concepts, questions, profile |
| Knowledge Graph | `~/.ros_config/graph/` (JSON) | SQLite + JSON backup | Typed nodes and edges |
| Citation Graph | None | SQLite + JSON backup | Paper→paper citation network |
| Vector Store | None | ChromaDB (persistent) | Embedding-based semantic search |
| Metadata Store | None | SQLite | Structured paper/dataset metadata |
| Dataset Registry | None | SQLite | Variable dictionary, schema versions |
| Experiment Tracker | None | SQLite | Hypothesis → result log |
| Vault | Obsidian folder (Markdown) | Same | Generated research notes |

---

## SECTION 6: Plugin Strategy

### Plugin Protocol

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    category: str  # "ocr", "parser", "llm", "embedding", "cognitive", "search", "writer", "agent"

class PluginProtocol(ABC):
    """Every plugin must implement this interface."""
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Called once on plugin load. Return True on success."""
        ...
    
    @abstractmethod
    def execute(self, input_data: Any, context: Dict[str, Any]) -> Any:
        """Primary execution method."""
        ...
    
    @abstractmethod
    def shutdown(self) -> None:
        """Called on plugin unload or app shutdown."""
        ...
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        ...
```

### Plugin Categories & Conversions

| Category | Current Hardcoded Module | Plugin Conversion |
|----------|--------------------------|-------------------|
| **OCR** | `parsers.py::parse_pdf()` (PyMuPDF) | `plugins/ocr_pymupdf/` — PyMuPDF adapter implementing `PluginProtocol`. Future: `plugins/ocr_tesseract/`, `plugins/ocr_azure/` |
| **Parser** | `parsers.py::parse_dataset()` (pandas) | `plugins/parser_csv/`, `plugins/parser_excel/`, `plugins/parser_transcript/` |
| **LLM Provider** | `qwen_provider.py`, `chinese_providers.py` | Each provider becomes a plugin implementing `PluginProtocol`. New providers can be added by dropping a folder into `plugins/` |
| **Embedding** | None — to be built | `plugins/embedding_sentence_transformers/`, `plugins/embedding_openai/`, `plugins/embedding_cohere/` |
| **Cognitive** | 5 hardcoded engines | Each becomes a plugin: `plugins/cognitive_note_evolution/`, `plugins/cognitive_contradiction/`, etc. |
| **Search** | Keyword-only | `plugins/search_keyword/` (current), `plugins/search_semantic/` (vector), `plugins/search_hybrid/` |
| **Knowledge Graph** | Hardcoded extractor | `plugins/graph_markdown_extractor/` — pluggable extraction strategies |
| **Writer** | None — to be built | `plugins/writer_section/`, `plugins/writer_reference/`, `plugins/writer_style/` |
| **Agent** | None — to be built | `plugins/agent_literature_search/`, `plugins/agent_paper_summary/`, `plugins/agent_hypothesis/` |

### Plugin Directory Structure

```
plugins/
├── __init__.py
├── registry.py            # PluginRegistry class
├── protocol.py            # PluginProtocol + PluginMetadata
│
├── ocr_pymupdf/
│   ├── __init__.py
│   ├── plugin.py          # Implements PluginProtocol
│   └── plugin.yaml        # Metadata (name, version, config schema)
│
├── provider_deepseek/
│   ├── __init__.py
│   ├── plugin.py
│   └── plugin.yaml
│
├── embedding_sentence_transformers/
│   ├── __init__.py
│   ├── plugin.py
│   └── plugin.yaml
│
└── cognitive_note_evolution/
    ├── __init__.py
    ├── plugin.py
    └── plugin.yaml
```

### Plugin Configuration

Each `plugin.yaml`:

```yaml
name: "deepseek-provider"
version: "1.0.0"
description: "DeepSeek LLM provider integration"
author: "ROS Team"
category: "llm"
config_schema:
  api_key:
    type: string
    required: true
    secret: true
  model:
    type: string
    default: "deepseek-chat"
    enum: ["deepseek-chat", "deepseek-coder"]
```

### Backward Compatibility During Plugin Conversion

During Phase 5A, existing hardcoded engine imports continue to work. Plugin versions of the same engines are loaded alongside. The `engine_loader.py` is updated to check for plugin overrides:

```python
def get_classifier():
    """Returns classifier — plugin if available, built-in as fallback."""
    plugin = registry.get("universal-classifier")
    if plugin and plugin.is_active:
        return plugin
    from core.classifier import UniversalClassifier
    return UniversalClassifier()
```

---

## SECTION 7: Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **vector DB integration breaks existing RAG** | MEDIUM | HIGH | Keep keyword RAG as fallback; feature-flag semantic RAG behind `--use-semantic-search` |
| **plugin protocol too rigid for future use cases** | MEDIUM | MEDIUM | Start with minimal protocol (init/execute/shutdown), add optional hooks later |
| **ChromaDB performance on large vaults (>10K notes)** | LOW | MEDIUM | Benchmark before release; provide migration path to Qdrant if needed |
| **LLM provider API changes break integrations** | HIGH | MEDIUM | Abstract provider interface already well-designed; add integration tests with recorded API responses (VCR pattern) |
| **PyQt6 ↔ API server dual code paths diverge** | MEDIUM | HIGH | Extract `AnalysisPipeline` as single source of truth; both UI and API delegate to it |
| **SQLite concurrent access from API server** | LOW | MEDIUM | Use WAL mode; single-writer architecture acceptable for research tool |

### Migration Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Regressions from monolith splitting** | HIGH | HIGH | Comprehensive test suite BEFORE splitting; diff output comparison (old vs new code on same input) |
| **Externalized data files not found at runtime** | MEDIUM | HIGH | Always ship inline defaults; use `importlib.resources` for package data |
| **Config directory migration loses user settings** | LOW | CRITICAL | Migration script creates backups; old paths supported for 2 release cycles |
| **Plugin loading breaks on missing dependency** | MEDIUM | MEDIUM | Graceful degradation — skip plugin, log warning, continue with built-in |
| **Phase 3-5 take longer than estimated** | HIGH | MEDIUM | Each phase produces shippable product; prioritize features within phase |

### Performance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Embedding generation on startup blocks UI** | HIGH | MEDIUM | Background thread for vault indexing; incremental updates |
| **Vector DB disk usage grows unboundedly** | MEDIUM | LOW | TTL-based eviction; max storage config |
| **API server adds latency for desktop users** | LOW | LOW | Desktop mode uses direct function calls, not HTTP |
| **Semantic search slower than keyword for small vaults** | MEDIUM | LOW | Route small vaults (<100 notes) to keyword search automatically |

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **API server exposes engines to network** | MEDIUM | CRITICAL | Auth required (API key or OAuth); rate limiting; input validation at API boundary |
| **Plugin code has unrestricted access** | MEDIUM | HIGH | Plugin sandbox (subprocess or restricted import); code review for official plugins |
| **API keys in plugin config files** | HIGH | MEDIUM | OS keychain integration (Phase 3); encrypted at rest |
| **Prompt injection via API endpoint** | MEDIUM | HIGH | Reuse existing `security.py` gate at API boundary |

### Maintenance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Plugin ecosystem fragments the codebase** | MEDIUM | MEDIUM | Monorepo for official plugins; clear plugin development guide |
| **Dual PyQt6 + Web UI increases maintenance** | HIGH | MEDIUM | Shared `AnalysisPipeline` minimizes duplication; PyQt6 remains primary until web UI matures |
| **Dependency version conflicts (sentence-transformers, chromadb, fastapi)** | MEDIUM | MEDIUM | Pin all versions; Dependabot for automated updates; CI tests all combinations |

---

## SECTION 8: Development Roadmap (Detailed)

### Phase 0: Cleanup & Foundation

**Timeline**: Week 1-2
**Complexity**: LOW
**Dependencies**: None

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W1 | Add `.gitignore`, remove `frontend/` + `obsidian_sync_old.py`, remove duplicate root test files, clean `package.json` | Clean project root; no dead code |
| W1 | Move 5 unique root test files to `tests/`, update imports, remove root `conftest.py` | All tests in `tests/` |
| W1 | Update `pytest.ini` — no `testpaths` restriction | `pytest` discovers all tests |
| W2 | Verify CI passes, fix any test failures from moves | Green CI badge |
| W2 | Tag `v2.1.0-cleanup` | Release |

---

### Phase 1: Stabilize

**Timeline**: Week 3-4
**Complexity**: MEDIUM
**Dependencies**: Phase 0

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W3 | Tasks 1.1–1.4: typo fix, logger, import cleanup, datetime migration | Code quality improvements |
| W3 | Task 1.5: Consolidate duplicate provider utils into `core/provider_utils.py` | Single source of truth for provider detection |
| W3 | Task 1.6: Merge `pdf_parser.py` into `parsers.py` | Single PDF parsing entry point |
| W4 | Task 1.7: Create `ROS.spec` and verify build | Build succeeds |
| W4 | Tasks 1.8–1.9: Add pytest to requirements, complete provider factory | CI fully functional |
| W4 | Task 1.10: Replace bare excepts with proper error handling | No silent failures |
| W4 | Tag `v2.2.0-stable` | Release |

---

### Phase 2: Extract & Externalize

**Timeline**: Week 5-8
**Complexity**: HIGH
**Dependencies**: Phase 1

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W5 | Task 2.1: Externalize JOURNAL_MAP → `data/journals.json` | Data-driven classifier |
| W5 | Task 2.2: Externalize prompts → `prompts/*.yaml` | Prompt templates editable without code changes |
| W5 | Tasks 2.3–2.4: Externalize ontology + patterns | All hardcoded data in `data/` |
| W6 | Task 2.5: Split `rag_engine.py` into 5 files under `core/rag/` | Testable RAG layers |
| W7 | Task 2.6: Refactor `worker.py::_execute()` into pipeline stages | Testable worker stages |
| W7 | Task 2.7: Consolidate config directories → `~/.ros_config/` | Single config location |
| W8 | Task 2.8: Extract `KnowledgeGraphDB` from `research_tension.py` | Decoupled graph DB |
| W8 | Verify all 155+ tests pass; behavior unchanged | Regression-free refactor |
| W8 | Tag `v2.3.0-extracted` | Release |

---

### Phase 3: Foundation Layer

**Timeline**: Week 9-14
**Complexity**: VERY HIGH
**Dependencies**: Phase 2

#### 3A: Embedding Pipeline (W9-10)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W9 | Add sentence-transformers; create `Embedder` class | Functional embedding generation |
| W9 | Create `SemanticChunker` | Smart text chunking |
| W10 | Wire `embedding_gov.py` into new pipeline | Cost-governed embedding |

#### 3B: Vector Database (W11-12)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W11 | Add chromadb; create `VectorStore` + `ChromaVectorStore` | Persistent vector storage |
| W11 | Create `VaultIndexer` with startup indexing + watchdog | Auto-indexed vault |
| W12 | Replace keyword RAG with semantic RAG (with fallback) | Semantic search functional |

#### 3C: API Foundation (W13-14)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W13 | Add fastapi/uvicorn; create `api/app.py` with `/analyze` endpoint | REST API serving analysis |
| W13 | Extract `AnalysisPipeline` (no Qt) from `worker.py` | UI-free analysis engine |
| W14 | Create Pydantic API models; add API integration tests | Tested API |
| W14 | Tag `v3.0.0-foundation` | Release |

---

### Phase 4: Research Intelligence

**Timeline**: Week 15-20
**Complexity**: VERY HIGH
**Dependencies**: Phase 3

#### 4A: Metadata & Citation (W15-16)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W15 | Create `MetadataExtractor` (LLM-based) | Structured paper metadata |
| W15 | Integrate Semantic Scholar API | Citation data fetching |
| W16 | Create `CitationGraph` | Paper→paper citation network |

#### 4B: Paper Comparison (W17-18)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W17 | Create `PaperComparer` | Structured paper comparison |
| W18 | Add comparison UI tab | User-facing comparison feature |

#### 4C: Gap Detection & Hypothesis (W19-20)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W19 | Create `GapDetector` | Research gap identification |
| W20 | Create `HypothesisGenerator` | AI-suggested hypotheses |
| W20 | Tag `v3.1.0-research` | Release |

---

### Phase 5: Platform

**Timeline**: Week 21-30
**Complexity**: VERY HIGH
**Dependencies**: Phase 4

#### 5A: Plugin System (W21-24)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W21 | Define `PluginProtocol` + `PluginRegistry` | Plugin infrastructure |
| W22-23 | Convert engines to plugins (OCR, parser, LLM, embedding, cognitive) | All engines as plugins |
| W24 | Plugin configuration UI; migration guide | User-manageable plugins |
| W24 | Tag `v3.2.0-plugins` | Release |

#### 5B: Research Dashboard (W25-27)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W25 | Dashboard frontend scaffold (React or HTMX) | Web dashboard skeleton |
| W26 | Real-time metrics WebSocket | Live observability |
| W27 | Knowledge graph viz, citation network, gap heatmap | Visual research overview |
| W27 | Tag `v3.3.0-dashboard` | Release |

#### 5C: Final Polish (W28-30)

| Week | Tasks | Deliverables |
|------|-------|--------------|
| W28 | Writing assistant integration | Section-by-section AI writing |
| W29 | Experiment tracking + dataset registry | Reproducible research support |
| W30 | Full test coverage push (85%+), documentation | Production-ready release |
| W30 | Tag `v4.0.0` | **ROS v4.0 GA** |

---

### Summary Timeline

```
Week  1-2  ████ Phase 0: Cleanup
Week  3-4  ████ Phase 1: Stabilize
Week  5-8  ████████ Phase 2: Extract & Externalize
Week  9-14 ████████████ Phase 3: Foundation (Embedding + Vector + API)
Week 15-20 ████████████ Phase 4: Research Intelligence
Week 21-30 ████████████████████ Phase 5: Platform
           ─────────────────────────────────────────────
           Total: 30 weeks (~7.5 months) to v4.0.0
```

---

*This document is the master refactoring plan for the ROS project. It should be reviewed and updated at the end of each phase with actual progress, discoveries, and any priority changes.*