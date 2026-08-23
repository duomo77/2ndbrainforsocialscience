# System Audit and Refactoring Report

**Project:** Research Operating System (ROS) — AI-native Research Second Brain
**Audit Date:** 2026-08-23
**Audit Mode:** Three-persona independent audit (A: Clean Code & Architecture, B: Security & Reliability, C: Scientific Knowledge Infrastructure) + cross-review
**Evidence Discipline:** Every finding is labeled `Statically Verified` / `Runtime Verified` / `Inferred` / `Not Verified`. Nothing is presented as verified without evidence. Areas that could not be confirmed are marked `UNKNOWN`.

> **Status of this document:** COMPLETE. Phase 1 (discovery/mapping), Phase 2 (three independent persona audits), Phase 3 (cross-review with conflict resolution), and Phase 4 (this report + refactoring ledger + Phase 0–6 plan) are finished. Phase 5 evidence discipline applied: every P0/P1 claim was independently re-verified by the lead auditor (§23 verification log). **No code was modified during the audit itself.**
>
> **Implementation progress:** Phases 1–4 (Stabilize → Secure → Correct → Refactor) + Immediate Fixes #1–#7 executed and verified 2026-08-23: both P0s closed; security/consistency/correctness P1s closed; dead parallel stacks removed (~1,200 LOC), provider registry formalized (ADR Stage 1), wikilinks unified, legacy→typed graph migrator landed (C-02 Stage 1). Suite green (329 passed), flake8/black ratchets hold. Remaining P1s: C-02 Stages 2–3 (consumer rewiring), C-03 (entropy control), C-05 (provenance stamping), C-06 (qualitative routing), C-08 (contradiction re-entry). Deferred with rationale: F-08 adapter, F-12 decomposition (Phase 5/6). See ledger statuses.

**Progress Ledger**

| Stage | Status |
|---|---|
| Repository discovery & inventory | Completed |
| Architecture reconstruction | Completed |
| Dependency map | Completed |
| Database / persistence map | Completed |
| Security boundary identification | Completed |
| Data flow reconstruction | Completed |
| Persona A audit (Clean Code & Architecture) | Completed — 18 findings (5×P1) |
| Persona B audit (Security & Reliability) | Completed — 18 findings (5×P1) + store matrix + boundary verification |
| Persona C audit (Scientific Knowledge Infrastructure) | Completed — 17 findings (9×P1) + scorecard |
| Cross-review & final decisions | Completed — §5 |
| P0/P1 evidence re-verification | Completed — §23 verification log |

---

## 1. Executive Summary

ROS is a PyQt6 desktop application (~140 Python files, ~33,500 LOC) that transforms research inputs (papers, lecture transcripts, datasets, equations, notes, code) into Obsidian Markdown knowledge notes via LLM analysis, then accumulates persistent structure across five graph/state subsystems plus an EPIC 09 literature-expansion layer.

Three independent senior-level audits (architecture/clean code, security/reliability, scientific-infrastructure) converged on one meta-finding: **the intellectual architecture is real as data model and vocabulary, but the runtime wiring delivers roughly a third of it — and the two things that could destroy the user's trust irreversibly are both broken today.**

**P0 — must fix before any further feature work:**

1. **X-01 — Silent mass data loss.** Ten or more JSON knowledge stores (graph, concepts, lineage, contradictions, evolution, trust) are written non-atomically, and their loaders silently reset to empty on any parse error. An ordinary crash mid-write — or a single corrupt byte — is followed by the next save *cementing* total loss of that store's entire history, with no log, no backup, no user notification. The correct pattern already exists in this codebase (`config.py`, `core/utils/file_utils.atomic_write`) and is ignored by every one of these stores. *(Triple-detected, lead-verified.)*
2. **X-02 — The prompt-injection defense chain is non-functional on every live path.** The gate's block path crashes on a nonexistent attribute and the exception is swallowed ("ignored"), so blocked input is never blocked — empirically reproduced. Trust arithmetic cannot block even a single CRITICAL detection. The gate fails open on any internal error. And it only ever scans typed text: **all file content (PDF/CSV/code/transcript) bypasses it entirely**, then flows unvalidated into the LLM, five persistence layers, and a trust-0.9 retrieval feedback loop. *(Four independent defects, triple-detected, empirically reproduced.)*

**P1 highlights (12 consolidated):** retrieved RAG context is computed then *discarded* — the flagship cognition loop is open-circuited (C-01); five parallel graph stores with none read back as truth (C-02/F-05); no pruning/decay/dedup anywhere plus a template-heading pollution feedback loop (C-03); lineage duplicates roots per re-analysis with self-parent risk (C-04); no provenance on any LLM-produced artifact (C-05); the qualitative input path is mis-routed and scoring is quant-biased (C-06); contradictions are persisted but never influence future reasoning (C-08); LLM output is stored at peer-reviewed trust 0.90 and *gains* trust through repetition (C-09); LLM output mutates all stores without any validation boundary (B-04); SafeMode fallbacks are cached as authoritative and crash on `{}`-titles (B-05); the declared Python 3.9 platform cannot even import the application (F-03).

**What works:** the dependency direction is sound; `config.py` atomic persistence, the schema-versioned typed graph store, the circuit breaker, the Retry-After-aware literature transport, the EPIC 09 provenance machinery, and the document pipeline are genuinely well-built — **the refactoring templates already exist inside this codebase**. The path forward is migration and wiring, not rewrite.

**The plan (§18):** Phase 1 Stabilize (green suite, honest platform floor) → Phase 2 Secure (fail-closed gate, output boundary, secrets) → Phase 3 Correct (atomic persistence, loop closure, idempotency) → Phase 4 Refactor (collapse parallel stacks) → Phase 5 Optimize (budgets, entropy control) → Phase 6 Extend (contradiction re-entry, lineage classification, provenance stamping). Every phase: objective, files, risks, dependencies, tests, expected result. Full finding-by-finding ledger with statuses appended.

The system's purpose — *preserve stable human-AI scientific cognition across years of intellectual evolution* — is currently undermined most by what should be its strongest property: persistence. Fix X-01 and X-02 first; everything else builds on durable, trustworthy memory.

---

## 2. System Architecture Overview

*(Statically Verified from code reading; runtime behavior marked where exercised.)*

```
┌──────────────────────────────────────────────────────────────────────────┐
│ UI (PyQt6) — ui/main_window.py → AnalysisWorker (QThread)                 │
│   input_panel → metadata form; result_panel; vault_panel; settings_dialog │
└──────────────┬───────────────────────────────────────────────────────────┘
               │ (api_key, base_url, model, input_type, file_path, raw_text)
               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ core/worker.py :: AnalysisWorker._execute()  — THE live action chain      │
│                                                                           │
│  0  SecurityGate.validate_input(raw_text)      ← typed text ONLY          │
│  1  parsers._parse_input(file)                 ← PDF/CSV/TXT/code (UNSCANNED)
│  1.5 CacheEngine + IncrementalEngine check                                │
│  1.6 ResourceGovernor model downgrade                                     │
│  1.7 RagEngine.prepare_context() ← vault notes + concept registry         │
│  2  memory.get_concept_list() + obsidian_sync.scan_vault_concepts()       │
│  3  FaultRecoveryEngine.execute_with_recovery(LLM call, SafeMode fallback)│
│       └ ros_engine.analyze_paper/transcript/dataset/equation (OpenAI SDK) │
│  4  _run_cognitive_engines(): 5 engines append Markdown sections          │
│       A note_evolution  B contradiction  C idea_lineage                   │
│       D math_ontology   E research_tension (+graph_db)                    │
│  5  Graph updates (3 stores):                                             │
│       legacy: ros_engine.extract_graph_edges → memory.update_graph        │
│       typed:  knowledge_graph.ingest_markdown (~/.ros_memory)             │
│       integrity: graph_integrity transaction (kg_nodes/kg_edges)          │
│  6  MemoryTrust.store_memory; cache.put_analysis                          │
│  7  obsidian_sync.save_note_to_vault (atomic + .bak)                      │
└──────────────────────────────────────────────────────────────────────────┘

Secondary flows (library-level, not driven by the UI):
  core/pipeline/DocumentPipeline     — 7-stage import (validate→store)
  core/intel/DocumentIntelligenceManager — layout/section/table/equation extraction
  core/metadata engine               — provenance-first metadata extraction (pure fns)
  literature/ (EPIC 09)              — ScientificContextEngine: OpenAlex, Semantic
                                       Scholar, Crossref, PubMed, ArXiv, SSRN
```

**Entry points:** `main.py` (GUI), `run.sh`/`run.bat`, `build_exe.sh|bat` (packaging), `pytest` (tests). No HTTP server, no CLI command surface, no background daemons. Concurrency exists only inside `core/worker.py` (QThread) and `core/orchestration.py`.

---

## 3. Repository Structure

*(Statically Verified — measured 2026-08-23)*

| Path | Files | LOC | Role |
|---|---|---|---|
| `core/` (top level) | 38 | 12,788 | All backend: providers, engines, security, graphs, memory, worker |
| `core/pipeline/` | 11 | 2,466 | Document import pipeline (validator→storage) |
| `core/intel/` | 13 | 3,215 | Document Intelligence (EPIC 05): layout/section/table/figure/equation |
| `core/metadata/` | 5 | 1,396 | Metadata Engine (EPIC 06): provenance-first extraction |
| `core/utils/` | 8 | 814 | atomic_write, ensure_dir, hashing, text/path/validation helpers |
| `literature/` | 20 | 3,332 | EPIC 09: six academic providers + ScientificContextEngine (added 2026-08-19) |
| `ui/` | 11 | 5,527 | PyQt6 UI (main_window, input/result/vault panels, settings, dashboards) |
| `tests/` | 16 | 3,068 | pytest suite |
| `config/` | 1 | 210 | Layered AppConfig wrapper |
| `logs/` | 1 | 181 | 10-category structured logger |
| root | 5 | 489 | main.py, conftest.py, 3 legacy test files |
| `documents/` | — | — | Runtime data: 210 raw / 111 processed / 111 metadata files |
| `agents/ brain/ cache/ dashboard/ datasets/ embeddings/ experiments/ graphs/ plugins/ processed/ projects/ vectors/ writing/` | README only | — | Scaffolded future modules (FOUNDATION epic) |
| Root docs | 11 md | — | ARCHITECTURE, FOUNDATION, DOCUMENT_PIPELINE, REFACTOR (×3), UPDATES, VALIDATION_REPORT, CONTRIBUTING, README |

**Total:** 140 `.py` files, ~33,530 LOC.

---

## 4. Three-Persona Audit

Each persona received the identical Phase-1 fact sheet, worked independently from code evidence, and recorded findings in the mandated format. No persona saw the others' conclusions before the cross-review (§5).

### 4.1 Senior Software Engineer

**Audit scope:** architecture, clean code, typing, error contracts, testability across all packages; static reading + targeted greps + two empirical probes (suite baseline, security-gate block path). (Audit executed independently; read-only.)

**Bottom line:** macro dependency direction is sound (`ui → core`, no `core → ui`, `literature → core.contracts/metadata`), but the codebase accretes parallel stacks with every version wave (v3→v8 per file headers): three parsing stacks, two provider stacks, three logging systems, four graph stores, three error contracts. The live path is always the least-engineered one. ~2.5k LOC of verified-unreferenced "capability" misleads contributors about what the product actually has.

#### Ranked findings

| ID | Sev | One-liner | File |
|----|-----|-----------|------|
| F-01 | **P1** | Security-gate BLOCK path crashes on nonexistent attr `threats_detected`; `except` swallows it and processing continues — **blocked input is never blocked** (empirically reproduced) | `core/worker.py:110-117` |
| F-02 | **P1** | Gate validates only `raw_text`; parsed file content never scanned (converges with lead + B-02) | `core/worker.py:105-121` |
| F-03 | **P1** | CI/Pipfile pin Python 3.9 but 13+ core modules import `datetime.UTC` (3.11+) incl. `ros_logger` (module-level import of worker) — **app cannot import on the declared platform**; engine_loader converts this into silent feature loss | `.github/workflows/*.yml`, `core/ros_logger.py:25` |
| F-04 | **P1** | `memory.py` persistence: non-atomic writes + swallowed JSON corruption + full-file read-modify-write = silent total loss of legacy graph/concepts; concurrent workers race | `core/memory.py:56-160` |
| F-05 | **P1** | Four divergent graph stores written per analysis; legacy write failure swallowed with `except: pass` (converges with C-02) | `core/worker.py:239-246` |
| F-06 | P2 | `engine_loader` references nonexistent `core.embedding_gov` (2 getters always fail); docstring promises NullObject pattern but returns `None` | `core/engine_loader.py:115-125` |
| F-07 | P2 | Dual provider architecture: `BaseLLMProvider`/factory/manager/client stack is production-dead; live path is direct `openai.OpenAI` + URL sniffing; factory advertises openai/azure it cannot create; ABC signature violated | `core/provider_factory.py`, `core/ros_engine.py:20` |
| F-08 | P2 | Three parallel parsing stacks; PDF parsed twice per file (UI preview + worker); parser errors returned as analyzable content | `core/parsers.py`, `ui/main_window.py:528` |
| F-09 | P2 | Three incompatible error contracts: `Ok/Err` (literature only), dead `exceptions.py` hierarchy (never raised; latent `NameError: Path` at :160), ad-hoc tuples/strings everywhere | `core/contracts.py`, `core/exceptions.py` |
| F-10 | P2 | Dead-code inventory (~2.5k LOC): `state_manager.py`, `observability.py`, `QueueOrchestrator`, `ObsidianSafeWriter`, `graph_utils.py`, `analyze_notes/analyze_qualitative`, epistemic engine, worker wrapper shims | multiple |
| F-11 | P2 | `classify_error` substring matching confuses retryable/permanent ("500" matches "1500ms"); worker passes base_url as circuit-breaker key | `core/fault_recovery.py:48-70` |
| F-12 | P2 | `AnalysisWorker._execute` ~200-line god function; 19 `except Exception` (7 bare `pass`); Engine E re-runs Engine B/D scans; `is_fallback` flag never read | `core/worker.py:100-320` |
| F-13 | P2 | Worker lifecycle: no single-flight guard (QAction re-fires), `closeEvent` abandons running QThread, no `deleteLater`; cache-hit path skips all post-analysis steps | `ui/main_window.py:583-625, 861-864` |
| F-14 | P2 | `.bak_*.md` backups accumulate in vault, match `rglob("*.md")`, pollute `list_notes`/`scan_vault_concepts` → backup stems injected into LLM prompts (converges with B-09, C-03) | `core/obsidian_sync.py:176` |
| F-15 | P2 | Critical paths untested (`_execute`, gate-block, memory persistence, fault recovery); `test_v8` "regression" tests regex source text instead of behavior | `tests/` |
| F-16 | P3 | Two divergent topic classifiers; ≥4 divergent wikilink regexes | `core/obsidian_sync.py`, `core/classifier.py` |
| F-17 | P3 | CI lint decorative: no flake8/black config anywhere; 1,414 core lines >79 chars, 844 >88 | `.github/workflows/*.yml` |
| F-18 | P3 | Plaintext API key at default umask (converges with B-08, lead runtime evidence) | `core/config.py` |

#### P1 findings (full format)

### [P1] F-01 — Security gate block path crashes and is silently bypassed

**File:** `core/worker.py` **Component:** `AnalysisWorker._execute` step 0 **Detected By:** Persona A **Status:** Statically Verified — **empirically reproduced by Persona A; independently confirmed by lead auditor** (`ValidationResult` fields are `is_safe, trust_score, threat_level, threats, sanitized_content, audit_id` — no `threats_detected`)

**Problem:** When the gate returns `is_safe=False`, the worker executes `threats = "; ".join(result.threats_detected)` (`worker.py:111`) — a nonexistent attribute. The `AttributeError` is caught by the surrounding except, which emits "보안 검증 오류 (무시)" ("security validation error (**ignored**)") and falls through: the pipeline proceeds with the original, unsanitized content. Even the correct field would fail (`"; ".join(result.threats)` — ThreatReport is not str). `validate_input` itself exists only via an import-time monkey-patch (`security.py:486-490`).
**Why It Matters:** The entire v4.0 "zero-trust" gate is provably ineffective exactly when it should act: every blocked input sails through.
**Security Impact:** prompt-injection payloads (the module's stated raison d'être) are processed and persisted unimpeded. **Data Integrity Impact:** malicious content reaches vault, memory graph, all graph stores. **Architecture Impact:** demonstrates the cost of the `except Exception: pass` culture — a contract bug in a security-critical path survived because errors are never surfaced.
**Recommended Fix:** `threats = "; ".join(t.description for t in result.threats)`; emit `error_occurred` and `return`; remove the swallowing except; define `validate_input` in the class body (drop the monkey-patch).
**Regression Risk:** none expected — the block path currently never works. **Required Tests:** gate returns `is_safe=False` → worker emits `error_occurred` and does not proceed.
**Priority:** P1 (escalated to P0 in cross-review as part of the consolidated injection-defense failure — see §6)

### [P1] F-02 — File-derived content bypasses the security gate entirely

**File:** `core/worker.py` **Detected By:** Persona A **Status:** Statically Verified (triple convergence: lead auditor Phase 1, Persona B B-02)

**Problem:** Step 0 validates `self.raw_text or ""`; for file input `raw_text` is typically empty, so the gate scans nothing. `_parse_input()` then loads PDF/CSV/transcript/code content which is never scanned before the LLM and vault/graph writes. PDF metadata (`meta["title"]`, `meta["author"]`) additionally becomes note identity (graph node names, vault filenames).
**Recommended Fix:** Move/duplicate validation to after `_parse_input()` on `content` and `file_meta`; fail closed. Keep pre-parse check as defense-in-depth.
**Regression Risk:** legitimate academic phrases matching loose patterns may be altered — tighten patterns per source type. **Required Tests:** fixture file with injection payload → `error_occurred`, no `analysis_done`.
**Priority:** P1 (consolidated to P0 — see §6)

### [P1] F-03 — Declared runtime (Python 3.9) cannot import the application

**File:** `.github/workflows/*.yml`, `core/Pipfile`, 13+ core modules **Detected By:** Persona A **Status:** Statically Verified — **re-verified by lead auditor** (grep: 13 modules with `from datetime import ... UTC` incl. `ros_logger.py:25`, a module-level import of `worker.py`; CI pins `python-version: '3.9'`)

**Problem:** `datetime.UTC` requires Python 3.11. On the declared platform, `import core.worker` fails at import time (ros_logger is not behind the fault-isolated loader); engine-loader-guarded engines additionally degrade to silent `import_error`/`None`. Also `core/contracts.py:52` executes `Result = Ok | Err` at import time — PEP 604 class unions require 3.10 (this is an assignment, not an annotation, so `from __future__ import annotations` does not defer it). CI tests an interpreter the product cannot run on; "green CI" is structurally impossible for the shipped code.
**Recommended Fix:** Pin CI/Pipfile/`python_requires` to the real floor (3.11), or replace `UTC` with `timezone.utc`; add a startup version guard.
**Regression Risk:** low — ancient interpreters get an explicit error instead of a silently crippled app. **Required Tests:** CI matrix (3.11, 3.12) importing `core.worker` + running the suite.
**Priority:** P1

### [P1] F-04 — memory.py: non-atomic writes + swallowed corruption = silent data loss

**File:** `core/memory.py` **Detected By:** Persona A **Status:** Statically Verified (converges with B-01, C-07)

**Problem:** All four legacy stores (profile, concepts, questions, graph) are written with bare `Path.write_text(json.dumps(...))`; every loader wraps `json.loads` in `except Exception: pass` returning empty defaults. Crash mid-write → truncated JSON → next load silently `{}` → next `update_graph` overwrites with only the newest note → **total accumulated graph lost with zero signal**. `update_graph` does full-file read-modify-write, so concurrent workers (possible per F-13) last-write-wins each other. The correct pattern exists in the same codebase (`core/config.py:84-105`: mkstemp + fsync + `os.replace` + corrupt backup) and is unused here.
**Recommended Fix:** Extract config.py's atomic writer into `core/utils/`; on decode error, rename to `.corrupt-<ts>` instead of silent reset; guard `update_graph` with a process-wide lock.
**Regression Risk:** very low. **Required Tests:** truncated-JSON fixture preserves file; kill-mid-write simulation; concurrent `update_graph` loses no edges.
**Priority:** P1 (consolidated to P0 in §6)

### [P1] F-05 — Four graph stores written per analysis; legacy write failure invisible

**File:** `core/worker.py:239-246` **Detected By:** Persona A **Status:** Statically Verified (converges with C-02, B store matrix)

**Problem:** Each analysis persists graph data into four independent stores with different schemas (legacy JSON, graph_integrity GraphStore, tension KnowledgeGraphDB, typed semantic KG); none reads or reconciles the others. Store (1)'s entire block — including `extract_graph_edges` and `register_concepts` — sits in `try/except Exception: pass`, so graph-extraction failure is completely invisible.
**Recommended Fix:** Pick one canonical store (the typed `knowledge_graph.py` service), write a one-time migrator for legacy JSON, demote others to read-only projections or delete; replace the swallowed except with status + structured log.
**Regression Risk:** medium (UI panels read different stores). **Required Tests:** one analysis → exactly one persistence write per concern; migration test.
**Priority:** P1

#### Architecture Decision Record — dual provider stacks (F-07)

**Context:** Two provider systems coexist. (A) `BaseLLMProvider → ProviderFactory → ProviderManager → LLMClient`: referenced only by the legacy root test `test_chinese_providers.py`; `PROVIDERS` advertises `openai`/`azure` but `create_provider` raises for both; concrete signature violates the ABC. (B) Live path: `ros_engine._build_client` constructs `openai.OpenAI` directly; `_detect_provider` sniffs provider identity from URL substrings/model prefixes, falling back to `"openai"`.

**Option A — Consolidate on the direct-openai path.** Formalize `_detect_provider` into a `ProviderProfile` registry table (base_url hint, max_tokens, extra_body quirks); delete stack A.
**Option B — Migrate onto a provider Protocol.** One `LLMProvider` Protocol (chat/stream, validate, name) implemented over `openai.OpenAI`; route `ros_engine` + `ValidationWorker` through it; delete stack A.

**Trade-offs:** A ≈ small effort, zero behavior risk, keeps provider knowledge scattered. B ≈ larger, needs streaming-fallback tests, yields the seam for future capabilities (embeddings/audio — currently missing, which is why `parse_audio` stubs out).
**Decision (recommended):** **B, staged.** Stage 1 = extract ProviderProfile table + keep direct client + delete stack A (unreferenced outside legacy root tests, outside `testpaths`). Stage 2 = introduce Protocol, move `validate_api`/`_call_llm` behind it.
**Reasoning:** URL-sniffing fallback silently misconfigures unknown gateways; an explicit registry fails loudly; one seam also fixes F-11's `provider = base_url` breaker-key confusion. The codebase's own trajectory (`interfaces.py`, `contracts.py`, literature's registry with transport injection) shows this is the intended end-state.
**Future reversibility:** high — Protocol is structural; Stage 1 alone is fully reversible.

#### Dead-code inventory (verified unreferenced)

| Item | LOC | Note |
|---|---|---|
| `core/state_manager.py` | 247 | never imported; docstring contradicts its own singleton |
| `core/observability.py` | 396 | never imported — a third logging system (converges with lead §15 finding) |
| `core/orchestration.py::QueueOrchestrator` | ~110 | never used; would auto-start daemon threads if called |
| `core/security.py::ObsidianSafeWriter` | ~100 | defined, never referenced — **candidate for adoption**, not just deletion |
| `core/graph_utils.py` | — | zero references |
| `core/qualitative_engine.py` | 527 | reachable only via uncalled `get_epistemic_engine` |
| `core/exceptions.py` | 271 | never raised/caught; latent `NameError: Path` |
| `core/contracts.py` DTOs | ~90 | self-referential only (Ok/Err IS used by literature) |
| `ros_engine.analyze_notes/analyze_qualitative` | ~50 | never called (NOTES_PROMPT/QUALITATIVE_PROMPT dead) |
| `core/base_provider.py` + factory + manager + client | ~430 | legacy root tests only |
| worker `_get_*` shims for uncalled/phantom engines | 3 | indirection over dead paths |

**Positive observations (for balance):** `core/config.py` (atomic writes + corruption backups), `graph_integrity.GraphStore.save` and `fault_recovery._save_log` (tmp+replace), `literature/search/transport.py` (retry/backoff/Retry-After, injectable session), `literature/context/engine.py` (provenance-first, fault-isolated), and `knowledge_graph.py` (frozen DTOs, stable IDs, locked singleton) are genuinely well-built — **the refactoring templates already exist inside this codebase**.

### 4.2 Security and Reliability Engineer

**Audit scope:** threat model (B.1), AI security (B.2), store integrity (B.3/B.4), reliability (B.5), secrets (B.6), filesystem (B.7), failure observability (B.8). Full reads of worker, security, obsidian_sync, fault_recovery, parsers, memory, memory_trust, graph_integrity, knowledge_graph, ros_engine, config, perf_engine, orchestration, rag_engine, providers + grep sweeps. (Audit executed independently; read-only.)

**Bottom line:** the codebase contains genuine, competent primitives — atomic config writes with corrupt-file backups, a schema-versioned graph store, a real circuit breaker, a good HTTP transport with Retry-After, list-form subprocess discipline. The systemic failure is **integration**: these primitives sit beside a live chain that (1) applies the security gate to only one of six hostile input classes, (2) cannot block even what it detects, (3) treats LLM output as trusted structured data across five persistence layers, and (4) persists nearly everything through non-atomic writes whose corruption handlers silently erase history. **No RCE path was found**; the dominant risks are irreversible silent data loss and durable knowledge-base poisoning.

#### Ranked findings

| ID | Sev | One-liner | File |
|---|---|---|---|
| B-01 | **P1** | 10+ JSON stores written non-atomically; corrupted load silently resets to `{}` and the next save cements total loss; two-file stores can diverge | memory/note_evolution/contradiction/lineage/tension/math_ontology |
| B-02 | **P1** | Gate scans only typed `raw_text`; **all file content and file-derived metadata bypass it** | `core/worker.py:109 vs 122, 322-337` |
| B-03 | **P1** | TrustScorer arithmetic: single CRITICAL threat → 0.40 (+0.05 length bonus) > 0.30 threshold → **not blocked** | `core/security.py:245-249, 285, 322` |
| B-04 | **P1** | LLM output mutates graph/memory/vault with zero sanitization: wikilink nodes, verbatim vault writes, vault→prompt feedback loop with hard-coded trust 0.9 (retrieval poisoning) | worker/knowledge_graph/rag_engine |
| B-05 | **P1** | SafeMode fallback cached + marked "computed" like a real analysis → stale fallback served for the session; titles containing `{}`/`}` crash `str.format()` and kill the fallback path exactly when the API is down | `core/worker.py:217-293`, `core/fault_recovery.py:181-233` |
| B-06 | P2 | No cancellation, no explicit LLM timeout (SDK default 600 s), retry amplification (3×FaultRecovery × SDK retries) — worker can hang tens of minutes | ros_engine/worker |
| B-07 | P2 | Security layer fails open: gate exceptions ignored ("무시"); engine-load failure skips validation altogether | `core/worker.py:107-121` |
| B-08 | P2 | API keys plaintext in `config.json` **and** `providers.json`; zero `chmod` anywhere → default-umask secrets | config/provider_manager |
| B-09 | P2 | Vault write path: non-atomic `_INDEX.md` RMW, deterministic `.tmp` name, non-atomic fallback write, unbounded `.bak` re-ingested by scans | `core/obsidian_sync.py:166-221` |
| B-10 | P2 | No cross-process locking anywhere; two app instances race on every store (shared fixed tmp names → torn writes) | all singletons |
| B-11 | P2 | Re-analysis non-idempotent: lineage timestamp IDs, evolution version ×2/run, trust self-boost +0.05 per identical re-run | idea_lineage/note_evolution/memory_trust |
| B-12 | P2 | Unbounded LLM-output-driven growth: no output-side wikilink cap, every `?`-line → QUESTION node, headings/tags → permanent concepts; tx-buffer bypasses edge cap | knowledge_graph/ros_engine/graph_integrity |
| B-13 | P2 | `rag_context` computed but never passed to the LLM (dead grounding path with live cost); RAG hard-codes trust 0.9 (converges with C-01) | worker/rag_engine |
| B-14 | P2 | Parser DoS surface: whole-file reads before truncation (OOM), no column/cell caps, parser errors become content sent to the LLM | `core/parsers.py` |
| B-15 | P3 | Audit trail not tamper-evident: self-hash only, no chaining (converges with lead runtime evidence) | `core/security.py:124-135` |
| B-16 | P3 | Divergent corruption semantics: typed graph hard-fails permanently (no migration/repair) while others silently reset; no fsync on most tmp-replace writers | knowledge_graph vs memory |
| B-17 | P3 | Advertised reliability machinery dead: QueueOrchestrator zero callers; no client-side rate limiting | orchestration |
| B-18 | P3 | Full tracebacks in UI dialogs; parser error strings flow into LLM prompts and can be persisted | worker/parsers |

#### P1 findings (full format)

### [P1] B-01 — Silent total-loss pattern: non-atomic writes + error-swallowing loads

**File:** `core/memory.py`, `core/note_evolution.py`, `core/contradiction_engine.py`, `core/idea_lineage.py`, `core/research_tension.py`, `core/math_ontology.py` **Detected By:** Persona B **Status:** Statically Verified (converges with A-F-04, C-C-07; store matrix below)

**Problem:** Ten persistent JSON stores are written with direct `open("w") + json.dump` (no temp, no rename); loaders catch every exception and return empty structures. Crash/power loss mid-write → truncated file → next startup silently loads `{}` → next analysis **overwrites the corrupted file with fresh-but-nearly-empty data**, permanently destroying the store's entire history with no error anywhere. Two-file stores (`lineage_nodes`+`lineage_branches`, `kg_nodes`+`kg_edges`) can additionally diverge on crash between writes. `research_tension.KnowledgeGraphDB.add_node/add_edge` rewrites both kg files per single node/edge — dozens of full rewrites per analysis. The correct implementation exists in-repo (`core/utils/file_utils.py:17-45`, mkstemp+fsync+replace) and is used only by config/app_config/literature/pipeline-file_storage.
**Why It Matters:** the product's entire value proposition is durable research memory; this pattern converts a rare event into irreversible, unnoticed loss of graph, registry, lineage, contradictions, and evolution history.
**Security Impact:** silent loss of audit/integrity stores destroys forensic history. **Data Integrity Impact:** irreversible store-wide loss. **Architecture Impact:** every store reimplements persistence badly; the existing atomic utility is ignored.
**Recommended Fix:** route all store writes through `atomic_write`; on load failure quarantine the corrupt file (config.py's backup-then-default pattern) instead of silent reset; schema sentinel on load.
**Regression Risk:** low (write-path only). **Required Tests:** kill-mid-write per store (old file intact); corrupt-file load (backup + explicit degradation, not silent `{}`); two-file consistency.
**Priority:** P1 (escalated to P0 in cross-review — §6)

### [P1] B-02 — T2 boundary missing: file content never passes the security gate

**File:** `core/worker.py`, `core/parsers.py` **Detected By:** Persona B **Status:** Statically Verified (triple convergence)

**Problem:** Step 0 validates only `self.raw_text`. For file input the gate scans an empty string; `_parse_input()` output is never scanned. Attacker-controllable PDF metadata (`meta["title"]`, `meta["author"]`) becomes note identity — graph node names, memory sources, vault filenames (`worker.py:237` title fallback chain).
**Security Impact:** full bypass of the anti-injection layer for the most untrusted input class; enables B-04's graph/vault poisoning via documents.
**Recommended Fix:** validate parsed `content` AND `file_meta` fields before use; treat metadata as untrusted labels (length-limit + sanitize).
**Required Tests:** PDF with injection in body and `..//` in metadata title; CSV with injection in cells; assert gate verdict applies.
**Priority:** P1 (consolidated to P0 — §6)

### [P1] B-03 — Single CRITICAL threat is never blocked (trust arithmetic)

**File:** `core/security.py` **Detected By:** Persona B **Status:** Statically Verified — arithmetic re-derived (converges with lead Phase-1 observation; lead's Phase-1 §27 row 7 stands corrected in detail: 0.40 before length bonus, 0.45 after)

**Problem:** Penalties subtract from 1.0 (CRITICAL=0.60, `security.py:245-250`); block threshold 0.3 (`:285`); `is_blocked = trust_score < block_threshold` (`:322`). One CRITICAL → 0.40, plus +0.05 length bonus for >2000-char content (`:258-260`) → 0.45 → `is_safe=True`. Detection fires, audit records it, sanitizer redacts the literal pattern — but the input proceeds to the LLM and all persistence steps. Two CRITICALs are needed to block; paraphrased injections avoiding the exact regexes score 1.0.
**Why It Matters:** the gate's own taxonomy labels something CRITICAL yet the policy cannot block it. `[SANITIZED]` redaction of matched substrings gives false assurance.
**Recommended Fix:** block outright on any CRITICAL threat (or CRITICAL penalty ≥0.75 and remove the length bonus); decouple "detected CRITICAL" from the continuous score; add review/quarantine path for academic text quoting injection literature.
**Required Tests:** one CRITICAL pattern → `is_safe == False`; benign econometrics abstracts stay safe.
**Priority:** P1 (consolidated to P0 — §6)

### [P1] B-04 — Untrusted LLM output directly mutates graph, memory, and vault (T3/T4/T5 poisoning loop)

**File:** `core/worker.py`, `core/knowledge_graph.py`, `core/rag_engine.py`, `core/obsidian_sync.py` **Detected By:** Persona B **Status:** Statically Verified

**Problem:** The LLM's markdown is treated as trusted structured data: (1) every `[[link]]` becomes graph_integrity nodes (trust 0.7) + edges (confidence 0.8) (`worker.py:261-266`), and `SemanticMarkdownExtractor` additionally creates a node per wikilink and per `?`-ending line with no length cap (`knowledge_graph.py:300-360`); (2) `mem_trust.store_memory(content=enhanced[:1000])` stores LLM text at source-type trust up to 0.9; (3) `enhanced` is written verbatim to the vault — frontmatter/section injection possible; (4) feedback loop: next analysis injects registry+vault-derived `existing_nodes` into prompts, and RAG stamps every vault candidate trust 0.9 (`rag_engine.py:464`) — poisoned artifacts are re-retrieved at maximum trust. Input-side flood caps (`MAX_WIKILINKS_PER_NOTE=150`) are enforced **only on input text**, never on LLM output.
**Security Impact:** indirect prompt injection → durable knowledge-base compromise (no code execution, but attacker-shaped graph topology). **Data Integrity Impact:** unbounded junk/poison nodes. **Architecture Impact:** no trust boundary between model output and persistence.
**Recommended Fix:** scan LLM output with the gate before mutation; cap wikilinks/nodes per ingest; store LLM-derived memory as `llm_output` trust class; wrap retrieved vault content in explicit "untrusted context" delimiters; human confirmation for bulk new concepts.
**Required Tests:** hostile LLM output (500 wikilinks, frontmatter breakout, `?`-line flood) → caps enforced, no frontmatter duplication; re-run → no growth.
**Priority:** P1

### [P1] B-05 — SafeMode fallback cached as authoritative; `.format()` crash on curly-brace titles

**File:** `core/worker.py`, `core/fault_recovery.py` **Detected By:** Persona B **Status:** Statically Verified — mechanism re-confirmed by lead auditor (`SAFE_MODE_TEMPLATE.format(` at fault_recovery.py:226; template contains `{title}` interpolation)

**Problem:** (1) Fallback poisoning of cache: `execute_with_recovery` returns `(result, is_fallback)` but `is_fallback` is never consulted before steps 4-7 — the stub note is run through cognitive engines, saved to the vault, `cache.put_analysis(...)` and `incremental.mark_computed(...)`. Within the session, re-analysis hits `needs_recompute → False` and returns the cached **stub** instead of retrying the now-possibly-recovered API. (2) `SAFE_MODE_TEMPLATE.format(title=title, ...)` raises `KeyError`/`ValueError` for titles like `"{Market} Design"`; the fallback's own try/except then returns `(None, True)` and the worker reports "LLM이 빈 결과를 반환했습니다" — total failure precisely when the API is down.
**Recommended Fix:** never cache/mark-computed when `is_fallback`; tag cache entries with provider+prompt version; build the fallback note without `str.format` (escaped substitution).
**Required Tests:** forced API failure → next run with same content is a cache MISS; title `"{}"` + API failure → fallback note produced.
**Priority:** P1

#### Store Integrity Matrix (abridged — full matrix in Persona B audit)

Legend: Atomic ✓ (fsync) / ~ (tmp+replace, no fsync, or direct write where noted) / ✗ direct write.

| Store | Writer | Atomic | Schema-checked | Concurrent-safe | Crash/corruption story |
|---|---|---|---|---|---|
| `config.json` | config.py:80-93 | ✓ mkstemp+fsync+replace | lenient merge | RLock only | **Best in repo:** corrupt renamed `config.corrupt-<ts>.json` → defaults |
| `contradictions.json` / `evolution.json` / `math_ontology.json` / `tension_alerts.json` | engine `_save` | ✗ | ✗ | ✗ | Crash → truncated → silent `{}` → next save **cements total loss** |
| `kg_nodes.json` + `kg_edges.json` | research_tension (per node/edge!) | ✗ two-file non-transactional | ✗ | ✗ | Crash between writes → nodes/edges diverge; O(N²) rewrites per analysis |
| `lineage_nodes.json` + `lineage_branches.json` | idea_lineage | ✗ two-file | ✗ | ✗ | Same divergence/reset story |
| `memory_trust.json` | memory_trust:108-115 | ~ fixed tmp, no fsync | ✗ — one bad record aborts entire load (`MemoryRecord(**r)` in one try) | ✗ | Corruption → **all trust history lost silently** |
| `graph_store.json` + checkpoints | graph_integrity | ~ fixed tmp / ✗ | ✗ | ✗ | Corruption → error log + silent empty rebuild; checkpoints lost |
| `fault_log.json` / `incremental_state.json` | fault_recovery / perf_engine | ~ tmp+replace, no fsync | ✗ | ✗ | History dropped / full recompute (safe direction) |
| `knowledge_graph.json` (legacy) + concepts/profile/questions | memory.py | ✗ | ✗ | ✗ | **Entire accumulated graph lost** on truncated write + next update |
| `semantic_knowledge_graph.json` (typed) | knowledge_graph:182-194 | ~ `.<pid>.tmp`+replace, no fsync | ✓ schema_version — but mismatch **raises permanently**; no migration/quarantine | RLock in-process | Corruption → typed graph ingest dead until manual file deletion |
| `security_audit.jsonl` | security.py append | append-only, no fsync | self-hash, no chain | interleaving possible | Deletions/reorder undetectable (B-15) |
| `providers.json` | provider_manager:49-56 | ✗ | ✗ | ✗ | Contains **plaintext API keys** |
| Vault notes / `_INDEX.md` | obsidian_sync | ~ tmp+replace with direct-write fallback; deterministic tmp | n/a | ✗ index RMW | `.bak_<ts>` backups unbounded & re-ingested (B-09) |

#### Trust Boundary Verification (T1–T8)

| Boundary | Control present? | Effective? |
|---|---|---|
| T1 typed text → gate | ✓ `SecurityGate.validate_input` | **Partial** — regex-only; single CRITICAL not blocked (B-03); block path crashes (F-01); fails open (B-07) |
| T2 file content → system | ✗ none | **No** — hostile documents bypass every detector; file size unchecked (B-02, B-14) |
| T3 LLM output → mutations | ✗ none | **No** — persistent poisoning + unbounded growth via one model response (B-04, B-12) |
| T4 LLM output → vault | ✗ minimal (filename sanitization only) | **Partial for paths** (no traversal — `/`,`\` replaced), **none for content** (frontmatter injection possible) |
| T5 vault → prompt loop | partial controls, wrong placement | **No effective boundary** — live loop unsanitized; RAG trust constant 0.9; `.bak` duplicates amplify (B-04, B-13) |
| T6 external APIs | mixed | **Partial** — failures contained (breaker, finite retries), hangs not (B-06); literature transport best-implemented |
| T7 secrets | ✗ weak | **Not effective** — plaintext ×2 stores, zero chmod (B-08; lead runtime evidence: live key present, stores 0644) |
| T8 subprocess | ✓ list-form only, quoted URI | **Effective** — no shell=True/os.system/eval/exec/pickle/yaml.load anywhere; `yaml.safe_load` for frontmatter |

### 4.3 Scientific Knowledge Infrastructure Architect

**Audit scope:** every cognitive engine, graph store, RAG subsystem, prompt corpus, and design document, read in full; every public API claimed active by the docs cross-referenced against call sites. (Audit executed independently; read-only.)

**Bottom line:** The system *contains* the intellectual architecture as data structures and prompts, but the runtime pipeline is wired so that most of it is **write-only**: retrieved context is discarded before the LLM call (verified — see C-01), the typed graph is never read back, contradictions/lineage/tensions never re-enter any future prompt, and the most provenance-rich subsystem (document pipeline + EPIC 09 literature layer) is not connected to the desktop flow at all. Persistence is split across **five parallel graph stores in two home directories**, none of which is the source of truth for the next run — the vault + concept registry implicitly dominate.

#### Intellectual Architecture Scorecard

| Claimed capability | Verdict | One-line evidence |
|---|---|---|
| Multi-epistemic prompts | **Partial** | QUALITATIVE_PROMPT genuinely has reflexivity/positionality/trustworthiness structure, but is unreachable in production (C-06); epistemic default = quantitative; maturity/trust scoring quant-biased |
| Note evolution ladder | **Partial** | 6-stage ladder + durable `evolution.json`, but mechanical one-way promotion, version ×2 inflation per run, no content history, rename orphans history (C-11) |
| Lineage tracing (lit note → hypothesis) | **Partial** | Ancestry traversal works in principle; corrupted in practice by per-run duplicate ORIGIN nodes, `wikilinks[:3]` parents, self-parent risk, dead branch/merge APIs (C-04) |
| Contradiction as first-class entity | **Nominal-only** | Typed persisted edges exist; detection = intra-note keyword co-occurrence; target is a keyword string not a note; never re-enters later cognition (C-08, C-12) |
| Math ontology | **Partial** | Real builtin ontology with depends_on persisted; detection is regex over 13 fixed econ entries; dependency graph rendered as Mermaid text, not persisted as graph (C-12) |
| RAG budgeting / "cheapest cognition first" | **Nominal-only** | `TokenBudgetManager.allocate()` never called; retrieval = filesystem-order keyword scan, no embeddings; cached-abstraction keyspace unreachable; **retrieved context discarded** (C-01, C-13) |
| Provenance durability | **Partial (disconnected)** | EPIC 09 records real per-provider ProvenanceRecords — but only via `core/pipeline`, which the UI never invokes; live path records no model/prompt/version; `metadata/engine._provenance()` defined, never called (C-05) |
| Entropy control (pruning/decay/dedup) | **Missing** | No delete path in any store; decay never executed and mathematically broken; template headings registered as concepts → feedback pollution loop (C-03, C-10) |

#### Ranked findings

| ID | Sev | One-liner | File |
|----|-----|-----------|------|
| C-01 | **P1** | RAG context computed then **discarded — never reaches the LLM prompt**; flagship cognition loop open-circuited | `core/worker.py` |
| C-02 | **P1** | Five parallel graph stores, two directories; **none read as truth on next run**; typed graph write-only | memory/knowledge_graph/research_tension/graph_integrity |
| C-03 | **P1** | **No pruning/decay/dedup anywhere**; template headings registered as concepts → positive-feedback pollution; `.bak`/index entries accumulate unboundedly | memory/ros_engine/obsidian_sync |
| C-04 | **P1** | Lineage: **duplicate ORIGIN node per re-analysis**, self-parent risk from `[[title]]` footer, parents = first 3 wikilinks, 8/10 transformation types unreachable, branch/merge APIs dead | idea_lineage/worker |
| C-05 | **P1** | **No provenance on LLM outputs, edges, evolution/lineage records**; metadata engine's provenance helper defined but never called; EPIC 09 provenance disconnected from desktop path | metadata/engine, worker |
| C-06 | **P1** | UI "qualitative" input falls through to generic transcript prompt; `QUALITATIVE_PROMPT` + `qualitative_engine.py` **unreachable in production**; epistemic default = quantitative | worker/input_panel/ros_engine |
| C-07 | **P1** | History stores **silently wipe entire contents on any JSON parse error** (`except: → {}`), no backup, non-atomic writes | note_evolution/idea_lineage/contradiction_engine/memory_trust |
| C-08 | **P1** | Contradictions & tensions **write-only**: persisted but never re-injected into any later prompt/RAG | contradiction_engine/research_tension/worker |
| C-09 | **P1** | LLM-generated text stored as `source_type="paper"` (trust 0.90); repeat runs boost trust +0.05 toward 1.0 — **structurally rewards hallucination reinforcement**; trust layer never read back | worker/memory_trust |
| C-10 | P2 | Trust decay math wrong (compounds quadratically) + **never scheduled** — dormant today, corrosive if enabled | memory_trust |
| C-11 | P2 | Evolution ladder: promotion-only on mechanical metrics, version +2/run, no demotion, no content history, rename orphans record | note_evolution/worker |
| C-12 | P2 | Contradiction/tension detection = intra-note keyword co-occurrence, econometrics-only; methodological/empirical types never emitted | contradiction_engine/research_tension |
| C-13 | P2 | RAG: **no embeddings** (`core.embedding_gov` referenced but missing), hardcoded Econometrics L2 folders, non-recursive L3 glob, L4 = first ~60 walk-ordered files, 50% of ranking weights always zero, budget `allocate()` never called, cache keyspace disjoint | rag_engine/engine_loader |
| C-14 | P2 | **Context flooding**: unbounded concept registry ∪ vault wikilinks injected raw into every prompt — opposite of "no context flooding" | worker/ros_engine |
| C-15 | P2 | Legacy graph: `note_path` always `""`; note edges **replaced not merged** per re-run; detached from vault files | worker/memory |
| C-16 | P2 | Graph-integrity checkpoints store counts+hash only — **rollback impossible**; snapshots RAM-only; full-graph DFS validation on every commit | graph_integrity |
| C-17 | P3 | Classifier `JOURNAL_MAP` duplicate keys silently clobber (`jme`, `jae`, `jeg`, `apsr`); two inconsistent topic vocabularies | classifier/obsidian_sync |

#### P1 findings (full format)

### [P1] C-01 — RAG retrieval output is discarded; the core cognition loop is open-circuited

**File:** `core/worker.py` **Component:** `AnalysisWorker._execute` **Detected By:** Persona C **Status:** Statically Verified — **independently re-verified by lead auditor** (grep: exactly 3 `rag_context` hits: init :155, assignment :160, status-bar truthiness :182)

**Problem:** Step 1.7 computes `rag_context, rag_plan = rag.prepare_context(...)` but `rag_context` is never passed to `_run_analysis` or any prompt builder; no `ros_engine.analyze_*` accepts retrieved context. The LLM call receives only system prompt + task prompt + raw concept-name list.
**Why It Matters:** "Maximum cognition signal per token" is the central intellectual claim; as wired, every analysis is generated with amnesia plus a raw name list. Retrieval metrics are recorded for work that is then thrown away — the observability layer reports a healthy retrieval system that influences nothing.
**Security Impact:** none. **Data Integrity Impact:** all downstream graph/lineage outputs generated without memory context. **Architecture Impact:** RAGEngine/TokenBudgetManager/RetrievalRanker/RAGContextBuilder function as telemetry, not cognition.
**Recommended Fix:** Add a `{retrieved_context}` slot to the analysis prompts and pass `rag_context` through `_run_analysis`.
**Regression Risk:** low. **Required Tests:** stubbed `prepare_context` output appears verbatim in the message payload sent to `_call_llm`.
**Priority:** P1

### [P1] C-02 — No single source of truth: five parallel graph stores, none read back

**File:** `core/memory.py`, `core/knowledge_graph.py`, `core/research_tension.py`, `core/graph_integrity.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** Each run writes to (1) `~/.ros_memory/knowledge_graph.json` (legacy), (2) typed semantic graph (KnowledgeGraphService), (3) `~/.econometric_wiki/kg_nodes.json`+`kg_edges.json` (tension engine's KnowledgeGraphDB), (4) `graph_store.json` (graph integrity), (5) lineage/evolution/contradiction stores. The next run's context reads **none** of them — only `memory.get_concept_list()` (names) + `scan_vault_concepts(vault)`.
**Evidence:** `load_graph()` callers = UI stat labels only; `get_knowledge_graph_service()` callers outside tests = worker write path only.
**Why It Matters:** Deleting the typed graph loses nothing authoritative — the vault + registry implicitly dominate. Five write-only ledgers with divergent node identities (title-hash vs `_stable_id`) silently disagree.
**Recommended Fix:** Designate the typed semantic graph canonical; make step-2 context and all engines read from it; demote others to derived caches or delete.
**Regression Risk:** medium (UI stats depend on legacy shape). **Required Tests:** delete-and-rebuild equivalence; single-reader contract.
**Priority:** P1

### [P1] C-03 — Semantic entropy grows unboundedly; template-heading pollution loop

**File:** `core/memory.py`, `core/ros_engine.py`, `core/obsidian_sync.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** (a) `extract_graph_edges` registers **headings and tags as implicit concepts** — prompt templates emit identical boilerplate headings every run ("🚀 Extension Opportunities", "❓ Open Research Questions"), which become concepts, appear in next run's node list, get wikilinked by the LLM, and become new graph nodes: a **positive-feedback boilerplate pollution loop**. (b) No store has any delete/prune path; trust quarantine marks but never removes; decay never executes (C-10). (c) `.bak_<ts>` files persist forever; `_INDEX.md` accumulates duplicate entries per re-analysis.
**Why It Matters:** Over the system's explicit years-scale horizon, signal-to-noise degrades monotonically — the durable semantic memory becomes a growing archive of template artifacts.
**Recommended Fix:** Stop registering headings/tags as concepts; TTL/threshold pruning; `.bak` garbage collection; index dedup.
**Regression Risk:** low-medium. **Required Tests:** N re-analyses of one paper leave concept registry/graph node counts bounded.
**Priority:** P1

### [P1] C-04 — Lineage duplicates nodes per re-run, risks self-parentage, most type system dead

**File:** `core/idea_lineage.py`, `core/worker.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** `lineage_id = sha256(title|timestamp)` → every re-analysis creates a **new** ORIGIN node for the same note; `find_by_title` returns the first in dict order. Worker passes `parent_titles = wikilinks[:3]` without self-exclusion while PAPER_PROMPT's footer instructs the LLM to emit `[[{title}]]` → on re-runs a note can become **a child of its own earlier duplicate** (DAG cycle). Transformation type is hardcoded ORIGIN/FORMALIZATION — 8 of 10 types never assigned; `create_branch`/`get_abandoned_branches` have zero callers.
**Why It Matters:** "How did this idea evolve?" — the core question lineage exists to answer — cannot be answered reliably: duplicate roots, order-dependent parents, self-edges, frozen transformation vocabulary. Parents from the first three wikilinks mistake LLM link order for intellectual descent.
**Recommended Fix:** Upsert by title (stable ID); exclude self-links; derive transform type from content diff; wire or remove branch/merge APIs.
**Regression Risk:** low. **Required Tests:** re-analysis idempotency; self-parent rejection.
**Priority:** P1

### [P1] C-05 — Provenance gap across all LLM-produced artifacts

**File:** `core/worker.py`, `core/metadata/engine.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** Saved notes get evolution frontmatter but no `model`/`prompt_version`/timestamp; `log_session` records title/type/path only; graph edges carry at best an input file path. `metadata/engine.py::_provenance()` is defined but **never called**; `BibliographicMetadata.to_dict(include_provenance=True)` emits an empty `_provenance: {}`. EPIC 09's correct provenance implementation is reachable only through `core/pipeline`, which no UI code imports.
**Why It Matters:** After a model swap, no analysis can be replayed, audited, or attributed. Future synthesis notes blend generations of LLM output with different hallucination profiles as if homogeneous — an epistemic integrity failure for a years-scale system. (Converges with lead-auditor §15 observability finding.)
**Recommended Fix:** Stamp `{model, provider, prompt_hash, temperature, ts}` into frontmatter on every analysis; attach `ProvenanceRecord` in `run_extraction`; wire EPIC 09 into the worker or expose the pipeline in the UI.
**Regression Risk:** low. **Required Tests:** provenance fields present in saved note + edges.
**Priority:** P1

### [P1] C-06 — Multi-epistemic routing broken: qualitative input never reaches the qualitative prompt

**File:** `core/worker.py`, `ui/input_panel.py`, `core/ros_engine.py` **Detected By:** Persona C **Status:** Statically Verified — converges with lead-auditor action-chain finding; **severity upgraded P2→P1** (UI tab sends `input_type="qualitative"`, worker's elif chain has no such branch → else → `analyze_transcript` as "notes")

**Problem:** `input_panel.py:850` sends `input_type="qualitative"`; `_run_analysis` branches paper/transcript-family/dataset/equation/else — qualitative material is processed by the generic transcript prompt. `analyze_qualitative` and `core/qualitative_engine.py` (528 lines: EpistemicMode, TheoreticalFramework, EpistemicTension) have zero production callers; `_detect_epistemic_mode` defaults to "quantitative" and only runs on the paper path. Compounding quant bias: MaturityScorer credits only econometric method names; MemoryTrustScorer gives a math bonus — qualitative notes are structurally scored less mature and less trustworthy.
**Why It Matters:** The anti-econometric-reductionism promise is implemented as dead code; interpretivist/critical material gets a transcript template and permanently wrong YAML/type/stage treatment.
**Recommended Fix:** Route `qualitative` input type to `analyze_qualitative`; make maturity/trust scoring epistemic-mode-aware.
**Regression Risk:** low. **Required Tests:** routing per input_type; parity test — a qualitative note can reach `permanent_note` maturity.
**Priority:** P1

### [P1] C-07 — History stores silently self-erase on any JSON parse error

**File:** `core/note_evolution.py`, `core/idea_lineage.py`, `core/contradiction_engine.py`, `core/memory_trust.py` **Detected By:** Persona C **Status:** Statically Verified — **re-verified by lead auditor** in note_evolution.py:143, idea_lineage.py:113, contradiction_engine.py:166 (memory_trust.py load pattern verified by Persona C, flagged for Phase-5 re-check)

**Problem:** Whole-file `try: json.load(...) except Exception: self._records = {}`. One malformed record, schema drift, or partial write → **the entire evolution/lineage/contradiction/trust history is silently discarded** — no backup, usually no log. Writes are non-atomic in these stores (plain `open(w)`+`json.dump`), so an interrupted write produces the corrupt file that triggers the next total wipe. `memory_trust`/`knowledge_graph` do tmp+replace correctly — the codebase knows the pattern; the cognitive-history stores don't use it.
**Why It Matters:** The most likely actual mechanism for "years of intellectual evolution" disappearing overnight — precisely the failure mode the system philosophy exists to prevent. Borderline P0 given irreversibility.
**Recommended Fix:** tmp+rename atomic writes everywhere; per-record tolerant loading (skip bad record, log); periodic versioned backups of history JSON.
**Regression Risk:** low. **Required Tests:** corrupt-one-record survival; kill-during-write.
**Priority:** P1

### [P1] C-08 — Contradictions and tensions never re-enter cognition

**File:** `core/contradiction_engine.py`, `core/research_tension.py`, `core/worker.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** Contradictions persist to `contradictions.json`, tensions to `tension_alerts.json`/`kg_*`, but nothing reads them back: no prompt includes unresolved contradictions; RAG's `RANKING_WEIGHTS` reserve `contradiction_import=0.15` + `tension_relevance=0.15` but the retriever never populates those fields; `apply_contradiction_penalty` has no production caller; `format_contradiction_report` runs only for the same note in the same run; `generate_global_tension_report` has no callers.
**Why It Matters:** A first-class research entity must *participate in future reasoning*. Today the system can detect a SUTVA violation in note A on Monday and help build a conflicting ATE generalization in note B on Tuesday with zero friction — the contradiction exists in a drawer.
**Recommended Fix:** Inject token-budgeted `get_unresolved()` summaries into prompts; populate `contradiction_import` during retrieval.
**Regression Risk:** low. **Required Tests:** unresolved contradiction for concept X appears in the next prompt mentioning X.
**Priority:** P1

### [P1] C-09 — Trust layer mislabels LLM output as peer-reviewed source and rewards repetition

**File:** `core/worker.py`, `core/memory_trust.py` **Detected By:** Persona C **Status:** Statically Verified

**Problem:** Worker stores `enhanced[:1000]` — **LLM-generated markdown** — with `source_type=self.input_type`; for paper input, `SOURCE_BASE_SCORES["paper"]=0.90` applies, so synthetic text receives peer-reviewed trust. The engine defines `llm_output: 0.45` — evidence the designers knew the distinction — but the worker never uses it. `memory_id = sha256(source + content[:100])` means re-analysis hits the existing record and applies `RETRIEVAL_BOOST +0.05` per run toward 1.0: **repetition inflates trust** — the exact hallucination-reinforcement loop the module docstring vows to prevent. `retrieve`/`format_context_injection` have zero callers — the trust layer is write-only.
**Security Impact:** memory-poisoning surface: adversarial input text → high-trust "paper" memories.
**Recommended Fix:** Store with `source_type="llm_output"` (or composite linking input source + model); remove or gate `RETRIEVAL_BOOST`.
**Regression Risk:** low. **Required Tests:** stored records for analyses carry `llm_output` provenance.
**Priority:** P1

#### P2/P3 findings (condensed)

- **C-10 [P2]** `memory_trust.py` — decay multiplies the *current* score by the full since-creation factor (compounds quadratically: 0.9 → 0.45 → 0.22 → quarantine in three cycles); `run_decay_cycle` ignores the `decay_applied` guard; never called. Dormant today, corrosive if enabled. Fix: decay from stored initial or incremental windows.
- **C-11 [P2]** `note_evolution.py` — `concept_count ≡ wikilink count`; one-way promotion; worker calls `register_note` twice per run (badge + `inject_evolution_frontmatter`) → version +2/run; content history = MD5 only; `note_id=sha256(title)` → rename orphans history; `merge_notes` never called.
- **C-12 [P2]** contradiction/tension/math detection is intra-note keyword co-occurrence; `target_note` is a literal keyword string, not a note (no cross-note edges ever); `METHODOLOGICAL`/`EMPIRICAL` enum members never emitted; no ideological/institutional/epistemic types; 7 econ-only tension patterns; a qualitative/humanities corpus generates zero detections.
- **C-13 [P2]** `rag_engine.py` — no embeddings anywhere (`core.embedding_gov` module missing — matches the pre-existing test collection error); L2 folders hardcoded Econometrics/ML/Statistics; L3 non-recursive glob; L4 = first ~60 files in `os.walk` order; trust constant 0.9; 50% of ranking weights always zero; `TokenBudgetManager.allocate()` never called; CACHED_ABSTRACTION key (md5(query+model)) disjoint from worker cache key (sha256(content)[:16]) → structurally unreachable.
- **C-14 [P2]** unbounded `existing_nodes` (registry ∪ vault wikilinks) rendered raw into every prompt — O(vault size) prompt growth; feeds C-03's pollution loop.
- **C-15 [P2]** legacy graph `note_path` always `""`; `update_graph` replaces edge sets wholesale per run (silent edge loss); backlinks never removed.
- **C-16 [P2]** graph-integrity checkpoints hold counts+hash only (no content) → rollback impossible; snapshots RAM-only (20 max); full O(V+E) DFS validation every commit, trending toward the 50k-node cap.
- **C-17 [P3]** `classifier.py` JOURNAL_MAP duplicate keys clobber (`jme`→Microeconomics misroutes *Journal of Monetary Economics*; `jae`, `jeg`, `apsr` similar); several mapped disciplines absent from DISCIPLINE_MAP → Uncategorized; obsidian_sync uses a second topic vocabulary.

**Top-3 leverage (Persona C):** (1) close the loop — inject retrieved/contradiction/memory context into analysis prompts (C-01/C-08); (2) designate one canonical graph store and read from it (C-02); (3) stamp provenance + fix store durability (C-05/C-07). Everything else is optimization on top of a loop that is currently open.

---

## 5. Cross-Review

Three independent audits + lead-auditor Phase-1 findings. Convergences (independent detections of the same defect) carry the highest confidence; conflicts were resolved by severity of *consequence*, with rationale recorded.

### 5.1 Convergent findings (multiple independent detectors)

| Consolidated issue | Detected by | Personas' severities | Final severity | Resolution |
|---|---|---|---|---|
| **Cognition loop open-circuited: retrieved context never reaches the LLM** | C-01, B-13, lead §16 | P1 / P2 | **P1** | Conflict resolved for P1: this is not a reliability concern but the *absence of the core claimed capability*; every downstream artifact is generated with amnesia. B's P2 rating addressed only the dead-cost angle |
| **Non-atomic store writes + silent self-erasure on corruption** | B-01, A-F-04, C-07, lead Phase-1 | P1 ×3 | **P0** | Escalated: the severity charter defines P0 as "may cause data loss"; this pattern *irreversibly and silently* destroys the system's primary asset (accumulated research memory) on an ordinary crash or one corrupt byte. All three personas independently identified it; the fix template already exists in-repo (`config.py`, `file_utils.atomic_write`) |
| **No functioning prompt-injection defense on any live path** | A-F-01 (block path crashes, empirically reproduced), B-03 (CRITICAL arithmetic), B-07 (fail-open), B-02/A-F-02/lead (T2 file-content bypass) | P1 ×4 | **P0** | Escalated as a *system-level* finding: every component of the only defense layer is independently broken — the gate cannot block even detected CRITICAL injections, crashes on its own block path, fails open on exceptions, and never sees file content. The charter's P0 "security breach" criterion is met at the potential level; no RCE exists, but durable knowledge-base compromise is unimpeded |
| **File content bypasses the gate** | lead Phase-1, A-F-02, B-02 | P1 ×3 | merged into P0 above | — |
| **Five graph stores, none read back as truth** | C-02, A-F-05, lead Phase-1, B matrix | P1 ×3 | **P1** | Unanimous. Canonical-store decision in §21 |
| **LLM output treated as trusted → poisoning + unbounded growth** | B-04, B-12, C-03, C-09 | P1/P2 | **P1** | Consolidated as "T3/T5 boundary missing"; C-09 trust mislabeling kept as a standalone P1 (epistemic consequence distinct from security) |
| **Provenance gap (model/prompt/version unrecorded)** | C-05, lead §15 | P1 + P2 | **P1** | Convergent; observability finding subsumed here |
| **Plaintext secrets, no permission hardening** | B-08, A-F-18, lead runtime evidence | P2 ×3 | **P2** | Local-desktop context acknowledged; still actionable (chmod + keychain path) |
| **`.bak` proliferation pollutes scans/prompts** | B-09, A-F-14, C-03(c) | P2 ×3 | **P2** | — |
| **Idempotency failures on re-analysis** | B-11, C-04, C-11 | P2/P1/P2 | **P1 for lineage (C-04: DAG corruption), P2 for evolution/trust** | — |
| **Audit JSONL not tamper-evident** | B-15, lead runtime evidence | P3 ×2 | **P3** | — |
| **Phantom `core.embedding_gov` module** | F-06, C-13, lead §17 (collection error) | P2 ×3 | **P2** | — |

### 5.2 Conflicting opinions and resolutions

| Issue | Conflict | Resolution & reasoning |
|---|---|---|
| Severity of discarded RAG context | B: P2 (dead cost) vs C: P1 (core capability absent) | **P1.** B evaluated the reliability impact of a dead path; C evaluated the product's central intellectual claim. The capability question dominates for this system's purpose |
| Store-wipe severity | All three: P1 (C noted "borderline P0") | **P0.** Applied the charter's P0 definition strictly: irreversible data loss of the primary asset, silent, triggered by ordinary events (crash, partial write, one malformed record) |
| Security gate cluster | Personas rated components P1 individually | **P0 consolidated.** Individual components at P1, but their *conjunction* means zero working injection defense exists on any live input path — a system-level security failure, not four bugs |
| `analyze_qualitative` unreachable | Lead: P2 (action-chain) vs C-06: P1 (epistemic promise + quant-biased scoring) | **P1.** C's evidence (UI tab actively mis-routes; maturity/trust scoring structurally quant-biased) shows user-visible epistemic harm, not just dead code |
| Python version floor | A: P1; B/C silent | **P1 confirmed.** No conflict; lead re-verification (13 modules incl. worker's module-level imports) makes it certain. CI integrity is part of "would an engineer understand this in 3 years" |

### 5.3 Audit-quality notes

- Persona A's F-01 was empirically reproduced (gate call + attribute access probe) — the strongest single piece of evidence in the audit.
- Lead auditor re-verified every persona P1 by independent grep/read before inclusion (verification log in §23 addendum).
- All personas noted the same structural meta-pattern independently: **each version wave (v3→v8) added a parallel layer instead of migrating the live path** — the live path is consistently the least-engineered stack. This is the root cause behind most findings and is addressed in §21.
- Pre-existing test failures (8) + collection error (1) were verified against the untouched baseline by both lead auditor and Persona A; excluded from new findings but listed as Phase-1 stabilize work.

---

## 6. Critical Findings (P0)

### [P0] X-01 — Silent, irreversible mass data loss: non-atomic store writes + error-swallowing loaders

**Files:** `core/memory.py`, `core/note_evolution.py`, `core/idea_lineage.py`, `core/contradiction_engine.py`, `core/research_tension.py`, `core/math_ontology.py`, `core/memory_trust.py` (load path) **Components:** all legacy + cognitive-history store save/load pairs **Detected By:** Persona B (B-01), Persona A (F-04), Persona C (C-07), lead auditor **Status:** Statically Verified (triple convergence; every cited line checked by ≥2 auditors)

**Problem:** ≥10 persistent JSON stores are written with direct `open("w")`/`write_text` (no temp file, no rename, mostly no fsync). Every loader wraps parsing in `except Exception: → {}` at whole-file level. The failure chain: crash/power loss mid-write (or a single corrupt byte from any cause) → truncated/invalid JSON → next load silently returns empty → **the next save overwrites the corrupted file with fresh-but-nearly-empty data, permanently destroying the entire history of that store with no log, no backup, no user notification.** Two-file stores (`lineage_*`, `kg_*`) can additionally diverge when a crash lands between the two writes. `research_tension` rewrites both kg files per node/edge — dozens of exposure windows per analysis. Worker lifecycle defects (F-13: no single-flight guard, `closeEvent` abandons running threads) supply the concurrent/crash triggers in production.
**Evidence:** full store matrix in §4.2; representative: `memory.py:131-133` (`GRAPH_FILE.write_text`), `:126-133` (swallowing load), `note_evolution.py:143-149`, `idea_lineage.py:113-120`, `contradiction_engine.py:166-172`, `math_ontology.py:237-248`, `research_tension.py:193-198`. The correct pattern exists in-repo and is ignored by all of these: `core/utils/file_utils.py:17-45` (mkstemp + fsync + `os.replace`) and `core/config.py:64-105` (atomic write + corrupt-file quarantine).
**Why It Matters:** the system's entire purpose is preserving years of intellectual evolution. This is the single most likely mechanism for that evolution disappearing overnight — silently, irreversibly, while the UI reports success. Runtime evidence on this machine: several engine stores frozen since 2026-06-01 — consistent with either inactivity or a wipe-and-reseed event (INFERRED).
**Security Impact:** loss of audit/integrity stores destroys forensic history. **Data Integrity Impact:** total, silent, unrecoverable. **Architecture Impact:** every store reimplements persistence badly.
**Recommended Fix (immediate):** (1) route every store write through `core.utils.file_utils.atomic_write`; (2) replace swallowing loaders with per-record tolerant parsing + corrupt-file quarantine (rename to `.corrupt-<ts>` + user-visible warning), modeled on `config.py`; (3) add a schema sentinel field to each store; (4) periodic versioned backups of history JSON (`.bak-<date>` outside scan paths).
**Regression Risk:** low — write-path only; happy-path semantics unchanged. **Required Tests:** kill-mid-write simulation per store (old file intact); corrupt-one-record survival; corrupt-file quarantine emits warning; two-file store consistency.
**Priority:** P0

### [P0] X-02 — The prompt-injection defense chain is non-functional on every live input path

**Files:** `core/worker.py`, `core/security.py`, `core/parsers.py` **Components:** `AnalysisWorker._execute` step 0, `SecurityGate.validate`, `TrustScorer.score` **Detected By:** Persona A (F-01, empirically reproduced), Persona B (B-02, B-03, B-07), lead auditor (Phase-1 T2) **Status:** Statically Verified + Runtime probe (Persona A reproduced the gate bypass)

**Problem:** Four independent failures combine into one system-level hole:
1. **Block path crashes** (F-01): on `is_safe=False` the worker reads nonexistent `result.threats_detected` (`worker.py:111`); the AttributeError is swallowed ("보안 검증 오류 (무시)") and **processing continues with the original unsanitized content**. Even with the correct attribute, `"; ".join(result.threats)` would raise TypeError. The gate has *never* blocked anything.
2. **Trust arithmetic cannot block a single CRITICAL** (B-03): 1.0 − 0.60 = 0.40, +0.05 length bonus = 0.45 > 0.30 threshold → `is_safe=True`.
3. **Fail-open** (B-07): any gate exception or engine-load failure skips validation entirely and continues.
4. **Wrong seam** (B-02/F-02): the gate validates only typed `raw_text`; parsed **file content (PDF/CSV/code/transcript) — the most untrusted input class — never passes it**, and attacker-controllable PDF metadata becomes note/graph/vault identity.
Downstream, B-04 guarantees persistence: unscanned content → LLM → unvalidated graph/memory/vault mutations → trust-0.9 re-retrieval into future prompts (durable poisoning loop).
**Evidence:** `worker.py:104-121` (all four defects in 17 lines); `security.py:245-260, 285, 322`; `ValidationResult` dataclass fields (no `threats_detected`); Persona A empirical probe: injection string → `is_safe=False, trust=0.0` → attribute access raises.
**Why It Matters:** a "zero-trust AI security layer" (module's own header) whose every enforcement mechanism is broken is worse than none: the audit log and `[SANITIZED]` redactions create false assurance while payloads reach the LLM and all five persistence layers.
**Security Impact:** durable knowledge-base compromise via any document the researcher opens; memory-poisoning amplified by C-09's trust mislabeling. **Data Integrity Impact:** poisoned nodes/notes persist and re-enter cognition. **Architecture Impact:** security control positioned pre-parse instead of at the content-finalization boundary.
**Recommended Fix (immediate, fail-closed):** (1) fix the block path (`t.description for t in result.threats`; emit `error_occurred`; return); (2) block outright on any CRITICAL threat regardless of score; (3) move/duplicate validation to after `_parse_input()` covering `content` + `file_meta`; (4) gate exceptions → block with explicit override option, never continue; (5) define `validate_input` in the class body (drop the monkey-patch).
**Regression Risk:** more false positives on academic text quoting injection literature — add a quarantine/review path instead of hard block for MEDIUM. **Required Tests:** one CRITICAL → blocked; gate exception → blocked; malicious PDF fixture → blocked; benign corpus stays safe.
**Priority:** P0

---

## 7. Security Findings (consolidated index)

| ID | Sev | Summary | Status |
|---|---|---|---|
| X-02 | **P0** | Injection defense chain non-functional (F-01+B-02+B-03+B-07 consolidated) | Statically Verified + reproduced |
| B-04 | P1 | LLM output → graph/memory/vault without any validation boundary; trust-0.9 feedback loop | Statically Verified |
| C-09 | P1 | LLM text stored as `paper` trust 0.90; repetition boosts trust (hallucination reinforcement) | Statically Verified |
| B-08 | P2 | Plaintext API keys in two stores; zero permission enforcement (runtime: live key present, stores 0644) | Runtime Verified |
| B-12 | P2 | Output-side flood caps absent; tx-buffer bypasses edge cap | Statically Verified |
| B-14 | P2 | Parser DoS surface (whole-file reads, no cell/column caps, errors-as-content) | Statically Verified |
| B-06 | P2 | Hang-as-DoS: no explicit LLM timeout (SDK 600 s), no cancellation | Statically Verified (SDK default Inferred) |
| B-15 | P3 | Audit JSONL self-hash only; deletions undetectable (runtime: 47 events, no prev_hash) | Runtime Verified |
| B-18 | P3 | Tracebacks in UI dialogs; exception strings into prompts/vault | Statically Verified |
| T8 | — | Subprocess surface verified clean (list-form args, quoted obsidian:// URI, no shell) | Statically Verified |

---

## 8. Database Integrity Findings

*(Full persona findings: §4.2 store matrix + B-series. Lead-auditor findings recorded here.)*

### [P2] Vault note deletion does not synchronize any state store

**File:** `ui/vault_panel.py` **Component:** `VaultPanel._show_context_menu` (delete branch) **Detected By:** Lead auditor (action-chain trace) **Status:** Statically Verified

**Problem:** Deleting a note executes `os.remove(path)` after a confirmation dialog and a tree refresh — nothing else. The typed knowledge graph (`~/.ros_memory/knowledge_graph.json`), legacy concept registry, graph-integrity store, lineage/evolution records, and the MOC index all keep referencing the deleted note. There is no snapshot/backup before removal (unlike the write path, which keeps `.bak`).
**Evidence:** `vault_panel.py:255-268` — delete branch: `os.remove(path); self.refresh()`. Paths originate from directory scans of the configured vault (no traversal exposure — verified), but removal is irreversible and unsynchronized.
**Why It Matters:** Persistent cross-store divergence: wikilinks and graph edges point at notes that no longer exist; RAG retrieval can never surface them again while graphs claim they exist — silent semantic rot of exactly the kind the system's philosophy forbids.
**Security Impact:** none (paths are scan-derived). **Data Integrity Impact:** orphan records in ≥5 stores; no recovery path. **Architecture Impact:** confirms absence of any delete/tombstone protocol across stores.
**Recommended Fix:** Route deletion through a single `delete_note()` service: snapshot file to `.ros_snapshots` (ObsidianSafeWriter already exists), mark graph nodes as tombstoned rather than deleting edges, update index; or minimum viable — snapshot + warning about dangling links.
**Regression Risk:** low. **Required Tests:** delete → snapshot exists; graph query reports tombstone; index rebuilt without entry.
**Priority:** P2

### Persistence Map (Phase 1)

There is **no SQL database** (`sqlite3`/`sqlalchemy` grep: zero matches; Statically Verified). Persistence inventory:

### Store Map

| Store | Location | Writer(s) | Format | Atomicity |
|---|---|---|---|---|
| Legacy concept graph | `~/.ros_memory/knowledge_graph.json` *(name to verify against memory.py — INFERRED)* | `memory.update_graph` | JSON | Not Verified |
| Concept registry | `~/.ros_memory/concept_registry.json` | `memory.register_concepts` | JSON | Not Verified |
| Typed semantic graph | `~/.ros_memory/knowledge_graph.json` (KnowledgeGraphStore) | `core/knowledge_graph.py` | JSON, `schema_version: 1` | tmp+replace (Statically Verified) |
| Graph integrity store | `~/.econometric_wiki/kg_nodes.json`, `kg_edges.json`, `graph_store.json` | `core/graph_integrity.py` | JSON | Not Verified |
| Note evolution | `~/.econometric_wiki/evolution.json` | `core/note_evolution.py` | JSON | Not Verified |
| Contradictions | `~/.econometric_wiki/contradictions.json` | `core/contradiction_engine.py` | JSON | Not Verified |
| Idea lineage | `~/.econometric_wiki/lineage_nodes.json`, `lineage_branches.json` | `core/idea_lineage.py` | JSON | Not Verified |
| Math ontology | `~/.econometric_wiki/math_ontology.json` | `core/math_ontology.py` | JSON | Not Verified |
| Memory trust | `~/.econometric_wiki/memory_trust.json` | `core/memory_trust.py` | JSON | Not Verified |
| Tension alerts | `~/.econometric_wiki/tension_alerts.json` | `core/research_tension.py` | JSON | Not Verified |
| Fault log | `~/.econometric_wiki/fault_log.json` | `core/fault_recovery.py` | JSON | Not Verified |
| Security audit | `~/.econometric_wiki/security_audit.jsonl` | `core/security.py` AuditTrail | JSONL append | append-only, non-chained hashes |
| Incremental state | `~/.econometric_wiki/incremental_state.json` | perf/incremental engine | JSON | Not Verified |
| App config | `~/.econometric_wiki/config.json` | `core/config.py` | JSON | atomic + corrupt backup (Statically Verified) |
| Provider profiles | `~/.ros_config/providers.json` | `core/provider_manager.py` | JSON | Not Verified |
| Document pipeline | `documents/{raw,processed,metadata,cache,temporary}/` | `core/pipeline/file_storage.py` | files+JSON | atomic tmp+replace (Statically Verified) |
| Obsidian vault | user vault path | `core/obsidian_sync.py` | Markdown | tmp+replace + `.bak` (Statically Verified) |
| Analysis cache | cache engine location TBD | `core/perf_engine.py` | JSON | Not Verified |
| ROS logs | `~/.econometric_wiki/logs/`, `~/.ros_config/logs/` | `core/ros_logger.py`, `logs/log_manager.py` | log files | n/a |

### Cross-store consistency exposure (Inferred from worker chain)

One analysis run mutates **≥ 9 independent stores** with no umbrella transaction or event log. Crash points between steps leave divergent state (e.g., vault note saved but lineage not registered; typed graph updated but legacy graph failed — the legacy failure is swallowed with `except Exception: pass`). Reconciliation/replay mechanisms: **not found** — confirmed exhaustively by Persona B (X-01, B-10, B-16).

---

## Appendix A — Dependency Map (Phase 1)

### Runtime dependencies (requirements.txt)
`PyQt6, PyMuPDF, openai, PyYAML, pandas, openpyxl, numpy, requests` (requests added by EPIC 09; previously transitive via openai — REFACTOR.md acknowledges).

### Dependency direction
```
ui/ ──→ core/worker ──→ {ros_engine, parsers, memory, obsidian_sync}
                  └──→ engine_loader ──→ all engines (lazy, fault-isolated)
core/pipeline, core/intel, core/metadata, literature/ : self-contained, import core.{contracts,utils,metadata,knowledge_graph}
literature/ ──→ core.{contracts, metadata.models, knowledge_graph, utils.file_utils}
```
- **No circular dependencies detected** at package level (Inferred from import reads; persona A to verify exhaustively).
- `engine_loader.py` is the deliberate service-locator: ~20 lazy getters with failure isolation — the single choke point for engine construction.
- **Provider abstraction:** `BaseLLMProvider` ABC + `ProviderFactory` + `ProviderManager` exist, but the live path (`ros_engine.py`) constructs `openai.OpenAI` directly and branches on URL-sniffing (`_detect_provider`). **Two parallel provider architectures coexist** (Persona A territory).
- **External API surface:** OpenAI-compatible endpoints (openai SDK); `requests.post` in `core/chinese_providers.py` (3 calls) and `core/qwen_provider.py` (1 call); `literature/search/transport.py` (6 academic APIs); no other network code.
- **No plugin/subprocess extension system**; `subprocess` appears only in `ui/vault_panel.py` (file-explorer open, list-form args) and `core/obsidian_sync.py` (`open`/`xdg-open` with quoted `obsidian://` URI). `__import__` appears in `core/intel/{parser_base,intelligence_manager}.py` over hardcoded module lists (Statically Verified safe pattern; line 181 iterates a literal list).

---

## Appendix B — Data Flow Map (Phase 1)

```
[Untrusted] file / typed text / PDF / CSV / code
   ↓  parsers.parse_*          (no security scan on file content — see T2)
[Untrusted] content (≤80k chars)
   ↓  SecurityGate             (raw_text path only; sanitize+trust+audit)
[Validated*] raw_text  |  [Untrusted] parsed file content
   ↓  RAG context (vault notes — Trusted store, but poisoned-graph risk)
[Composite prompt]  → LLM (OpenAI-compatible)  [External]
[Untrusted] LLM Markdown output
   ↓  cognitive engines (rule-based scans over LLM text)
[Mutable] enhanced Markdown
   ↓  3 graph stores + memory trust + cache   [Internal, Mutable]
   ↓  obsidian_sync.save_note_to_vault        [Internal → user vault]
[External] Obsidian vault (user-visible truth surface)
   ↓  (next run) scan_vault_concepts → RAG → prompts   ← feedback loop
```

Trust labels: file inputs Untrusted; typed input Untrusted→Validated by gate; LLM output Untrusted (never fully trusted); vault/graph stores Trusted-but-mutable; the vault→RAG→prompt loop means **poisoned output at time T becomes trusted context at time T+1** — the core retrieval-poisoning surface (Persona B).

---

## Appendix C — Security Boundary Map (Phase 1)

| ID | Boundary | Control present | Status |
|---|---|---|---|
| T1 | typed text → system | SecurityGate.validate (patterns, sanitizer, trust score, audit) | Statically Verified |
| T2 | **file content → system** | **NONE** — parsed PDF/CSV/TXT/code skips the gate | Statically Verified (worker.py steps 0→1) |
| T3 | LLM output → graph/memory mutations | regex wikilink extraction only; no content policy | Statically Verified |
| T4 | LLM output → vault filesystem | save_note_to_vault sanitizes filename + atomic write + .bak | Statically Verified |
| T5 | vault → prompt (feedback loop) | none (scan_vault_concepts trusts vault) | Statically Verified |
| T6 | external APIs (6 academic + LLM) | transport retries/backoff (literature); none beyond SDK timeouts (LLM) | Partially Verified |
| T7 | config/secrets | config.json plaintext API keys in home dir (0600 Not Verified) | Statically Verified plaintext; perms Not Verified |
| T8 | subprocess | list-form args only; quoted URI for obsidian:// | Statically Verified |

No eval/exec/pickle/yaml.load/SQL anywhere (grep: zero matches). No CSRF/XSS surface (no web server). Primary threat classes per persona-B charter: indirect prompt injection via T2/T5, retrieval poisoning via T5, secret handling at T7.

---

## 23. Unverified Areas

- Runtime behavior of all JSON stores under concurrent QThread runs (Not Verified statically inferred as unsafe — B-10)
- Whether `ObsidianSafeWriter` (security.py) is actually used by the vault write path — **RESOLVED: dead code** (A-F-10, B-09 grep: zero callers; vault path uses its own inline writer)
- Cache engine storage location and eviction (Not Verified)
- `core/orchestration.py` queue semantics under load (Not Verified — zero callers, B-17)
- UI action chains beyond the analyze flow (settings persistence verified structurally only)
- PyMuPDF/openpyxl CVE surface for pinned versions (Not Verified — B-14 note)
- openai SDK exception payload contents re: key leakage in error strings (Not Verified — B-18 note)

### Phase-1 Runtime Evidence Addendum (collected read-only, 2026-08-23)

**Phase-5 re-verification log (lead auditor, independent of persona agents):**

| Claim | Verdict | Evidence |
|---|---|---|
| C-01 RAG context discarded | **CONFIRMED** | `grep rag_context core/` → exactly 3 hits: worker.py:155 init, :160 assignment, :182 status truthiness; never passed to `_run_analysis` |
| C-04 lineage timestamp IDs | **CONFIRMED** | `idea_lineage.py:161-164` — `sha256(f"{title}|{timestamp}")` |
| C-09 trust boost + unused `llm_output` score | **CONFIRMED** | `memory_trust.py:145` (`"llm_output": 0.45`), :210-219 (`memory_id` dedup → `+RETRIEVAL_BOOST`) |
| C-02 no graph read-back | **CONFIRMED** | `grep load_graph(` → production callers only inside memory.py writers/stats; worker context = `get_concept_list()` (worker.py:188) |
| C-06 qualitative unreachable | **CONFIRMED** | repo-wide grep `analyze_qualitative` → definition only |
| C-07 store self-erase | **CONFIRMED (all 4 stores)** | `except Exception:` loads at note_evolution.py:143, idea_lineage.py:113, contradiction_engine.py:166 (lead grep); memory_trust.py:97-105 one-bad-record-aborts-load (Persona B, consistent with lead's mechanism read) |
| C-13 missing embedding module | **CONFIRMED** | `core.embedding_gov` absent; `tests/test_performance_hot_paths.py` collection error imports it (pre-existing) |

| Evidence | Status | Observation |
|---|---|---|
| Store permissions | Runtime Verified | `config.json` is `-rw-------` (0600) but **every other store** (`contradictions.json`, `evolution.json`, `memory_trust.json`, `security_audit.jsonl`, `kg_*.json`, `~/.ros_memory/*`) is `-rw-r--r--` (0644, world-readable) |
| Permission enforcement | Statically Verified | **No `chmod`/`0o600` anywhere in the codebase** (grep across all `.py`). The 0600 on config.json is coincidental (creator umask), not a designed control |
| Secret storage | Runtime Verified | Live API key (`sk-ws-…`, len 115, DashScope) stored **plaintext** in `config.json` fields `api_key` |
| Audit-log chaining | Runtime Verified | `security_audit.jsonl` (47 events) carries per-event self-hash `_hash` only; **no `prev_hash`** → lines can be deleted/edited without detection |
| Store liveness | Runtime Verified | `kg_nodes.json`, `kg_edges.json`, `graph_store.json`, `lineage_*.json`, `math_ontology.json`, `memory_trust.json` last modified **2026-06-01**; `contradictions.json`, `evolution.json`, `security_audit.jsonl` last modified **2026-08-19** → several engines' stores have not been written for ~2.5 months (inferred inactive or silently failing; persona C to determine) |
| Worker chain tail | Statically Verified | `_update_semantic_graph` failure → status message only; `ValidationWorker` propagates API-test errors correctly |

---

## 9. API and Integration Findings (Phase 1)

### External API inventory (Statically Verified)

| Integration | Call sites | Auth | Timeout | Retry | Rate-limit handling | Error mapping |
|---|---|---|---|---|---|---|
| LLM (OpenAI-compatible, streaming) | `ros_engine._call_llm` (5 analyze_* fns) | API key in-memory from config | **None explicit** — SDK default | silent stream→non-stream fallback; FaultRecovery wraps at worker level (3 retries + SafeMode) | none (relies on provider) | exception string surfaced to UI |
| LLM validation probe | `ros_engine.validate_api` | same | none explicit | none | n/a | mapped to hints (401/404/timeout) |
| DeepSeek/GLM/Kimi/MiniMax/ERNIE/SiliconFlow/01.AI | `chinese_providers.py` (3× `requests.post`) | api_key param | 30–60 s | none | none | `raise_for_status` |
| Qwen (legacy path) | `qwen_provider.py` (1× `requests.post`) | api_key param | present | none | none | `raise_for_status` |
| OpenAlex | `literature/search/openalex_provider.py` | none (polite `mailto`) | 25 s | transport: 3 retries, exp. backoff + jitter | 429 Retry-After honored | TransportError → provenance record |
| Semantic Scholar | `semantic_scholar_provider.py` | optional `x-api-key` | 25 s | same transport | 429 Retry-After honored | provenance record (observed live: public pool throttles) |
| Crossref | `crossref_provider.py` | none (polite `mailto`) | 25 s | same | same | same |
| PubMed E-utilities | `pubmed_provider.py` | optional `api_key` | 25 s | same | transport pacing | same |
| arXiv | `arxiv_provider.py` | none | 25 s | same | **3 s min interval** (courtesy) | same |
| SSRN | `ssrn_provider.py` via OpenAlex index | none | 25 s | same | same | same |
| Obsidian URI | `obsidian_sync.py` (`open`/`xdg-open` subprocess) | n/a | n/a | n/a | n/a | try/except silent |

**Provider abstraction verdict (§12 requirement):** the academic layer has a clean contract (`LiteratureProvider` + registry — new sources drop in). The LLM layer does **not**: live analysis constructs `openai.OpenAI` directly in `ros_engine._build_client` and branches on URL sniffing; the `BaseLLMProvider`/`ProviderFactory`/`ProviderManager` architecture exists in parallel but is not the live path. Model/provider replacement today works only because every supported backend speaks the OpenAI chat protocol — embedding models, vector backends and non-OpenAI protocols would require touching `ros_engine` itself. *(Persona A owns the architecture decision on this; recorded here as integration fact.)*

---

## 10. Graph and Semantic Integrity Findings

Consolidated from Persona C (primary), B, A. Full details in §4.3/§4.2/§4.1.

| Concern | Finding | Sev |
|---|---|---|
| Source of truth | Five parallel graph stores; none read back on the next run; vault + concept registry implicitly dominate (C-02, F-05, B matrix) | P1 |
| Entropy control | No pruning/decay/dedup anywhere; template headings registered as concepts → positive-feedback pollution loop; `.bak`/index accumulation (C-03, B-09, F-14) | P1 |
| Lineage integrity | Duplicate ORIGIN node per re-analysis; self-parent risk; `wikilinks[:3]` parents; 8/10 transformation types unreachable; branch/merge dead (C-04, B-11) | P1 |
| Contradictions | Persisted typed entities, but write-only: never re-enter prompts/retrieval; detection is intra-note keyword co-occurrence; `target_note` is a keyword string, not a note (C-08, C-12) | P1 / P2 |
| Evolution ladder | Real 6-stage ladder + durable store; but mechanical one-way promotion, version ×2/run, no content history, rename orphans history (C-11) | P2 |
| Graph-integrity engine | Checkpoints hold counts+hash only (rollback impossible); RAM-only snapshots; O(V+E) validation per commit; tx-buffer bypasses edge cap (C-16, B-12) | P2 |
| Legacy graph semantics | `note_path` always `""`; edge sets replaced per run (silent edge loss); backlinks never removed (C-15) | P2 |
| Delete protocol | Vault delete synchronizes nothing; no tombstones anywhere in any store (lead finding) | P2 |
| Semantic-graph hardening | Typed store hard-fails permanently on corruption/schema mismatch — no migration or quarantine (B-16) | P3 |

**Verdict (charter C.2):** the typed knowledge graph is **not** the primary source of truth today — it is write-only. Designating it canonical is the single highest-leverage architectural decision (§21).

## 11. RAG Findings

| Concern | Finding | Sev |
|---|---|---|
| Loop closure | `rag_context` computed per analysis, never passed to the LLM — core "cognition signal per token" capability absent (C-01, B-13) | **P1** |
| Retrieval substrate | No embeddings anywhere (`core.embedding_gov` phantom); L2 folders hardcoded Econometrics; L3 non-recursive glob; L4 = first ~60 walk-ordered files; 50% of ranking weights always zero (C-13) | P2 |
| Budgeting | `TokenBudgetManager.allocate()` never called; budget defaults exist but are unenforced (C-13) | P2 |
| Context flooding | Unbounded concept registry ∪ vault wikilinks injected raw into every prompt — O(vault size) growth; opposite of the stated philosophy (C-14) | P2 |
| Trust model | Every vault candidate hard-coded trust 0.9; `.bak` junk re-retrieved (B-04, B-09) | P1 (as part of T5) |
| Cache coherence | CACHED_ABSTRACTION key disjoint from worker cache keyspace → structurally unreachable; context never cached despite key computation (C-13) | P2 |
| Observability theater | `rag_observability` records retrievals that influence nothing (C-01 corollary, lead §15) | P2 |

## 12. Clean Code Findings

From Persona A (full detail §4.1): god-function `_execute` (~200 lines, 12 concerns, 19 except-clauses, 7 bare-pass; F-12); three error contracts coexisting with a dead exception hierarchy containing a latent `NameError` (F-09); three parsing stacks with double PDF parse and errors-as-content (F-08); ~2.5k LOC verified dead code misleading contributors (F-10); magic constants scattered (`[:16]`, `[:1000]`, `[:2000]`, trust 0.9/0.7, confidence 0.8); four divergent wikilink regexes and two divergent topic classifiers (F-16); source-regex "regression tests" (F-15). Counterweight: genuinely clean templates exist (`config.py`, `file_utils`, `literature/` package, `knowledge_graph.py` frozen DTOs).

## 13. Architecture Findings

1. **Meta-pattern (root cause):** every version wave (v3→v8) added a parallel layer beside the live path instead of migrating it — the live path is consistently the least-engineered stack (three personas, independent convergence). REFACTOR_PLAN.md/REFACTOR_REPORT.md confirm this is known, half-finished work.
2. **Service-locator drift:** `engine_loader` provides fault isolation but returns `Optional` (promised NullObject never implemented), pushing null-checks everywhere and masking hard failures (F-03/F-06 interaction).
3. **Dual provider stacks** — ADR in §4.1: staged migration to one `LLMProvider` Protocol (Option B).
4. **Four ingestion/cognition pipelines** (`core/parsers` live; `core/pipeline`, `core/intel`, `core/metadata` library-only) with the best-engineered one bypassed by the product (F-08, C-05).
5. **Dependency direction is sound** at package level (no cycles found; `ui → core` only; `literature → core.contracts/metadata`).
6. **Platform contract broken:** declared Python 3.9 vs actual 3.11 floor (F-03).

## 14. Reliability Findings

From Persona B (full detail §4.2): non-atomic persistence (X-01/P0); SafeMode fallback cached as authoritative + `.format()` crash on `{}`-titles (B-05, P1); no cancellation + no explicit LLM timeout + retry amplification → tens-of-minutes hangs (B-06); fail-open security (X-02); no cross-process locking, shared fixed tmp names (B-10); non-idempotent re-analysis (B-11); divergent corruption semantics across stores (B-16); dead queue/reliability machinery (B-17). Positive: circuit breaker, Retry-After-aware literature transport, SafeMode concept, and fault-isolated engine loading are real, working primitives.

---

## 15. Observability Findings (Phase 1)

The charter requires the system to answer: *What happened? Why? Which component? Which data changed? Which model? How many tokens? How long? What failed? Can it be replayed/rolled back?*

| Question | Answer today | Evidence |
|---|---|---|
| What happened / which component | Partial — UI status stream + `engine_update` signals (volatile); structured JSONL events only on the `DocumentPipeline` flow (`core/pipeline/*.py` call `log_event`) | Statically Verified |
| Which model / how many tokens | **NO** — `StructuredLogger.log_analysis_complete(title, tokens, elapsed_ms)` exists but is never called; streaming calls don't capture usage | Statically Verified |
| Correlation / trace IDs | **NO** — `ObservabilityEngine.new_trace_id()` exists but has zero call sites | Statically Verified |
| Metrics (cache hit rate, success rate) | **NO** at runtime — `ObservabilityEngine`/`SystemMetrics`/`AlertManager` fully implemented with **zero production call sites** (dead infrastructure) | Statically Verified (`grep record_analysis|get_observability(` → definitions only) |
| Security events | YES — `security_audit.jsonl` (47 events on this machine; unchained — see §27 T7 note) | Runtime Verified |
| RAG retrieval metrics | YES — worker calls `rag_observability.record_retrieval(...)` per run | Statically Verified |
| Replayability | **NO** — vault notes carry no model/prompt/version provenance (footer only: "Processed by ROS v7.0"); no event log of the analysis run | Statically Verified |
| Rollback | Partial — vault write keeps `.bak_<ts>`; snapshots dir `.ros_snapshots` absent on this machine (ObsidianSafeWriter never instantiated) | Runtime Verified |

### [P2] Live analysis path has no durable observability; ObservabilityEngine is dead infrastructure

**File:** `core/observability.py`, `core/worker.py` **Component:** `ObservabilityEngine` / `AnalysisWorker._execute` **Detected By:** Lead auditor **Status:** Statically Verified

**Problem:** The complete observability stack (trace IDs, analysis metrics, alerts, timers, efficiency reports) is implemented but never invoked. The live worker imports `StructuredLogger as _SL` and never uses it; per-run model, latency, token usage, and failure classification exist only as transient Qt signals. After a crash or a disputed note, nothing can answer which model produced it, at what cost, or what failed around it.
**Evidence:** `core/observability.py:197-392` (full engine) vs zero call sites for `record_analysis` / `get_observability` / `new_trace_id` repo-wide; `worker.py:36` imports `_SL` with no subsequent use; `rag_observability` is the only observability component actually wired.
**Why It Matters:** Years-scale scientific cognition infrastructure requires auditable runs (model swaps, cost tracking, failure forensics). Current state makes cost audits, regression forensics, and reproducibility claims impossible.
**Security Impact:** none directly. **Data Integrity Impact:** provenance gap for every LLM-produced note. **Architecture Impact:** dead parallel infrastructure increases maintenance surface.
**Recommended Fix:** Wire three calls into `_execute`: `new_trace_id()` at start; `record_analysis(...)` at completion/failure with model + elapsed + fallback flag; persist trace id + model into note frontmatter. Then delete or keep `ObservabilityEngine` based on adoption — but do not leave it dead.
**Regression Risk:** low (additive logging). **Required Tests:** fake-LLM worker run → analysis record present with model/elapsed; frontmatter contains trace id.
**Priority:** P2

---

## 16. Performance and Cost Findings (Phase 1, static)

### LLM call inventory (Statically Verified)

| Call site | Calls per analysis | Notes |
|---|---|---|
| `ros_engine._call_llm` via `analyze_paper/transcript/dataset/equation/notes` | **1** | streaming; silent fallback to non-streaming on stream failure |
| `ros_engine.extract_graph_edges` | **0** | deliberately deterministic regex extraction — no second network dependency (good design) |
| `ros_engine.validate_api` | 1 (user-triggered) | 5-token probe |
| SafeMode fallback (`fault_recovery`) | 0 | local template note on provider failure |
| `literature/` EPIC 09 expansion | 0 in worker path | standalone/opt-in only; per-provider transport retries bounded |

**Token budget per analysis:** content truncated at 20k–65k chars by type (≈5k–16k input tokens) + `max_tokens` 6000–8192 by provider + full graph-node list and researcher profile injected into every prompt. Cache engine (`content_hash` + `incremental_state.json`) short-circuits identical re-analysis.

### Cost risks

### [P2] Silent mid-stream truncation returns partial analysis as complete

**File:** `core/ros_engine.py` **Component:** `_call_llm` **Detected By:** Lead auditor (pre-persona) **Status:** Statically Verified

**Problem:** If the streaming response raises mid-stream after some chunks arrived, the exception is swallowed (`except Exception: pass`) and the partial text is returned as if complete; the non-streaming fallback only runs when zero chunks arrived.
**Evidence:** `ros_engine.py:526-541` — `for chunk in stream: ... except Exception: pass` then `if chunks: return "".join(chunks)`.
**Why It Matters:** Truncated notes are persisted to vault/graphs with no flag — corrupted knowledge silently enters the second brain; re-analysis only happens if the user notices.
**Security Impact:** none. **Data Integrity Impact:** PERSISTENT — partial note cached (`cache.put_analysis`) and graph-mutated. **Architecture Impact:** low.
**Recommended Fix:** Track stream completion (catch exception, discard partial chunks, fall through to non-streaming; or mark result `truncated=True` and refuse cache put).
**Regression Risk:** low — adds one retry on rare failures.
**Required Tests:** stream-raises-after-N-chunks → result equals full non-streamed response.
**Priority:** P2

### [P2] Qualitative-analysis entry point exists but is unreachable

**File:** `core/ros_engine.py` **Component:** `analyze_qualitative` **Detected By:** Lead auditor (action-chain trace) **Status:** Statically Verified

**Problem:** A dedicated qualitative-analysis API (QUALITATIVE_PROMPT, material_type, framework parameters) is defined but called by no UI action, worker branch, or test. Qualitative material is instead routed through `analyze_transcript` (worker else-branch), relying on epistemic-mode branching inside generic prompts.
**Evidence:** grep across repo: single match at definition site `ros_engine.py:773`; worker `_run_analysis` has no `qualitative` branch.
**Why It Matters:** The system's flagship promise of epistemic diversity is partially nominal at the action-chain level: interpretivist/constructivist inputs never reach the purpose-built qualitative prompt.
**Recommended Fix:** Wire an explicit qualitative input type (or route `input_type in (interview, ethnography, field_notes)` to it), or delete the dead path.
**Regression Risk:** low either way. **Required Tests:** routing test per input type.
**Priority:** P2

### [P3] `_detect_epistemic_mode` contains a never-matching discipline entry

**File:** `core/ros_engine.py` **Component:** `_detect_epistemic_mode` **Detected By:** Lead auditor **Status:** Statically Verified

**Problem:** `quant_disciplines` contains `"machineLearning"` (camelCase) while the comparison value is lowercased (`disc_norm`), so the entry can never match.
**Evidence:** `ros_engine.py:576-579`.
**Recommended Fix:** lowercase the set members (also fixes the conceptual mismatch — ML is not a social-science discipline for this product's core).
**Priority:** P3

---

## 17. Test Coverage Findings (Phase 1)

115 test functions across 16 modules in `tests/` + 3 legacy root-level test files (~3,068 LOC). (Statically Verified inventory.)

| Area | Module(s) | Verdict |
|---|---|---|
| Document pipeline (7 stages, storage, error recovery, parsers) | test_document_pipeline.py (747 lines, 16 classes) | Strong |
| Document intelligence extractors | test_document_intelligence.py | Broad but **partly broken** (4 failures are test-code bugs) |
| Knowledge graph store + extractor + idempotency | test_semantic_knowledge_graph.py | Strong |
| Graph integrity transactions | test_graph_integrity_transactions.py | Thin (2 tests) |
| Security gate / classifier / evolution / contradiction / obsidian sync / regressions | test_v8.py (434 lines) | Moderate |
| Worker semantic-graph emission | test_worker_semantic_graph.py | Thin (2 tests; mocks the chain) |
| RAG retrieval bounds + hot-path performance | test_rag_retrieval_bounds.py, test_performance_hot_paths.py | Moderate; **hot_paths module fails collection** (imports nonexistent `core.embedding_gov`) |
| EPIC 09 literature expansion | test_scientific_context.py (36 tests) | Strong (network-free) |
| Config reliability | test_config_reliability.py | Adequate |
| **Live worker chain end-to-end** | — | **MISSING** (no test exercises steps 0→7 of `AnalysisWorker._execute` with a fake LLM) |
| **RAG engine `prepare_context` semantics** | — | Weak (bounds only) |
| **Memory trust decay, lineage, math ontology, tension engines** | — | MISSING (only test_v8 touches evolution/contradiction) |
| Cross-store crash consistency | — | MISSING |

**Baseline note:** 8 failures + 1 collection error are pre-existing (verified against untouched baseline): test-code signature mismatches in `test_document_intelligence.py`, imports of nonexistent `core.pdf_parser` and `core.embedding_gov`. These must be fixed or deleted in Phase 1 (Stabilize) — a red suite hides real regressions.

---

## 18. Refactoring Plan

Guiding rule (charter §17): **make the smallest safe change that meaningfully improves the system**, in priority order Security > Data Integrity > Correctness > Reliability > Architecture > Maintainability > Performance > Style. No semantic information (concepts, provenance, lineage, contradictions, hypotheses) may be destroyed by any step (charter §18). Tests gate every phase (charter §19).

### Phase 0 — Understand ✅ (this audit)
**Objective:** architecture reconstruction, dependency/database/security-boundary/data-flow mapping, three-persona audit, cross-review.
**Result:** this report. All P0/P1 claims independently re-verified by the lead auditor (§23 verification log).

### Phase 1 — Stabilize
**Objective:** make the suite green and the platform contract honest, so later phases have a trustworthy gate.
**Files:** `tests/test_document_intelligence.py`, `tests/test_performance_hot_paths.py`, `core/engine_loader.py` (phantom getters), `.github/workflows/*.yml`, `core/Pipfile`.
**Actions:** fix or delete the 4 broken intel tests (test-code bugs) and the `pdf_parser` import test; delete or re-stub the `embedding_gov` imports (F-06); pin CI to Python 3.11+ (or swap `datetime.UTC` → `timezone.utc`) and add a version guard (F-03); add flake8/black config and ratchet (F-17).
**Risks:** none to runtime behavior. **Dependencies:** none. **Tests:** full suite green incl. collection. **Expected result:** green baseline; honest platform floor.

### Phase 2 — Secure
**Objective:** close X-02 (P0) and B-04/B-09/B-08.
**Files:** `core/worker.py` (step 0 + new post-parse validation), `core/security.py` (block policy, class-body `validate_input`, optional hash-chained audit), `core/parsers.py` (size gates, errors-as-signals), `core/config.py` + `core/provider_manager.py` (chmod 0600/0700), `core/obsidian_sync.py` (backup rotation + scan exclusion), `core/memory_trust.py` (`llm_output` source type).
**Actions:** fail-closed gate incl. post-parse content + file metadata; block on any CRITICAL; LLM-output validation boundary before mutations with wikilink/node caps; plaintext-secret permission hardening; `.bak` eviction + exclusion from scans; store LLM text at trust 0.45 class.
**Risks:** false-positive blocks on legitimate academic text → quarantine/review path. **Dependencies:** Phase 1 green suite. **Tests:** gate-block unit tests, malicious-PDF fixture, hostile-LLM-output fixture, permission assertion. **Expected result:** every trust boundary (T1–T8) enforced or explicitly accepted.

### Phase 3 — Correct
**Objective:** close X-01 (P0) and the correctness P1s (B-05, C-01, C-04, C-09, F-13).
**Files:** all store save/load pairs (via a shared `core/utils` persistence contract), `core/fault_recovery.py` (SafeMode template), `core/worker.py` (rag_context wiring, `is_fallback` handling, single-flight), `core/idea_lineage.py` (stable IDs, self-link exclusion), `core/memory_trust.py` (remove RETRIEVAL_BOOST), `ui/main_window.py` (lifecycle guards).
**Actions:** atomic + fsync writes and corrupt-quarantine loaders for every store; never cache fallbacks; inject `rag_context` into prompts with untrusted-content delimiters; lineage idempotency; worker single-flight + `deleteLater`.
**Risks:** prompt shape change (C-01) — validate output quality before/after on fixtures. **Dependencies:** Phase 2. **Tests:** kill-mid-write, corrupt-record survival, cache-miss-after-fallback, re-analysis idempotency, rag-context-in-prompt. **Expected result:** no silent data-loss path; the cognition loop closed.

### Phase 4 — Refactor
**Objective:** collapse parallel stacks (root-cause meta-pattern) without behavior change.
**Files:** provider stacks (ADR in §4.1), parsing stacks, error contracts, `_execute` decomposition, dead-code removal (~2.5k LOC), wikilink/classifier unification.
**Actions:** staged LLMProvider Protocol migration (delete dead stack A first); route worker ingestion through `DocumentPipeline` behind an adapter; adopt `Ok/Err` at module boundaries and quarantine `exceptions.py`; extract `_execute` steps into testable units; centralize wikilink parsing in `core/utils/markdown_utils.py`.
**Risks:** medium — signal ordering and UI-visible strings must be preserved; golden tests first. **Dependencies:** Phases 1–3. **Tests:** golden equivalence per migrated path. **Expected result:** one stack per concern; live path is the engineered path.

### Phase 5 — Optimize
**Objective:** enforce budgets and entropy control (C-03, C-14, C-16; B-06).
**Actions:** ranked top-k `existing_nodes` with hard cap; output-side growth caps in the mutation APIs; `.bak`/index dedup; explicit LLM timeouts + cooperative cancellation; incremental graph validation; real embeddings index (design decision) replacing walk-order keyword scan.
**Dependencies:** Phase 4 seams. **Tests:** prompt-size bound test; entropy-budget test (N re-analyses ⇒ bounded growth); timeout/cancel tests.

### Phase 6 — Extend
**Objective:** realize currently-nominal capabilities on the corrected foundation: contradiction re-entry into prompts/retrieval (C-08), lineage transformation classification (C-04), epistemic-aware maturity/trust scoring + qualitative routing (C-06), model/prompt provenance stamping (C-05), wire EPIC 09 literature expansion into the desktop flow (its pipeline entry point already exists, unused by the UI).
**Dependencies:** Phases 3–5. **Tests:** per capability (e.g., unresolved contradiction for concept X appears in the next prompt mentioning X).

---

## 19. Immediate Fixes (do first, all low-risk)

1. **Gate block path** (`worker.py:111`): `"; ".join(t.description for t in result.threats)`; emit `error_occurred`; return. *(X-02.1)*
2. **Block on any CRITICAL threat** regardless of trust score. *(X-02.2)*
3. **Post-parse validation**: run the gate on parsed `content` + `file_meta` before the LLM. *(X-02.3)*
4. **Fail closed** on gate exceptions; remove "무시" fall-through. *(X-02.4)*
5. **Atomic store writes**: swap every `write_text(json…)` for `core.utils.file_utils.atomic_write` (mechanical, template exists). *(X-01.1)*
6. **Quarantine instead of wipe**: corrupt JSON → rename `.corrupt-<ts>` + warning, never silent `{}`. *(X-01.2)*
7. **SafeMode**: skip `cache.put_analysis`/`mark_computed` when `is_fallback`; build the template without `str.format`. *(B-05)*
8. **Secret permissions**: `os.chmod(0o600)` on `config.json`/`providers.json` at write. *(B-08)*
9. **Worker single-flight guard** + `deleteLater`. *(F-13)*
10. **CI**: Python 3.11 floor + lint config. *(F-03, F-17)*

## 20. Short-Term Refactoring (Phases 2–3 remainder)

LLM-output validation boundary with caps (B-04/B-12); `llm_output` trust class + remove RETRIEVAL_BOOST (C-09); lineage stable IDs + self-link exclusion (C-04); inject `rag_context` with untrusted delimiters (C-01); `classify_error` from typed signals, real provider key for the breaker (F-11); cross-process lockfile (B-10); parser size gates + errors-as-signals (B-14); explicit LLM timeout + cancel flag (B-06); vault `.bak` rotation/exclusion (B-09/F-14); trust-decay math fix before anyone enables it (C-10); fix intel test bugs and phantom modules (Phase 1).

## 21. Long-Term Architecture (Phases 4–6)

1. **One canonical graph**: typed `semantic_knowledge_graph.json` as source of truth; one-time migrator from legacy JSON; other stores become derived projections or are deleted (C-02/F-05). UI stat consumers rewired.
2. **One provider seam**: staged `LLMProvider` Protocol per ADR (§4.1).
3. **One ingestion path**: `DocumentPipeline` (best-engineered stack) behind a worker adapter; EPIC 09 literature expansion + metadata-engine provenance become reachable from the UI (C-05).
4. **Persistence contract**: every store gets schema version + migration hook + atomic/fsync write + quarantine (config.py as model; B-16).
5. **Provenance everywhere**: `{model, provider, prompt_hash, ts, trace_id}` in note frontmatter and edge metadata; hash-chained audit log (B-15, C-05).
6. **Retrieval upgrade**: real persisted embedding index + graph-neighbor expansion from the canonical graph + enforced token budgets — replacing walk-order keyword scan (C-13); contradiction-aware ranking weights finally populated (C-08).
7. **Entropy governance**: TTL/threshold pruning, concept normalization, weak-edge decay — scheduled, logged, reversible (C-03).
8. **Contradictions as first-class participants**: unresolved contradictions injected (token-budgeted) into future prompts and retrieval; cross-note contradiction edges with human confirmation (C-08/C-12).

## 22. Regression Risks

| Change | Risk | Mitigation |
|---|---|---|
| Fail-closed gate | False-positive blocks on academic text quoting injection patterns | Quarantine/review path; per-input-type pattern tuning; benign-corpus regression test |
| rag_context injection | Prompt shape change alters output style/quality | Before/after fixture comparison; token budget cap |
| Canonical graph migration | UI panels/stats read legacy stores | Per-consumer rewiring checklist; migration dry-run; legacy kept read-only during transition |
| Atomic-write rollout | Behavior change on happy path | None expected (same content); write-path-only tests |
| Worker decomposition | Signal ordering / UI-visible strings change | Preserve exact emit sequence; snapshot tests of signal stream |
| Dead-code deletion | `test_v8` source-regex tests break | Replace with behavior tests first (F-15) |
| Backup rotation | Users relying on `.bak` files | Move to `.ros_snapshots/` (kept, not deleted) before exclusion |
| Python floor bump | Users on older interpreters | Explicit startup error + README note (better than silent cripple) |

---

## 24. Final Engineering Assessment

**Would a competent engineer understand this system three years from now?**
*Not yet.* The accretion pattern (parallel stacks per version wave, live path = least-engineered stack, ~2.5k LOC of misleading dead "capability", three error contracts, five graph stores) actively misleads readers about what the product does. The materials for understanding exist — ARCHITECTURE.md, DOCUMENT_PIPELINE.md, per-EPIC docs, and genuinely excellent internal templates (config.py, knowledge_graph.py, literature/) — but the code's actual topology contradicts its documentation. Phases 1–4 close this gap; each is small, testable, and reversible.

**Would a researcher trust the provenance, lineage, contradictions, and transformations of their knowledge?**
*Not yet.* Provenance exists only in disconnected subsystems (EPIC 09, document pipeline); lineage duplicates roots per re-analysis; contradictions are detected but never influence future reasoning; evolution versions inflate mechanically; and X-01 means the entire record can silently vanish on an ordinary crash. The intellectual data model is *right* — the scorecard (§4.3) shows real structures for every claimed capability — but runtime wiring currently delivers roughly a third of the promise, and the durability guarantees are below what "years of intellectual evolution" requires.

**Would the system survive model replacement, database migration, plugin failure, API failure, corrupted input, and years of semantic growth?**
*Partially.* Model replacement works only within the OpenAI-chat protocol (no seam for embeddings/non-chat backends). API failure is handled (breaker + SafeMode) but the fallback path itself is buggy (B-05). Corrupted input is handled by parsers structurally but not securely (X-02). Years of semantic growth is the weakest axis: no pruning, no dedup, template-pollution feedback loop, O(vault-size) prompt growth (C-03/C-14). Database "migration" is N/A (no SQL) but JSON schema evolution has no mechanism outside the one typed store, which hard-fails instead of migrating.

**Overall:** a system with a genuinely original and correct intellectual architecture, real engineering competence in its newest layers, and systemic integration debt in its live path. Two P0s (silent mass data loss; non-functional injection defense) must be fixed before any further feature work. The refactoring templates already exist inside the codebase — the path forward is migration, not rewrite.

## 25. Recommended Next Steps

1. **Today:** Phase 1 Stabilize + Immediate Fixes #1–#6 (gate + persistence). These are mechanical, low-risk, and remove both P0s.
2. **This week:** Phase 2 Secure remainder (output boundary, secrets permissions, backup hygiene) with the listed tests.
3. **Next two weeks:** Phase 3 Correct (fallback cache, rag_context wiring, lineage idempotency, lifecycle guards).
4. **Then:** Phases 4–6 in order, each gated on golden tests, with the canonical-graph migration as the keystone decision.
5. **Continuous:** keep this report's Refactoring Ledger current; every fix lands with its required test; re-run the suite (must stay green after Phase 1).

---

# Refactoring Ledger

Status: OPEN · INVESTIGATING · READY · IN PROGRESS · VERIFIED · BLOCKED · DEFERRED

| ID | File | Problem | Severity | Action | Status |
|----|------|---------|----------|--------|--------|
| X-01 | core/memory.py + 6 cognitive stores | Non-atomic writes + silent self-erase on corruption | **P0** | atomic_write everywhere + quarantine loaders + schema sentinels + periodic backups | **VERIFIED** (2026-08-23: atomic writes + quarantine loaders landed in memory.py, note_evolution, idea_lineage, contradiction_engine, research_tension, math_ontology, memory_trust; per-record tolerant loading; 10 regression tests) |
| X-02 | core/worker.py, core/security.py, core/parsers.py | Injection defense chain non-functional (crash on block, threshold math, fail-open, T2 bypass) | **P0** | Fail-closed gate: fix block path, block-on-CRITICAL, post-parse validation, no monkey-patch | **VERIFIED** (2026-08-23: block path fixed, CRITICAL always blocks, post-parse file+metadata validation, fail-closed on exception/missing engine; 9 regression tests incl. worker-level) |
| C-01 | core/worker.py, core/ros_engine.py | rag_context computed then discarded | P1 | Add `{retrieved_context}` prompt slot; pass through `_run_analysis` | **VERIFIED** (2026-08-23: rag_context threaded through worker → all 5 live analyze_* functions, appended under an explicit untrusted-vault-material delimiter; prompt-capture regression tests for paper/notes/equation paths) |
| C-02/F-05 | 4–5 graph stores | No source of truth; none read back | P1 | Canonical typed graph + migrator; demote others | IN PROGRESS — **Stage 1 VERIFIED** (2026-08-23): `core/graph_migration.py` one-time sentinel-idempotent legacy→typed migrator, non-destructive (legacy file untouched), fail-isolated lazy trigger in worker, 4 regression tests. Remaining: UI-stats consumer rewiring + legacy store demotion (Stages 2–3) |
| C-03 | memory/ros_engine/obsidian_sync | No entropy control; template-heading pollution loop | P1 | Stop headings-as-concepts; pruning; backup GC; index dedup | OPEN |
| C-04 | core/idea_lineage.py, core/worker.py | Duplicate lineage nodes; self-parent risk; dead type system | P1 | Stable IDs by (title, content-hash); exclude self-links; derive transform type | IN PROGRESS (2026-08-23: upsert-by-title verified — re-analysis updates the existing node, no duplicate roots; self-links excluded at worker + engine; content-hash change tracking tested. Transform-type derivation (8/10 dead vocabulary) deferred to Phase 6) |
| C-05 | core/worker.py, core/metadata/engine.py | No provenance on LLM outputs/edges/records | P1 | Stamp {model, prompt_hash, ts, trace_id}; attach ProvenanceRecord; wire EPIC 09 to UI path | OPEN |
| C-06 | core/worker.py, ui/input_panel.py | Qualitative input mis-routed; quant-biased scoring | P1 | Route qualitative → analyze_qualitative; epistemic-aware scoring | READY |
| C-07 | 4 history stores | Whole-file wipe on parse error (subsumed by X-01) | P1 | per X-01 | **VERIFIED** (with X-01, 2026-08-23) |
| C-08 | contradiction/tension/worker | Contradictions write-only | P1 | Inject unresolved into prompts; populate ranking weights | OPEN |
| C-09 | core/worker.py, core/memory_trust.py | LLM text trusted as paper 0.90; repetition boosts | P1 | source_type="llm_output"; remove RETRIEVAL_BOOST | **VERIFIED** (2026-08-23: worker stores `llm_output` class (0.45); boost removed; repetition-no-longer-boosts regression test) |
| B-04 | worker/knowledge_graph | LLM output mutates stores unvalidated | P1 | Output validation boundary + caps | **VERIFIED** (2026-08-23: `validate_llm_output` boundary before all mutations; wikilink budget + node-name caps in extractor and graph-integrity loop; poisoned-output-never-persisted worker test) |
| B-05 | worker/fault_recovery | Fallback cached as authoritative; `.format()` crash | P1 | Never cache fallbacks; escaped template | **VERIFIED** (cache guard 2026-08-23 Phase 1; sentinel-based template replacing `str.format` 2026-08-23 Phase 3 — `{}`-titles no longer crash; both halves regression-tested) |
| F-03 | CI/Pipfile + 13 modules | Declared 3.9 < actual 3.11 floor | P1 | Pin 3.11+ or drop UTC; version guard | **VERIFIED** (2026-08-23: CI 3.11, Pipfile 3.11, main.py startup guard) |
| F-13 | ui/main_window.py | No single-flight; closeEvent abandons thread | P1→P2 | Guards + deleteLater + bounded wait | **VERIFIED** (2026-08-23: single-flight guard with user notice, toolbar QAction locked alongside button, `finished→deleteLater`, closeEvent bounded 2 s wait; guard regression test) |
| B-06 | ros_engine/worker | No timeout/cancellation; retry amplification | P2 | Explicit timeout; cancel flag; Stop button | OPEN |
| B-14 | core/parsers.py | Whole-file reads (OOM DoS); errors-as-content | P2 | Size gates; errors-as-signals | **VERIFIED** (2026-08-23: `MAX_INPUT_FILE_BYTES` pre-read gate on all five parsers; parse errors returned as `parse_error` signals, worker fails fast — error text never reaches LLM/vault; 3 regression tests) |
| B-08 | config/provider_manager | Plaintext secrets, no permissions | P2 | chmod 0600/0700; keychain path later | **VERIFIED** (2026-08-23: 0600 on config.json + providers.json at write; permission assertion tests; keychain/env-first remains future) |
| B-09/F-14 | core/obsidian_sync.py | .bak proliferation pollutes scans/prompts | P2 | Snapshots dir + eviction + scan exclusion | **VERIFIED** (2026-08-23: backups moved to `.ros_backups/`, capped at 5/note, excluded from list_notes/scan_vault_concepts; rotation + exclusion tests) |
| B-10 | all singletons | No cross-process locking | P2 | Lockfile + per-store RLocks | OPEN |
| B-11/C-11 | evolution/lineage/trust | Non-idempotent re-analysis | P2 | Version-neutral upsert; single register_note; boost removal | **VERIFIED** (2026-08-23: version-neutral upsert when checksum unchanged — double registration no longer inflates version; lineage idempotency via C-04; trust boost removed via C-09; 4 regression tests. Remaining: collapsing the double register_note call site — harmless now, deferred) |
| B-12 | knowledge_graph/graph_integrity | Output-side growth unbounded; cap bypass | P2 | Caps in mutation APIs incl. tx buffer | OPEN |
| B-13 | — | (merged into C-01) | — | — | VERIFIED (merged) |
| B-14 | core/parsers.py | Parser DoS surface | P2 | Size gates; caps; errors-as-signals | READY |
| C-10 | core/memory_trust.py | Decay math wrong + never scheduled | P2 | Decay from initial/incremental; dry-run logging | OPEN |
| C-12 | contradiction/tension/math | Keyword-only, econ-only detection | P2 | LLM-assisted cross-note candidates; discipline packs | DEFERRED |
| C-13 | core/rag_engine.py | No embeddings; walk-order scan; dead budget | P2 | Real index + budget enforcement (Phase 5) | OPEN |
| C-14 | worker/ros_engine | Unbounded existing_nodes injection | P2 | Ranked top-k + hard cap | READY |
| C-15 | memory/worker | Legacy graph detached; edges replaced | P2 | Real note paths; edge history (moot after canonical migration) | DEFERRED |
| C-16 | core/graph_integrity.py | Checkpoints cannot restore; O(V+E) per commit | P2 | Persisted snapshots; incremental validation | OPEN |
| F-06 | core/engine_loader.py | Phantom embedding_gov getters | P2 | Delete getters + worker shims (Phase 1) | **VERIFIED** (2026-08-23: phantom getters + dead worker shims removed; real `SemanticDeduplicator` implemented per the existing test contract; hot-path tests now run) |
| F-07 | provider stacks | Dual provider architecture | P2 | ADR Option B staged | IN PROGRESS — **Stage 1 VERIFIED** (2026-08-23): dead stack A deleted (`base_provider`/`provider_factory`/`provider_manager`/`llm_client`/`chinese_providers`/`qwen_provider`, ~800 LOC + 2 root fossil tests); `PROVIDER_PROFILES` registry formalized with 16 behavior-equivalence tests. Stage 2 (Protocol migration of the live path) remains Phase 6 |
| F-08 | parsing stacks | Three stacks; double PDF parse | P2 | DocumentPipeline adapter (Phase 4) | DEFERRED to Phase 6 (documented: adapter requires FileStorage side-effect review; risk/benefit favored deferral under smallest-safe-change rule) |
| F-09 | contracts/exceptions | Three error contracts; dead hierarchy + NameError | P2 | Adopt Ok/Err; quarantine exceptions.py | **VERIFIED** (2026-08-23: latent `NameError: Path` fixed Phase 1; module formally quarantined with do-not-raise notice; Ok/Err remains the live contract) |
| F-10 | multiple | ~2.5k LOC dead code | P2 | Delete or adopt (ObsidianSafeWriter: adopt) | **VERIFIED** (2026-08-23: `state_manager.py`, `graph_utils.py`, QueueOrchestrator machinery (218 lines), full provider stack A, 2 root fossil test files deleted — zero-reference verified pre-deletion; deletions pinned by regression tests; ObsidianSafeWriter adoption remains open) |
| F-11 | core/fault_recovery.py | classify_error substring confusion | P2 | Typed classification; real breaker key | READY |
| F-12 | core/worker.py | God function; swallowed exceptions | P2 | Step extraction + log-and-continue | DEFERRED to Phase 5 (worker-level hardening tests now provide the safety net; decomposition without that net was higher risk than value) |
| F-15 | tests/ | Critical paths untested; source-regex tests | P2 | WorkerHarness + behavior tests | OPEN |
| Lead §15 | observability/worker | No durable run observability | P2 | trace_id + record_analysis wiring; frontmatter stamp | READY |
| Lead §8 | ui/vault_panel.py | Delete unsynchronized across stores | P2 | delete_note service + tombstones | OPEN |
| Lead §16 | core/ros_engine.py | Silent mid-stream truncation | P2 | Completion tracking; discard partial on error | **VERIFIED** (2026-08-23: streams without a terminal finish_reason are discarded and retried non-streaming; complete streams return directly without redundant retry; 2 regression tests) |
| B-15 | core/security.py | Audit not tamper-evident | P3 | prev_hash chaining | **VERIFIED** (2026-08-23: hash-chained AuditTrail with `verify_chain()`; tamper-detection regression test; legacy unchained files documented) |
| B-16 | store corpus | Divergent corruption semantics; no fsync | P3 | Unified persistence contract (Phase 4) | OPEN |
| B-17 | core/orchestration.py | Dead queue machinery; no rate limiting | P3 | Adopt or delete | **VERIFIED** (2026-08-23: QueueOrchestrator + task queue machinery deleted per audit; ResourceGovernor retained; client-side rate limiting remains future) |
| B-18 | worker/parsers | Tracebacks to UI; errors as content | P3 | classify_error user messages | OPEN |
| C-17/F-16 | classifier/obsidian_sync | Map collisions; dual vocabularies/regexes | P3 | Dedupe maps; single wikilink util | IN PROGRESS (journal-map F601 collisions deduped with pin tests; **wikilink regexes unified** into `core.utils.markdown_utils.extract_wikilink_targets` across all 5 consumers with golden tests, 2026-08-23; topic-vocabulary unification remains) |
| F-17 | CI | Lint decorative | P3 | Config + ratchet (Phase 1) | **VERIFIED** (2026-08-23: `.flake8` fatal-class config, `pyproject.toml` black config, CI flake8 core/ passes, black enforced on literature/) |
| baseline | tests/ | 8 pre-existing failures + 1 collection error | P2 | Fix/delete (Phase 1) | **VERIFIED** (2026-08-23: suite green 232→256 with new hardening tests) |

---

## Appendix — Phase-1 maps

The Dependency Map, Data Flow Map, and Security Boundary Map produced in Phase 1 appear in this document as **Appendix A (Dependency Map)**, **Appendix B (Data Flow Map)**, and **Appendix C (Security Boundary Map)**, immediately following §23.
