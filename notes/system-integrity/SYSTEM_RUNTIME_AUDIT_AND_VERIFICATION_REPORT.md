# System Runtime Audit and Verification Report

## 1. Executive Summary

The React/TypeScript frontend and FastAPI runtime boot locally and execute the demo analysis path. The audit reproduced five defects, applied focused fixes, and reran the complete Python regression suite. Final evidence is `346 passed, 6 warnings`; the frontend typecheck/build also passes. No confirmed P0 issue remains in the tested local scope. Research-integrity features are present but not all roadmap claims are complete.

## 2. Project Purpose

This repository is an AI-native research second brain for humanities and social-science work. It transforms raw documents and research notes into derived Markdown, graph relations, and optional Obsidian notes while preserving source distinction, provenance, uncertainty, and contradiction signals.

## 3. Repository Architecture

The active runtime is `main.py` -> FastAPI (`api/app.py`) -> `api/runtime.py` -> the Qt-free `core/analysis_pipeline.py`. React/Vite in `frontend/` is the user interface. The legacy PyQt UI and worker remain optional compatibility code; PyQt is not in the default requirements or web runtime.

## 4. Research Knowledge Architecture

Raw input is parsed and security-scanned. Generated Markdown is a derived artifact, typed semantic graph and memory stores are derived state, and an optional Obsidian vault is the durable user-facing Markdown destination. The runtime now records `source_type`, `source_ref`, transformation model, `ai_generated`, `human_verified`, `evidence_status`, and `citation_status` in generated frontmatter.

## 5. Runtime Environment

| Item | Evidence |
|---|---|
| Python | 3.13.0 |
| Node | 22.13.0 |
| npm | 10.9.2 |
| Backend | FastAPI + Uvicorn on `127.0.0.1:8000` |
| Frontend | Vite dev server on `127.0.0.1:5173` |
| Package manager | npm with `package-lock.json` |
| Canonical persistence | UTF-8 Markdown and JSON stores |

## 6. Baseline Results

Before the final fixes, the existing baseline was install PASS, build PASS, and `337 passed, 6 warnings`. Runtime reproduction then found vault path traversal, multipart field loss, unbounded upload reads, frontmatter injection, and cached auto-save omission. These findings were converted into regression tests before final verification.

## 7. Dependency Map

Python dependencies cover parsing, metadata, FastAPI, Uvicorn, multipart uploads, and literature providers. JavaScript dependencies cover React, React DOM, Vite, TypeScript, Lucide icons, and concurrent dev processes. `npm ci`, `pip check`, and `npm audit --omit=dev --audit-level=high` passed in this environment; npm audit reported zero vulnerabilities.

## 8. Data Flow Map

```text
React input
  -> /api/analyze or /api/analyze-file
  -> upload/type/security validation
  -> parser
  -> bounded RAG context
  -> local demo or selected LLM provider
  -> LLM-output security gate
  -> epistemic/provenance envelope
  -> cognitive engines
  -> canonical Markdown save (optional)
  -> graph, memory, cache, and integrity indexes
  -> React result and runtime events
```

## 9. Source-of-Truth Matrix

| State | Canonical | Derived | Rebuildable |
|---|---|---|---|
| Original uploaded/raw source | User file / original vault source | No | No |
| Generated Markdown note | Yes when auto-saved | No | No, unless source and model are retained |
| Typed semantic graph | No | Yes | Yes from Markdown |
| Legacy graph and memory trust | No | Yes | Partial |
| Analysis cache | No | Yes | Yes |
| RAG/vector layer | No real vector store found | Yes/roadmap | Intended yes |

## 10. Security Boundary Map

Raw text and parsed file content pass the security gate before analysis. LLM output passes a second gate before downstream mutation. Uploads are extension-allowlisted, streamed, and capped at 50 MiB. Obsidian writes validate resolved containment, reject symlink escapes, and use durable atomic replacement. API keys are kept in request memory and are not placed in generated provenance.

## 11. Obsidian Integration

`core/obsidian_sync.py` classifies notes into type/topic folders, updates `_INDEX.md`, rotates hidden backups, excludes backup files from scans, and preserves the original note when atomic replacement fails. A real user vault was not mutated; temporary vault tests cover Korean/Unicode filenames, backups, traversal, symlinks, idempotent index updates, and failure preservation.

## 12. Zotero / Citation Integration

Zotero metadata is accepted by the provider/paper analysis path and literature providers preserve provenance structures. The runtime deliberately marks generated citation state `NOT_VERIFIED`; no live Zotero account or citation database was available for end-to-end verification. Citation hallucination detection beyond this state marker remains a risk.

## 13. Semantic Graph

The typed graph persists nodes and typed edges with endpoint validation and atomic JSON state. Markdown wikilinks are ingested as graph relations. Stable graph identity is not based solely on a filename in the typed store, but full rename/delete reconciliation across all caches is only partially verified.

## 14. Retrieval and RAG

Current RAG is bounded local retrieval with token budgeting, graph/local candidates, caching, and observability. No production embedding provider or vector database implementation was found. Exact lexical and graph retrieval remain the dependable fallback; multilingual and formula retrieval benchmarks are not yet present. External reference architectures were inspected for ideas only: Karpathy-style raw/wiki separation, Obsidian-second-brain skill/MCP workflows, Khoj synchronization, and Smart Connections local-first embeddings. No external implementation code was copied.

## 15. AI Provider Architecture

Provider detection and validation are isolated in `core/ros_engine.py` and provider profiles. The shared knowledge model does not require rewriting when the provider changes. Live provider calls were not run because no user credential was supplied; `demo-local` provides deterministic no-key runtime coverage.

## 16. Research Provenance

Generated notes carry source type/reference, transformation, model, AI-generated, human-verified, evidence, citation, and timestamps. The source reference for browser uploads is the original filename rather than a temporary path. Full claim-level page/quote provenance is not guaranteed for every provider output.

## 17. Contradiction Handling

Rule-based contradiction scanning and scientific-context contradiction states exist, and existing tests cover contested evidence. A complete cross-paper contradiction workflow with human resolution, supporting/contradicting source sets, and hypothesis lineage is only partially implemented.

## 18. Note Evolution

`core/note_evolution.py` maintains note IDs, stages, maturity, versions, ancestors, descendants, and merge lineage. The analysis pipeline injects its fields without replacing the source text. Full lifecycle transitions from fleeting note through research program need broader end-to-end fixtures.

## 19. Security Findings

| Finding | Severity | Status |
|---|---|---|
| Topic traversal / symlink vault escape | P0/P1 boundary risk | Fixed and regression-tested |
| Multipart upload field loss | P1 functional | Fixed and regression-tested |
| Unbounded upload read | P1 reliability | Fixed and regression-tested |
| Frontmatter title injection | P1 integrity | Fixed and regression-tested |
| Cached auto-save omission | P1 functional | Fixed and regression-tested |

## 20. Database Findings

No relational database was found. JSON/file stores are used. Typed graph mutations validate endpoints and commit atomically within their own store. Cross-store transactions are not fully atomic.

## 21. File-System Findings

The prior direct-write fallback was removed from note persistence. Temp files are written, flushed, fsynced, and replaced; backup copies are made before replacement. Directory fsync is used where supported. Concurrent writer races and filesystem-specific crash injection remain unverified.

## 22. Runtime Failures Reproduced

The audit reproduced all five listed defects with temporary vaults, FastAPI `TestClient`, and a cache stub. Each reproduction has a named regression test in `tests/test_analysis_pipeline.py`, `tests/test_web_api.py`, or `tests/test_phase2_secure.py`.

## 23. Code Changes Applied

The focused changes are in `core/obsidian_sync.py`, `core/analysis_pipeline.py`, `core/utils/markdown_utils.py`, `api/app.py`, `api/runtime.py`, `frontend/src/api.ts`, `core/worker.py`, and the regression test files. The verifier was updated to report the new evidence.

## 24. Regression Tests Added

New coverage includes vault traversal and symlink rejection, atomic replace failure preservation, multipart field binding, upload size/type rejection, cached auto-save, save failure propagation, title sanitization, and forced epistemic state. Existing tests across document parsing, graph integrity, RAG bounds, provider contracts, scientific context, note evolution, and legacy worker behavior remain in the suite.

## 25. Runtime Verification

| Check | Result |
|---|---|
| `npm ci --ignore-scripts --no-audit --no-fund` | PASS |
| `python3 -m pip check` | PASS |
| `npm audit --omit=dev --audit-level=high` | PASS, 0 vulnerabilities |
| `npm run build` | PASS |
| `npm test` | PASS, 346 passed, 6 warnings |
| `python3 -m compileall -q api core literature tools main.py` | PASS |
| FastAPI `/api/health` | RUNTIME VERIFIED |
| React browser boot and demo Analyze action | RUNTIME VERIFIED |
| Browser console errors | None observed |

## 26. Before / After Results

| Check | Before | After |
|---|---|---|
| Full Python tests | 337 passed | 346 passed |
| Vault traversal | Reproduced escape | Blocked |
| Upload form fields | Ignored | Preserved |
| Upload size control | Unbounded read | 50 MiB streamed cap |
| Title frontmatter integrity | Reproducible injection | Sanitized and forced AI state |
| Cached auto-save | Skipped | Saved through common contract |
| Build | PASS | PASS |

## 27. Remaining Risks

Cross-store crash recovery, concurrent vault writers, live provider behavior, claim-level citation verification, and full rename/delete reconciliation remain material risks. The cognitive engines can still have their own side effects before final persistence; this is documented rather than hidden.

## 28. Unverified Areas

Live OpenAI-compatible/Anthropic/provider calls, real Zotero synchronization, real user vault mutation, vector store lifecycle, runtime agents, full mobile browser layout, and OS-specific Windows filesystem behavior are `NOT VERIFIED`.

## 29. Architecture Decisions

### Context

The project needed a runnable web frontend without making PyQt the active runtime, while preserving the existing research pipeline.

### Existing Behavior

The legacy worker owned orchestration and the new web path needed the same semantics.

### Problem

Duplicating orchestration would cause provider, security, graph, and persistence drift.

### Option A

Keep the desktop worker as the only implementation and wrap it with UI automation.

### Option B

Extract a Qt-free `AnalysisPipeline` and inject UI/runtime callbacks.

### Trade-offs

Option B keeps the domain flow reusable and testable, while the legacy PyQt code remains optional until fully retired.

### Decision

Use the shared Qt-free pipeline behind FastAPI and React; keep PyQt outside default dependencies.

### Reversibility

The pipeline callback boundary allows the legacy worker to remain a compatibility adapter while the web runtime evolves.

## 30. Recommended Next Steps

1. Add a deterministic three-paper golden dataset covering contradiction, synthesis, and hypothesis lineage.
2. Add a reconciliation command for Markdown, typed graph, memory, and cache drift.
3. Add provider-backed tests using recorded fixtures rather than live credentials.
4. Implement or explicitly remove the vector-store roadmap and add multilingual/formula retrieval benchmarks.
5. Move or delete the legacy PyQt UI only after compatibility coverage is intentionally retired.

## 31. Final Engineering Assessment

**FUNCTIONAL AND RUNTIME VERIFIED FOR THE LOCAL WEB PATH; RESEARCH INFRASTRUCTURE PARTIALLY VERIFIED.** The repository now has a repeatable React/FastAPI runtime, a passing integrated regression suite, explicit provenance boundaries, and fixed filesystem/upload integrity defects. It should not yet be described as a complete production-grade citation-verified research platform until the unverified areas above are implemented and tested.
