# ROS v8.0 — Architecture Document

## System Overview

Research Operating System (ROS) is a scientific cognition infrastructure for researchers across all academic disciplines. It transforms raw research materials (papers, transcripts, datasets, equations) into a structured, interconnected Obsidian knowledge graph.

## Domain Ownership Map

| Domain | Module(s) | Responsibility |
|--------|-----------|----------------|
| **Input** | `parsers.py` | PDF, text, CSV, audio script parsing |
| **Classification** | `classifier.py` | Universal discipline classifier (45 fields, 400+ journals) |
| **Analysis** | `ros_engine.py`, `qualitative_engine.py` | LLM analysis pipeline, multi-epistemic modes |
| **Cognition A** | `note_evolution.py` | 6-stage note maturity lifecycle |
| **Cognition B** | `contradiction_engine.py` | Rule-based + LLM contradiction detection |
| **Cognition C** | `idea_lineage.py` | Git-style intellectual genealogy tracking |
| **Cognition D** | `math_ontology.py` | Mathematical object extraction and linking |
| **Cognition E** | `research_tension.py` | Research tension detection + knowledge graph DB |
| **RAG** | `rag_engine.py`, `embedding_gov.py`, `rag_observability.py` | 4-Layer retrieval, embedding governance, observability |
| **Security** | `security.py` | Zero-trust input validation, prompt injection defense |
| **Integrity** | `graph_integrity.py` | Transaction mutations, rollback checkpoints |
| **Memory** | `memory_trust.py` | Trust decay, hallucination reinforcement prevention |
| **Performance** | `perf_engine.py` | Token economy, multi-layer cache, incremental compute |
| **Orchestration** | `orchestration.py` | Async queue, resource governance |
| **Fault Recovery** | `fault_recovery.py` | Circuit breaker, exponential backoff, safe mode |
| **Persistence** | `obsidian_sync.py` | Atomic writes, topic-folder routing, index MOC |
| **Infrastructure** | `engine_loader.py`, `ros_logger.py` | Lazy engine loading, unified structured logging |
| **Contracts** | `contracts.py` | Strong-typed domain contracts (Protocol-based) |
| **Observability** | `observability.py` | Structured logging, telemetry, metrics |
| **State** | `state_manager.py` | Explicit state ownership, immutable state management |
| **Memory (Long)** | `memory.py` | Researcher profile, long-term research memory |
| **Config** | `config.py` | API keys, vault path, classification rules persistence |

## Data Flow

```
Input (PDF/Text/CSV/Script/Equation)
    ↓ parsers.py
    ↓ security.py (Zero-Trust validation)
    ↓ classifier.py (discipline detection)
    ↓ rag_engine.py (4-Layer context retrieval)
    ↓ ros_engine.py / qualitative_engine.py (LLM analysis)
    ↓ [5 Cognitive Engines run in parallel]
    ↓ obsidian_sync.py (atomic write → topic folder)
    ↓ Obsidian Vault (_INDEX.md updated)
```

## Key Design Decisions

**1. Cheapest-Cognition-First (RAG)**
L1 exact match → L2 keyword → L3 graph traversal → L4 LLM API. Minimizes token cost.

**2. Engine Loader Pattern**
All 20+ engines are lazily initialized via `engine_loader.py`. Failures are isolated — one engine crash does not block the pipeline.

**3. Atomic Writes**
All Obsidian vault writes use `.tmp` → `os.replace()` pattern. No partial file corruption possible.

**4. Zero Global State in Hot Path**
Global singletons exist only as module-level caches behind `engine_loader.py`. The analysis pipeline itself is stateless.

**5. Multi-Epistemic Support**
7 epistemological modes (positivist, interpretivist, critical, mixed, computational, experimental, auto) allow the system to serve both quantitative and qualitative researchers.

## Test Coverage

```
tests/test_v8.py — 35 tests (unit + integration + edge-case + regression)
  ✅ Security: injection detection, safe input, empty input
  ✅ Classifier: economics/nature journals, unknown fallback, discipline map
  ✅ Note Evolution: register, frontmatter injection
  ✅ Contradiction Engine: rule scan, weak IV detection
  ✅ Obsidian Sync: file creation, atomic write, index MOC
  ✅ Regressions: KeyError 'D,Y', streaming empty, None attribute, obsidian pass
  ✅ Edge Cases: empty markdown, unicode title, long title, unicode injection
  ✅ Integration: security→classifier pipeline, save+scan, engine loader registry
```

## Supported Disciplines (45 fields)

Social Sciences: Economics, Sociology, Political Science, Psychology, Anthropology, Communication, Education, Geography, Criminology, Demography, Law, Social Work, Urban Studies

Natural Sciences: Physics, Chemistry, Biology, Mathematics, Statistics, Earth Science, Environmental Science, Astronomy, Ecology, Neuroscience, Marine Science, Materials Science

Engineering & Applied: Computer Science, ML/AI, Engineering, Data Science, Operations Research, Information Systems

Health & Medicine: Medicine, Public Health, Epidemiology, Pharmacology, Clinical Psychology, Nursing, Dentistry

Humanities: History, Philosophy, Linguistics, Literature, Cultural Studies, Archaeology, Religious Studies

Interdisciplinary: Cognitive Science, Complexity Science, STS, Sustainability Science
