# Phase 6 Extension Implementation Review

Date: 2026-09-04

Source reviewed: user-provided `PHASE 6 -- CONTROLLED SYSTEM EXTENSION AND RESEARCH CAPABILITY EVOLUTION`

## Executive Decision

PHASE 6 STATUS: ACCEPT WITH CONDITIONS

The repository appears ready for Phase 6 discovery, prioritization, and design work. It should not yet jump directly into major semantic, vector, agent, or autonomous mutation features.

The safest first implementation target is:

> Extract a Qt-free `AnalysisPipeline` from `AnalysisWorker`, then use that pipeline as the stable boundary for future API, RAG, semantic graph, and agent extensions.

This is an enabling extension rather than a flashy feature. It improves extensibility, testability, API readiness, rollback safety, and controlled mutation boundaries without changing research semantics.

Implementation update:

P6-001 has now been implemented as a minimal behavior-preserving program change:

- Added `core/analysis_pipeline.py`.
- Updated `core/worker.py` so `AnalysisWorker` delegates orchestration to `AnalysisPipeline`.
- Added `tests/test_analysis_pipeline.py` to pin the new Phase 6 boundary.
- Verified the full suite with `python3 -m pytest -q`: `333 passed, 5 warnings`.

## Current Repository Context

ROS is currently a PyQt desktop application that turns research material into Obsidian-ready Markdown notes and semantic graph state.

Relevant existing components:

- `core/worker.py`: the current end-to-end analysis orchestration path.
- `core/pipeline/pipeline.py`: document processing pipeline for validation, identification, parsing, OCR placeholder, cleaning, normalization, and storage.
- `core/contracts.py`: typed DTOs and Protocol boundaries for analysis, storage, cache, classification, and observability.
- `core/interfaces.py`: provider interfaces for OCR, parsing, embeddings, search, storage, graph, and agents.
- `core/knowledge_graph.py`: typed semantic graph with stable IDs, atomic JSON persistence, capped wikilink extraction, and idempotent upserts.
- `core/embedding_gov.py`: bounded shingle-based deduplication; despite the name, this is not yet an embedding system.
- `core/rag_engine.py`: current retrieval implementation, still mostly local and keyword/graph-oriented rather than true vector semantic retrieval.

Relevant tests checked in this review:

- `tests/test_phase1_hardening.py`
- `tests/test_phase2_secure.py`
- `tests/test_phase3_correct.py`
- `tests/test_phase4_refactor.py`
- `tests/test_semantic_knowledge_graph.py`

Verification run:

```text
python3 -m pytest tests/test_phase1_hardening.py tests/test_phase2_secure.py tests/test_phase3_correct.py tests/test_phase4_refactor.py tests/test_semantic_knowledge_graph.py -q

101 passed, 5 warnings in 7.13s
```

Note: the first sandboxed test attempt failed because `core/ros_logger.py` attempted to write to `~/.econometric_wiki/logs/ros.log`, which is outside the managed workspace sandbox. The same command passed with normal execution permission.

## Phase 6 Entry Checklist

| Requirement | Status | Evidence / Note |
|---|---|---|
| No unresolved P0 issue blocks safe development | Pass for reviewed scope | Security, persistence, stream completion, graph migration, and semantic graph tests passed. |
| No unresolved P1 data-integrity issue affects proposed extension | Pass for reviewed scope | Atomic writes, corrupt-file quarantine, graph dangling-edge rejection, and idempotent migration are tested. |
| Relevant database migrations are stable | Pass for typed graph migration | Legacy-to-typed graph migration is sentinel-idempotent and non-destructive. |
| Relevant semantic graph operations are understood | Pass | `KnowledgeGraphStore.apply()` validates edge endpoints and writes atomically. |
| Existing note lifecycle behavior is documented | Partial pass | Note evolution has tests for stable versioning; broader lifecycle docs should be expanded before semantic lifecycle changes. |
| Relevant API boundaries are understood | Partial pass | DTOs and Protocols exist, but `AnalysisWorker` still bypasses them in the main path. |
| Relevant security boundaries are identified | Pass for current path | Raw input, parsed file content, and LLM output gates are tested. |
| Existing regression tests are available or can be created | Pass | Phase tests already pin important regressions. |
| The extension has a rollback strategy | Needs design | Pipeline extraction can be rolled back by routing `AnalysisWorker` back to existing `_execute()`. |
| The extension has a clear research purpose | Pass if scoped to pipeline boundary | Enables safer research capability evolution without changing canonical knowledge. |

Conclusion: Phase 6 can begin at Phase 6A-6C. High-impact implementation should wait for a small ADR and test scaffold.

## Research Justification

Research Problem:

Researchers need ROS to evolve from a single desktop workflow into a durable scientific cognition infrastructure while preserving provenance, graph meaning, trust boundaries, and note lifecycle semantics.

Existing Limitation:

The main analysis flow is concentrated inside `AnalysisWorker._execute()`. This couples UI threading, status signals, file parsing, security gates, RAG, LLM calls, cognitive engines, graph mutation, cache writes, and Obsidian persistence.

Required Cognitive Capability:

ROS needs controlled extension points where research workflows, retrieval systems, semantic graph operations, and future agents can be added without silently changing the meaning of existing notes or graph objects.

System Capability:

A Qt-free `AnalysisPipeline` can become the single application service boundary. Desktop UI, future FastAPI endpoints, and experimental agents can all call the same pipeline.

Minimal Extension:

Extract existing behavior into a pure Python pipeline while preserving `AnalysisWorker` signals and current user workflow.

Measurable Research Benefit:

- Lower regression risk for research-note creation.
- Clearer provenance and mutation boundaries.
- More testable analysis stages.
- Future API/RAG/agent features can be introduced behind explicit contracts.

## Candidate Extensions

| ID | Extension | Category | Impact | Recommendation |
|---|---|---:|---:|---|
| P6-001 | Qt-free `AnalysisPipeline` extraction | E1, E7 | Level 2 | NOW |
| P6-002 | Phase 6 Extension Ledger and ADR templates | E7 | Level 0 | NOW |
| P6-003 | SearchProvider boundary for current RAG | E4, E7 | Level 2 | NEXT |
| P6-004 | Vector/embedding semantic RAG in shadow mode | E4, E7, E10 | Level 3 | NEXT, experimental |
| P6-005 | First-class contradiction object design | E2, E6 | Level 3 | NEXT, design first |
| P6-006 | Research agent for literature synthesis | E3, E8 | Level 3-4 | LATER |
| P6-007 | Autonomous graph mutation agent | E3, E10 | Level 4 | REJECT for now |

## Recommended NOW Extension: AnalysisPipeline Extraction

### Extension Name

Controlled Analysis Pipeline Boundary

### Extension Category

E1 -- Research Workflow Extension

E7 -- Provider / Infrastructure Extension

### Impact Level

Level 2 -- Cross-module.

It touches worker orchestration, DTOs, tests, and possibly document parsing integration. It must not change graph schema, note identity, note maturity, provenance semantics, or Obsidian file format.

### Scientific Objective

Make the research-analysis lifecycle explicit and inspectable:

```text
Input
 -> Security Validation
 -> Parsing
 -> Parsed Content Validation
 -> Cache / Incremental Check
 -> RAG Context
 -> Existing Concept Retrieval
 -> LLM Analysis
 -> LLM Output Validation
 -> Cognitive Engine Enrichment
 -> Graph Mutation
 -> Memory / Cache Persistence
 -> Obsidian Save
 -> Result
```

### Non-Goals

- No vector database yet.
- No embedding dependency yet.
- No new agent.
- No semantic graph schema change.
- No automatic note promotion.
- No autonomous mutation authority.
- No provider SDK replacement.

### Existing Components Reused

- `AnalysisRequest`, `AnalysisResult`, `LLMConfig`, `VaultConfig`, `ResearcherProfile` from `core/contracts.py`.
- `DocumentPipeline` from `core/pipeline/pipeline.py`, initially as an optional file-processing path.
- Engine loader wrappers from `core/worker.py` or direct `core.engine_loader` calls.
- `SecurityGate` behavior currently accessed through `_get_security_layer()`.
- Existing `ros_engine.analyze_*` functions.
- Existing cognitive engines.
- Existing graph, memory, cache, and Obsidian sync logic.

### New Components

Suggested files:

```text
core/analysis_pipeline.py
tests/test_analysis_pipeline.py
docs or root ADR file: ADR-001-analysis-pipeline-boundary.md
```

If no docs directory is introduced, keep ADRs at repository root or under `architecture/` only after choosing a convention.

### Modified Components

- `core/worker.py`: keep `AnalysisWorker` as Qt adapter; delegate execution to `AnalysisPipeline`.
- `core/contracts.py`: add fields only if necessary and with backward-compatible defaults.
- `tests/test_phase*_*.py`: preserve existing tests; add new tests instead of rewriting established regression coverage.

## Proposed Implementation Sequence

1. Write a small ADR for the pipeline boundary.
2. Add `AnalysisCallbacks` dataclass with optional callables:
   - `on_token(text)`
   - `on_status(text)`
   - `on_engine_update(name, payload)`
   - `is_cancelled()`
3. Add `AnalysisPipeline.run(...)`.
4. Move the internal logic of `AnalysisWorker._execute()` into pipeline stage methods with behavior-preserving names.
5. Make `AnalysisWorker._execute()` construct DTOs, call the pipeline, and emit final/error/save signals.
6. Add unit tests for pipeline stages with optional engines neutralized.
7. Add adapter tests proving existing PyQt signals still fire.
8. Run existing phase tests plus new pipeline tests.

## Minimal API Shape

```python
@dataclass
class AnalysisCallbacks:
    on_token: Callable[[str], None] | None = None
    on_status: Callable[[str], None] | None = None
    on_engine_update: Callable[[str, dict], None] | None = None
    is_cancelled: Callable[[], bool] | None = None


class AnalysisPipeline:
    def run(
        self,
        request: AnalysisRequest,
        llm_config: LLMConfig,
        vault_config: VaultConfig,
        callbacks: AnalysisCallbacks | None = None,
    ) -> Result[AnalysisResult, str]:
        ...
```

This shape keeps future FastAPI and CLI entry points from depending on PyQt.

## Security Boundary Map

Current critical boundaries to preserve:

| Boundary | Required Rule |
|---|---|
| User text -> Security gate | Fail closed if validation fails or gate unavailable. |
| Imported file -> Parser | Parser failures must be signals, not LLM content. |
| Parsed file content -> Security gate | Validate after parse before LLM. |
| Retrieved context -> LLM | Mark retrieved context as untrusted and not instructions. |
| LLM output -> Graph / Memory / Vault | Validate before any mutation. |
| Cognitive engine output -> Graph | Cap node/link growth and validate names. |
| Graph mutation -> Store | Atomic and idempotent writes only. |
| Future agent -> Mutation | Draft mutation only unless explicitly approved. |

## Semantic Compatibility Test

The `AnalysisPipeline` extraction should answer all semantic compatibility questions as "no change":

| Question | Expected Answer |
|---|---|
| Does this change note identity? | No |
| Does this change note maturity? | No |
| Does this change note lineage? | No |
| Does this change provenance? | No |
| Does this change contradiction handling? | No |
| Does this change research object relationships? | No |
| Does this invalidate old notes? | No |
| Does this require migration? | No |
| Can older data still be interpreted? | Yes |

If any answer changes during implementation, the extension becomes Level 3 and requires a stronger ADR.

## Persona Reviews

### Persona A: Senior Software / Platform Architect

Position:

Accept with conditions. The pipeline extraction reduces coupling and improves testability. It should avoid introducing a large framework or dependency injection container.

Concerns:

- Do not create parallel orchestration systems.
- Keep existing engine loader behavior stable.
- Preserve public imports and UI behavior.
- Avoid moving all code at once if smaller stage extraction is possible.

Required action:

Use a small service class and callback object. No new runtime dependency is needed.

### Persona B: Security, Reliability, and Data Integrity Architect

Position:

Accept with conditions. The refactor is acceptable only if the existing security gates remain fail-closed and LLM output still cannot reach graph, memory, cache, or vault before validation.

Concerns:

- Current tests prove important boundaries; new pipeline tests must pin those boundaries again.
- Cache persistence must not store SafeMode fallback output.
- Graph failures should remain isolated from final analysis output.
- Any future API endpoint must not bypass the pipeline.

Required action:

Add tests for raw input blocking, parsed file blocking, poisoned LLM output blocking, SafeMode non-cache behavior, and graph failure isolation through the new pipeline.

### Persona C: Scientific Knowledge Infrastructure Architect

Position:

Accept. This extension improves scientific integrity by making transformation stages visible and reviewable.

Concerns:

- Do not let pipeline extraction become an excuse to flatten epistemic modes.
- Do not introduce vector similarity as a replacement for lineage, contradiction, or provenance.
- Keep qualitative and interpretive material valid in the same flow as quantitative/econometric material.

Required action:

Document the pipeline as a research transformation lifecycle, not merely an engineering workflow.

## Cross Review

### Extension Review Conflict

**Proposal:** Extract `AnalysisPipeline` before adding Phase 6 research capabilities.

**Persona A Position:** This is architecturally necessary and low-risk if kept small.

**Persona B Position:** This is acceptable only if every existing security/data-integrity regression is re-pinned at the new boundary.

**Persona C Position:** This is useful because it makes epistemic transformations explicit.

**Core Conflict:** How much refactoring is safe before adding user-visible research capability?

**Trade-Off:** Refactoring first delays visible features, but adding features directly to `AnalysisWorker` increases long-term semantic and reliability risk.

**Final Decision:** Extract the pipeline first.

**Reasoning:** Phase 6 is about controlled extension. The current worker is the main uncontrolled extension pressure point.

**Reversibility:** High. `AnalysisWorker` can route back to the old `_execute()` during rollback if the extraction is staged cleanly.

## Extension Admission Gate

| Criterion | Score | Notes |
|---|---:|---|
| Research Value | 4/5 | Indirect but foundational for trustworthy research workflows. |
| Scientific Integrity | 5/5 | Preserves existing semantics while making transformations clearer. |
| Architectural Fit | 5/5 | Matches existing `contracts.py` and Phase 3C plan. |
| Security Risk | 3/5 | Refactor risk exists; mitigated by existing tests. |
| Data Integrity Risk | 3/5 | Must preserve graph/cache/vault ordering. |
| Complexity Cost | 2/5 | Small if only a service/callback boundary is introduced. |
| Operational Cost | 1/5 | No new provider or background job. |
| Maintenance Cost | 2/5 | Should reduce maintenance cost after migration. |
| Reversibility | 4/5 | High if the worker adapter remains. |
| Testability | 5/5 | Major improvement. |
| Interoperability | 4/5 | Prepares CLI/API/web use. |

Decision: ACCEPT WITH CONDITIONS.

## Phase 6 Extension Ledger

| ID | Extension | Category | Impact | Status | Risk | Tests | Rollback |
|---|---|---|---:|---|---|---|---|
| P6-001 | Controlled Analysis Pipeline Boundary | E1, E7 | 2 | IMPLEMENTED | Medium | `tests/test_analysis_pipeline.py` + full suite | Worker can delegate to old flow if reintroduced |
| P6-002 | Extension Ledger / ADR templates | E7 | 0 | ACCEPTED | Low | Docs review | Remove docs only |
| P6-003 | SearchProvider boundary for current RAG | E4, E7 | 2 | DEFERRED TO NEXT | Medium | Contract + retrieval regression | Keep current `rag_engine.py` path |
| P6-004 | Vector semantic RAG shadow mode | E4, E7, E10 | 3 | EXPERIMENTAL LATER | High | Retrieval, provenance, latency, fallback | Disable feature flag, rebuild derived index |
| P6-005 | First-class contradiction objects | E2, E6 | 3 | DESIGN ONLY | High | Semantic regression tests | Keep current contradiction report format |
| P6-006 | Literature synthesis agent | E3, E8 | 3 | LATER | High | Agent eval + security + provenance | Read-only mode |
| P6-007 | Autonomous graph mutation agent | E3, E10 | 4 | REJECTED FOR NOW | Critical | Not applicable | Not implemented |

## Implementation Backlog

### NOW

1. Create ADR for `AnalysisPipeline`.
2. Add `AnalysisCallbacks`.
3. Extract pipeline without behavior change.
4. Keep `AnalysisWorker` as adapter.
5. Add focused pipeline regression tests.

### NEXT

1. Introduce `SearchProvider` adapter around existing RAG behavior.
2. Add shadow-mode vector retrieval proposal without mutating canonical graph.
3. Design contradiction objects as semantic records, not just tags.
4. Add provenance and attribution checks to semantic regression cases.

### LATER

1. API endpoint calling the same pipeline.
2. Read-only research agents.
3. Human-review mutation proposals.
4. Background indexing with visible checkpoints and idempotency keys.

### REJECT FOR NOW

1. Autonomous graph mutation.
2. Multi-agent orchestration without separable scientific roles.
3. Vector embeddings as canonical research memory.
4. New semantic graph schema fields without migration and rollback plan.

## Testing Strategy

Required before merging P6-001:

- Unit tests for each pipeline stage.
- Contract tests for `AnalysisRequest`, `AnalysisResult`, `LLMConfig`, and `VaultConfig` use.
- Regression tests copied/adapted from current worker security tests.
- Graph mutation failure isolation test.
- Cache fallback non-persistence test.
- Obsidian auto-save success/failure adapter test.
- Cancellation checkpoints test.
- Existing phase regression suite.

Suggested command:

```text
python3 -m pytest tests/test_analysis_pipeline.py tests/test_phase1_hardening.py tests/test_phase2_secure.py tests/test_phase3_correct.py tests/test_phase4_refactor.py tests/test_semantic_knowledge_graph.py -q
```

## Rollback Strategy

For P6-001:

1. Keep `AnalysisWorker._execute()` behavior available until pipeline tests are stable.
2. Introduce routing through a small internal switch if needed:

```text
ROS_USE_ANALYSIS_PIPELINE=1
```

3. If regressions occur, set the switch off or revert only the worker delegation patch.
4. Since no schema migration is involved, no data rollback should be required.

For future semantic or vector features:

- Use feature flags.
- Treat embeddings and vector indexes as derived data.
- Preserve canonical Markdown and typed graph as source of truth.
- Make reindexing safe and idempotent.

## Observability Requirements

The pipeline should preserve or improve answers to:

- What input was analyzed?
- Which parser was used?
- Which security gates passed?
- Which model/provider was used?
- Was RAG used?
- Which graph mutations were attempted?
- Which persistence actions succeeded?
- Was output fallback, cached, or fresh?
- What failed and at what stage?

## Final Recommendation

Begin Phase 6 with controlled architecture work, not autonomous research features.

The first concrete implementation should be `AnalysisPipeline` extraction. It is the best leverage point because it reduces the risk of every later extension: semantic RAG, citation-aware retrieval, contradiction objects, API endpoints, and research agents.

Phase 6 should remain conservative:

```text
Small stable capability
 -> explicit boundary
 -> tests
 -> shadow mode for high-risk features
 -> human review for canonical mutations
 -> production only after semantic regression checks
```
