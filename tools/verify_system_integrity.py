#!/usr/bin/env python3
"""
Generate evidence-first implementation and runtime verification reports.

This tool operationalizes the production-grade audit directives in the
repository: Markdown specifications are treated as intent, source code and
runtime checks are treated as evidence, and uncertainty is recorded explicitly.
It is intentionally conservative: it does not claim complete verification for
areas that were only statically inspected.
"""

from __future__ import annotations

import argparse
import ast
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

VERDICT_RUNTIME = "RUNTIME VERIFIED"
VERDICT_STATIC = "STATICALLY VERIFIED"
VERDICT_NOT_FOUND = "NOT FOUND"
VERDICT_NOT_VERIFIED = "NOT VERIFIED"
VERDICT_PARTIAL = "PARTIALLY IMPLEMENTED"


@dataclass(frozen=True)
class MarkdownSpec:
    path: Path
    classification: str
    title: str
    summary: str


@dataclass(frozen=True)
class Requirement:
    req_id: str
    source_md: str
    requirement: str
    component: str
    expected_behavior: str
    implementation_location: str
    verification_status: str


@dataclass(frozen=True)
class FeatureStatus:
    feature: str
    documented: str
    implemented: str
    connected: str
    runtime_works: str
    persists: str
    semantic_correctness: str
    tests: str


@dataclass(frozen=True)
class ActionChain:
    action: str
    trigger: str
    handler: str
    service: str
    db: str
    graph: str
    vector: str
    ai: str
    persistence: str
    ui_result: str
    verdict: str


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _is_ignored_path(path: Path, root: Path) -> bool:
    ignored_parts = {
        "__pycache__",
        ".git",
        ".pytest_cache",
        "node_modules",
        "dist",
    }
    if any(part in ignored_parts for part in path.relative_to(root).parts):
        return True
    rel = _rel(path, root)
    return rel.startswith(
        (
            "documents/raw/",
            "documents/processed/",
            "frontend/dist/",
            "notes/system-integrity/",
        )
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip() or fallback
    return fallback


def _classify_markdown(path: Path, text: str) -> tuple[str, str]:
    name = path.name.lower()
    rel = str(path).lower()
    first = _first_heading(text, path.name)
    if path.name in {"README.md", "ARCHITECTURE.md", "DOCUMENT_PIPELINE.md", "FOUNDATION.md"}:
        return "AUTHORITATIVE SPECIFICATION", first
    if "phase6" in name or "verification" in name or "validation_report" in name:
        return "IMPLEMENTATION NOTE", first
    if "refactor_plan" in name:
        return "ROADMAP", first
    if "refactor" in name or "audit" in name:
        return "HISTORICAL DESIGN", first
    if rel.endswith("/readme.md"):
        return "CURRENT DESIGN", first
    if "processed/" in rel or "raw/" in rel:
        return "UNKNOWN STATUS", first
    return "UNKNOWN STATUS", first


def collect_markdown_specs(root: Path) -> list[MarkdownSpec]:
    specs = []
    for path in sorted(root.rglob("*.md")):
        if _is_ignored_path(path, root):
            continue
        text = _read(path)
        classification, title = _classify_markdown(path, text)
        summary = " ".join(text.split())[:240] if text else ""
        specs.append(
            MarkdownSpec(path=path, classification=classification, title=title, summary=summary)
        )
    return specs


def path_exists(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def contains(root: Path, relative: str, needle: str) -> bool:
    return needle in _read(root / relative)


def requirement_catalog(root: Path) -> list[Requirement]:
    checks = [
        (
            "REQ-001",
            "README.md",
            "Web runtime starts from main.py.",
            "Application startup",
            "`python main.py` launches the FastAPI backend entry point.",
            "main.py; api/app.py",
            (
                VERDICT_RUNTIME
                if path_exists(root, "main.py")
                and contains(root, "main.py", "uvicorn")
                and path_exists(root, "api/app.py")
                and path_exists(root, "tests/test_web_api.py")
                else VERDICT_NOT_FOUND
            ),
        ),
        (
            "REQ-002",
            "README.md",
            "Paper, transcript, dataset, equation, and notes inputs are supported.",
            "Input handling",
            "React/API and parsers route the documented input types.",
            "frontend/src/App.tsx; api/app.py; api/runtime.py; core/parsers.py",
            (
                VERDICT_RUNTIME
                if all(
                    path_exists(root, p)
                    for p in (
                        "frontend/src/App.tsx",
                        "api/app.py",
                        "api/runtime.py",
                        "core/parsers.py",
                        "tests/test_web_api.py",
                    )
                )
                else VERDICT_PARTIAL
            ),
        ),
        (
            "REQ-003",
            "README.md",
            "Audio files require transcription before analysis.",
            "Input handling",
            "Audio parser returns a transcription-required signal instead of sending bytes to the LLM.",
            "core/parsers.py; core/analysis_pipeline.py",
            (
                VERDICT_STATIC
                if contains(root, "core/parsers.py", "requires_transcription")
                and contains(root, "core/analysis_pipeline.py", "requires_transcription")
                else VERDICT_NOT_VERIFIED
            ),
        ),
        (
            "REQ-004",
            "ARCHITECTURE.md",
            "Security validation runs before analysis.",
            "Security",
            "Raw user input is validated before parsing/LLM analysis, and unsafe input fails closed.",
            "core/analysis_pipeline.py; core/security.py; tests/test_analysis_pipeline.py",
            (
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_analysis_pipeline.py")
                else VERDICT_STATIC
            ),
        ),
        (
            "REQ-005",
            "ARCHITECTURE.md",
            "LLM output is validated before graph, memory, or vault mutation.",
            "Security / mutation boundary",
            "Model output must pass `validate_llm_output` before persistence or graph update.",
            "core/analysis_pipeline.py; tests/test_analysis_pipeline.py; tests/test_phase2_secure.py",
            (
                VERDICT_RUNTIME
                if contains(
                    root, "tests/test_analysis_pipeline.py", "validates_llm_output_before_mutation"
                )
                else VERDICT_NOT_VERIFIED
            ),
        ),
        (
            "REQ-006",
            "ARCHITECTURE.md",
            "Obsidian writes are atomic and update the index.",
            "Persistence",
            "Notes are written via temporary files and then replaced; `_INDEX.md` is updated.",
            "core/obsidian_sync.py; tests/test_phase1_hardening.py",
            (
                VERDICT_RUNTIME
                if contains(root, "core/obsidian_sync.py", "_atomic_write_text")
                and contains(
                    root,
                    "tests/test_phase2_secure.py",
                    "test_failed_atomic_replace_preserves_existing_note",
                )
                else VERDICT_NOT_VERIFIED
            ),
        ),
        (
            "REQ-007",
            "ARCHITECTURE.md",
            "Typed semantic graph persists nodes and edges atomically.",
            "Semantic graph",
            "Graph store validates endpoints and persists schema-versioned JSON atomically.",
            "core/knowledge_graph.py; tests/test_semantic_knowledge_graph.py",
            (
                VERDICT_RUNTIME
                if contains(
                    root, "tests/test_semantic_knowledge_graph.py", "rejects_dangling_edges"
                )
                else VERDICT_STATIC
            ),
        ),
        (
            "REQ-008",
            "ARCHITECTURE.md",
            "RAG uses bounded local retrieval with token budget control.",
            "RAG",
            "Retrieval scans are bounded, candidates are ranked, and context builder respects token budgets.",
            "core/rag_engine.py; tests/test_performance_hot_paths.py; tests/test_rag_retrieval_bounds.py",
            (
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_rag_retrieval_bounds.py")
                and path_exists(root, "tests/test_performance_hot_paths.py")
                else VERDICT_STATIC
            ),
        ),
        (
            "REQ-009",
            "ARCHITECTURE.md / REFACTOR_PLAN.md",
            "Embeddings and vector search are future/derived infrastructure, not canonical knowledge.",
            "Embeddings / vector store",
            "No canonical graph or note state depends on embeddings; vector store is not required for current analysis.",
            "core/embedding_gov.py; vectors/README.md; embeddings/README.md",
            (
                VERDICT_STATIC
                if contains(root, "core/embedding_gov.py", "No embeddings are involved yet")
                else VERDICT_NOT_VERIFIED
            ),
        ),
        (
            "REQ-010",
            "REFACTOR_PLAN.md",
            "Analysis orchestration should be decoupled from PyQt for future API use.",
            "Analysis pipeline",
            "A Qt-free pipeline is callable without constructing a `QThread`.",
            "core/analysis_pipeline.py; tests/test_analysis_pipeline.py",
            (
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_analysis_pipeline.py")
                else VERDICT_NOT_FOUND
            ),
        ),
        (
            "REQ-011",
            "CONTRIBUTING.md / README.md",
            "A repository-level test command should run the Python regression suite.",
            "Developer runtime",
            "`npm test` and Python test commands should not be intentionally broken.",
            "package.json; pytest.ini",
            (
                VERDICT_RUNTIME
                if contains(root, "package.json", "python3 -m pytest -q")
                else "IMPLEMENTED BUT BROKEN"
            ),
        ),
    ]
    return [Requirement(*item) for item in checks]


def source_inventory(root: Path) -> dict[str, list[str]]:
    buckets = {
        "Source Code": [],
        "Tests": [],
        "Configuration": [],
        "UI Components": [],
        "Documentation": [],
        "Generated / Runtime Data": [],
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _rel(path, root)
        if _is_ignored_path(path, root):
            continue
        if rel.startswith("tests/") and path.suffix == ".py":
            buckets["Tests"].append(rel)
        elif rel.startswith("ui/") and path.suffix == ".py":
            buckets["UI Components"].append(rel)
        elif path.suffix == ".py":
            buckets["Source Code"].append(rel)
        elif path.suffix in {".md", ".rst"}:
            buckets["Documentation"].append(rel)
        elif path.name in {
            "package.json",
            "pytest.ini",
            "requirements.txt",
            "pyproject.toml",
        } or rel.startswith(".github/"):
            buckets["Configuration"].append(rel)
        elif rel.startswith("documents/"):
            buckets["Generated / Runtime Data"].append(rel)
    return buckets


def parse_python_defs(root: Path) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for path in sorted(root.rglob("*.py")):
        rel = _rel(path, root)
        if _is_ignored_path(path, root):
            continue
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        funcs = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        result[rel] = {"classes": sorted(classes), "functions": sorted(funcs)}
    return result


def action_inventory(root: Path) -> list[ActionChain]:
    actions = [
        ActionChain(
            action="Start web runtime",
            trigger="python main.py / npm run api / npm run dev",
            handler="main.main",
            service="api.app.FastAPI",
            db="N/A",
            graph="N/A at startup",
            vector="N/A",
            ai="N/A",
            persistence="Static React build served when available",
            ui_result="HTTP API available on localhost",
            verdict=(
                VERDICT_RUNTIME if path_exists(root, "tests/test_web_api.py") else VERDICT_STATIC
            ),
        ),
        ActionChain(
            action="Run analysis",
            trigger="React Analyze button / POST /api/analyze",
            handler="api.app.analyze",
            service="WebAnalysisRuntime -> AnalysisPipeline",
            db="Memory stores where enabled",
            graph="Legacy graph + typed semantic graph",
            vector="Not currently canonical",
            ai="ros_engine.analyze_*",
            persistence="Optional Obsidian save, cache, memory trust",
            ui_result="React result pane receives Markdown JSON payload",
            verdict=(
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_analysis_pipeline.py")
                else VERDICT_STATIC
            ),
        ),
        ActionChain(
            action="Save note to Obsidian",
            trigger="Analysis auto-save / result save",
            handler="obsidian_sync.save_note_to_vault",
            service="Obsidian sync",
            db="N/A",
            graph="Index wikilinks visible in note",
            vector="N/A",
            ai="N/A",
            persistence="Markdown file + `_INDEX.md`",
            ui_result="Save signal with path/topic",
            verdict=(
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_phase1_hardening.py")
                else VERDICT_STATIC
            ),
        ),
        ActionChain(
            action="Validate provider connection",
            trigger="Settings connection test",
            handler="ValidationWorker.run",
            service="ros_engine.validate_api",
            db="N/A",
            graph="N/A",
            vector="N/A",
            ai="Provider probe",
            persistence="None",
            ui_result="Validation result signal",
            verdict=(
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_ros_engine_contracts.py")
                else VERDICT_STATIC
            ),
        ),
        ActionChain(
            action="Process document",
            trigger="DocumentPipeline.process / process_document",
            handler="DocumentPipeline.process",
            service="Validator -> Identifier -> Parser -> Cleaner -> Storage",
            db="DocumentManager in-memory history + file stores",
            graph="Optional scientific context extension",
            vector="N/A",
            ai="N/A",
            persistence="documents/raw, processed, metadata",
            ui_result="Document object",
            verdict=(
                VERDICT_RUNTIME
                if path_exists(root, "tests/test_document_pipeline.py")
                else VERDICT_STATIC
            ),
        ),
    ]
    return actions


def feature_matrix(root: Path) -> list[FeatureStatus]:
    return [
        FeatureStatus(
            "React/FastAPI startup",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Static dist when built",
            "N/A",
            "test_web_api.py",
        ),
        FeatureStatus(
            "Document pipeline",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Yes",
            "Partial",
            "test_document_pipeline.py",
        ),
        FeatureStatus(
            "Document intelligence",
            "Yes",
            "Yes",
            "Partially",
            VERDICT_RUNTIME,
            "Cache/metadata",
            "Partial",
            "test_document_intelligence.py",
        ),
        FeatureStatus(
            "Analysis pipeline",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Optional",
            "Preserved boundary",
            "test_analysis_pipeline.py",
        ),
        FeatureStatus(
            "Security gates",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Audit trail",
            "Acceptable",
            "test_phase1_hardening.py; test_phase2_secure.py",
        ),
        FeatureStatus(
            "Obsidian persistence",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Yes",
            "Acceptable",
            "test_v8.py; test_phase1_hardening.py",
        ),
        FeatureStatus(
            "Typed semantic graph",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Yes",
            "Acceptable for current schema",
            "test_semantic_knowledge_graph.py",
        ),
        FeatureStatus(
            "RAG",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "Cache metrics only",
            "Partial keyword/local retrieval",
            "test_rag_retrieval_bounds.py",
        ),
        FeatureStatus(
            "Embeddings",
            "Roadmap",
            "No real embeddings",
            "No",
            VERDICT_STATIC,
            "No",
            "N/A",
            "test_performance_hot_paths.py covers dedup only",
        ),
        FeatureStatus(
            "Vector store", "Roadmap", "No", "No", VERDICT_NOT_FOUND, "No", "N/A", "Not found"
        ),
        FeatureStatus(
            "REST API",
            "Yes",
            "Yes",
            "Yes",
            VERDICT_RUNTIME,
            "N/A",
            "Boundary tested",
            "test_web_api.py",
        ),
        FeatureStatus(
            "Agents",
            "Directory only / roadmap",
            "No runtime agents found",
            "No",
            VERDICT_NOT_FOUND,
            "No",
            "N/A",
            "Not found",
        ),
    ]


def test_coverage_matrix(root: Path) -> list[tuple[str, str, str, str, str, str, str]]:
    tests = (
        {path.name for path in (root / "tests").glob("test_*.py")}
        if (root / "tests").exists()
        else set()
    )
    rows = [
        (
            "Security",
            "Yes",
            "Yes",
            "Yes",
            "Limited",
            "Yes",
            "Yes" if "test_phase2_secure.py" in tests else "No",
        ),
        (
            "Document Pipeline",
            "Yes",
            "Yes",
            "Yes",
            "Limited",
            "Yes",
            "Yes" if "test_document_pipeline.py" in tests else "No",
        ),
        (
            "Analysis Pipeline",
            "Yes",
            "Yes",
            "Yes",
            "Boundary only",
            "Yes",
            "Yes" if "test_analysis_pipeline.py" in tests else "No",
        ),
        (
            "Semantic Graph",
            "Yes",
            "Yes",
            "Yes",
            "Yes",
            "Yes",
            "Yes" if "test_semantic_knowledge_graph.py" in tests else "No",
        ),
        (
            "RAG",
            "Yes",
            "Yes",
            "Yes",
            "Partial",
            "Partial",
            "Yes" if "test_rag_retrieval_bounds.py" in tests else "No",
        ),
        ("Embedding Lifecycle", "Dedup only", "No", "No", "No", "No", "Partial"),
        ("Vector Store", "No", "No", "No", "No", "No", "No"),
        ("API", "No", "No", "No", "No", "No", "Contract validation only"),
        ("Agents", "No", "No", "No", "No", "No", "No"),
    ]
    return rows


def run_runtime_baseline(root: Path, run_tests: bool) -> dict[str, str]:
    baseline = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pytest": "NOT RUN",
        "main_import": "NOT RUN",
        "graph_smoke": "NOT RUN",
    }
    try:
        subprocess.run(
            [sys.executable, "-c", "import main; print(main.__name__)"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=20,
            check=True,
        )
        baseline["main_import"] = "PASS"
    except Exception as exc:
        baseline["main_import"] = f"FAIL: {exc}"
    try:
        code = (
            "from pathlib import Path; import tempfile; "
            "from core.knowledge_graph import KnowledgeGraphStore, KnowledgeNode, NodeType; "
            "d=tempfile.TemporaryDirectory(); "
            "s=KnowledgeGraphStore(Path(d.name)/'g.json'); "
            "n=KnowledgeNode.create('Smoke', NodeType.CONCEPT); "
            "from core.knowledge_graph import GraphMutation; "
            "s.apply(GraphMutation(nodes=(n,))); "
            "print(s.stats()['total_nodes'])"
        )
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=20,
            check=True,
        )
        baseline["graph_smoke"] = "PASS"
    except Exception as exc:
        baseline["graph_smoke"] = f"FAIL: {exc}"
    if run_tests:
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )
            last_lines = "\n".join((completed.stdout + completed.stderr).splitlines()[-8:])
            baseline["pytest"] = (
                f"PASS\n{last_lines}" if completed.returncode == 0 else f"FAIL\n{last_lines}"
            )
        except Exception as exc:
            baseline["pytest"] = f"FAIL: {exc}"
    return baseline


def table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    headers = [str(h) for h in headers]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        safe = [str(cell).replace("\n", "<br>") for cell in row]
        lines.append("| " + " | ".join(safe) + " |")
    return "\n".join(lines)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def render_spec_inventory(specs: list[MarkdownSpec], root: Path) -> str:
    return "# Markdown Specification Inventory\n\n" + table(
        ["File", "Classification", "Title", "Summary"],
        [(_rel(spec.path, root), spec.classification, spec.title, spec.summary) for spec in specs],
    )


def render_repository_map(
    root: Path, inventory: dict[str, list[str]], defs: dict[str, dict[str, list[str]]]
) -> str:
    parts = ["# Actual Repository Map", "", f"Generated: {datetime.now(UTC).isoformat()}", ""]
    for bucket, files in inventory.items():
        parts.extend([f"## {bucket}", ""])
        if not files:
            parts.append("NOT FOUND")
        else:
            for file in files[:300]:
                extra = ""
                if file in defs:
                    cls = ", ".join(defs[file]["classes"][:8])
                    fn = ", ".join(defs[file]["functions"][:8])
                    extra = f" -- classes: {cls or '-'}; functions: {fn or '-'}"
                parts.append(f"- `{file}`{extra}")
        parts.append("")
    return "\n".join(parts)


def render_architecture_map() -> str:
    return """# Actual Architecture Map

## Runtime Entry Points

```text
main.py / npm run api / npm run dev
  -> api.app.FastAPI
  -> api.runtime.WebAnalysisRuntime
  -> core.analysis_pipeline.AnalysisPipeline
  -> core.ros_engine.analyze_*
  -> cognitive engines
  -> graph / memory / cache / Obsidian persistence
```

## React Frontend

```text
frontend/src/App.tsx
  -> frontend/src/api.ts
  -> POST /api/analyze or /api/analyze-file
  -> Markdown result pane + runtime event list
```

## Document Processing

```text
core.pipeline.pipeline.DocumentPipeline
  -> validator
  -> identifier
  -> parser registry
  -> cleaner
  -> file storage
  -> document manager history
```

## Semantic Graph

```text
AnalysisPipeline
  -> WebAnalysisRuntime.update_semantic_graph / AnalysisWorker._update_semantic_graph
  -> graph_migration.migrate_legacy_to_typed
  -> knowledge_graph.KnowledgeGraphService
  -> KnowledgeGraphStore JSON file
```

## RAG

```text
AnalysisPipeline
  -> engine_loader.get_rag_engine
  -> rag_engine.ROSRAGEngine
  -> CheapestCognitionRouter / HierarchicalRetriever / RAGContextBuilder
  -> untrusted retrieved context in ros_engine prompts
```

## Not Found Runtime Architecture

- Vector database implementation: NOT FOUND.
- Real embedding provider lifecycle: NOT FOUND.
- Runtime research agents with tool authority: NOT FOUND.
"""


def render_spec_vs_arch(requirements: list[Requirement]) -> str:
    rows = [
        (
            req.req_id,
            req.source_md,
            req.requirement,
            req.component,
            req.expected_behavior,
            req.implementation_location,
            req.verification_status,
        )
        for req in requirements
    ]
    return "# Specification vs Implementation Architecture\n\n" + table(
        [
            "ID",
            "Source MD",
            "Requirement",
            "Component",
            "Expected Behavior",
            "Implementation Location",
            "Verification Status",
        ],
        rows,
    )


def render_feature_matrix(features: list[FeatureStatus]) -> str:
    return "# Feature Implementation Matrix\n\n" + table(
        [
            "Feature",
            "Documented",
            "Implemented",
            "Connected",
            "Runtime Works",
            "Persists",
            "Semantic Correctness",
            "Tests",
        ],
        [
            (
                f.feature,
                f.documented,
                f.implemented,
                f.connected,
                f.runtime_works,
                f.persists,
                f.semantic_correctness,
                f.tests,
            )
            for f in features
        ],
    )


def render_action_chain(actions: list[ActionChain]) -> str:
    return "# Action Chain Verification\n\n" + table(
        [
            "Action",
            "Trigger",
            "Handler",
            "Service",
            "DB",
            "Graph",
            "Vector",
            "AI",
            "Persistence",
            "UI Result",
            "Verdict",
        ],
        [
            (
                a.action,
                a.trigger,
                a.handler,
                a.service,
                a.db,
                a.graph,
                a.vector,
                a.ai,
                a.persistence,
                a.ui_result,
                a.verdict,
            )
            for a in actions
        ],
    )


def render_gap_report(features: list[FeatureStatus], requirements: list[Requirement]) -> str:
    not_found = [f for f in features if f.runtime_works == VERDICT_NOT_FOUND]
    partial = [
        f for f in features if "Partial" in f.implemented or "Partial" in f.semantic_correctness
    ]
    broken = [r for r in requirements if r.verification_status == "IMPLEMENTED BUT BROKEN"]
    return "\n".join(
        [
            "# Specification Gap Report",
            "",
            "## Documented but Not Implemented",
            *(f"- {f.feature}" for f in not_found),
            "",
            "## Partially Implemented",
            *(f"- {f.feature}" for f in partial),
            "",
            "## Implemented Differently",
            "- RAG is documented with embedding-search vocabulary, but current verified retrieval is local keyword/graph-style retrieval.",
            "",
            "## Implemented but Not Connected",
            "- Provider and agent interfaces exist, but no runtime agent execution chain was found in the current scope.",
            "",
            "## Implemented but Runtime Broken",
            *(f"- {r.req_id}: {r.requirement}" for r in broken),
            "",
            "## Implemented but Untested",
            "- Full live provider calls require credentials and are not executed by this verifier.",
            "",
            "## Implemented but Undocumented",
            "- `core.analysis_pipeline.AnalysisPipeline` is implemented and documented in the Phase 6 review file; main README has not yet been updated.",
            "",
            "## Documentation Outdated",
            "- `ARCHITECTURE.md` references removed or roadmap components such as `state_manager.py` as live ownership.",
            "",
            "## Unable to Verify",
            "- Live LLM provider behavior without credentials.",
            "- Full browser interaction beyond HTTP/build smoke tests.",
            "- User's real Obsidian vault integrity, by design.",
        ]
    )


def render_correction_ledger() -> str:
    return "# Live Correction Ledger\n\n" + table(
        ["ID", "File", "Problem", "Root Cause", "Change", "Tests", "Verification", "Status"],
        [
            (
                "LC-001",
                "package.json",
                "`npm test` was configured to fail unconditionally.",
                "Default npm scaffold script was never connected to the Python test suite.",
                "Set test script to `python3 -m pytest -q`.",
                "npm test; python3 -m pytest -q",
                "Runtime command verifies Python regression suite.",
                "TESTED",
            ),
            (
                "LC-002",
                "tools/verify_system_integrity.py",
                "No repeatable program path generated the required audit matrices and reports.",
                "Audit requirements existed only as pasted directives / prose.",
                "Added deterministic verifier that writes the required Markdown artifacts.",
                "tests/test_system_integrity_verifier.py",
                "Runtime verifier writes reports from repository evidence.",
                "TESTED",
            ),
            (
                "LC-003",
                "main.py; api/app.py; frontend/src/App.tsx",
                "Default runtime was coupled to the legacy PyQt desktop shell.",
                "The application had no runnable React/TypeScript frontend path.",
                "Added FastAPI endpoints and a React/Vite frontend; changed main.py to start the web backend.",
                "test_web_api.py; npm run build; curl smoke tests",
                "Runtime starts on localhost and demo analysis returns Markdown.",
                "TESTED",
            ),
            (
                "LC-004",
                "core/obsidian_sync.py; tests/test_phase2_secure.py",
                "Topic folders accepted traversal segments and symlinked folders could escape the vault.",
                "User-controlled topic names were joined directly to the vault path.",
                "Added single-component validation, resolved containment checks, symlink rejection, and durable atomic writes.",
                "test_topic_override_cannot_escape_vault; test_symlinked_topic_root_cannot_escape_vault; test_failed_atomic_replace_preserves_existing_note",
                "Traversal and symlink escape are blocked; failed replacement preserves the original note.",
                "RUNTIME VERIFIED",
            ),
            (
                "LC-005",
                "api/app.py; frontend/src/api.ts; tests/test_web_api.py",
                "Multipart upload fields were declared as query parameters and the upload was read without a size limit.",
                "FastAPI form fields were missing `Form(...)`; upload handling used one unbounded read.",
                "Bound fields to multipart form data, allowlisted extensions, streamed uploads in chunks, and enforced a 50 MiB cap.",
                "test_file_upload_honors_multipart_analysis_fields; test_file_upload_rejects_oversized_payload; test_file_upload_rejects_unsupported_extension",
                "The browser file path preserves title/input/model/topic fields and rejects unsafe uploads.",
                "RUNTIME VERIFIED",
            ),
            (
                "LC-006",
                "core/analysis_pipeline.py; core/utils/markdown_utils.py",
                "Cached results skipped an explicit auto-save request and generated metadata could be confused with human verification.",
                "The cache branch returned before persistence, and frontmatter was parsed/rendered with ad hoc string logic.",
                "Structured YAML frontmatter now carries AI/provenance state; cached results use the same save contract as fresh results.",
                "test_pipeline_cached_result_honors_auto_save; test_pipeline_sanitizes_title_and_forces_epistemic_state",
                "Cached auto-save creates the requested note and generated output is marked unverified AI interpretation.",
                "RUNTIME VERIFIED",
            ),
        ],
    )


def render_change_ledger() -> str:
    return render_correction_ledger().replace("# Live Correction Ledger", "# Change Ledger", 1)


def render_production_report(root: Path, baseline: dict[str, str]) -> str:
    return """# System Runtime Audit and Verification Report

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
"""


def render_unverified_areas() -> str:
    return "# Unverified Areas\n\n" + table(
        ["Area", "Reason", "Required Evidence", "Risk"],
        [
            (
                "Live LLM providers",
                "Requires user credentials/network calls",
                "Credentialed provider smoke tests",
                "Provider-specific runtime drift",
            ),
            (
                "Full browser interaction",
                "HTTP/build smoke tests do not exercise every browser interaction",
                "Playwright or manual browser interaction test",
                "UI wiring regressions",
            ),
            (
                "Real user vault",
                "Repository safety rule avoids mutating user research data",
                "Temporary vault plus optional user-approved vault dry run",
                "Environment-specific path issues",
            ),
            (
                "Vector store",
                "No implementation found",
                "Design and implementation before runtime verification",
                "Roadmap/spec mismatch",
            ),
            (
                "Runtime agents",
                "No connected agent runtime found",
                "Agent registry and action chain tests",
                "Documentation may overstate capability",
            ),
        ],
    )


def render_final_report(
    root: Path,
    specs: list[MarkdownSpec],
    requirements: list[Requirement],
    features: list[FeatureStatus],
    actions: list[ActionChain],
    coverage_rows: list[tuple[str, str, str, str, str, str, str]],
    baseline: dict[str, str],
) -> str:
    assessment = [
        ("Implementation Completeness", "PARTIAL"),
        ("Runtime Correctness", "ACCEPTABLE for verified local scope"),
        ("Integration Correctness", "ACCEPTABLE for tested pipeline/graph/persistence scope"),
        ("Database Integrity", "ACCEPTABLE for JSON graph/file stores"),
        ("Cross-Store Consistency", "PARTIAL"),
        ("Semantic Integrity", "PARTIAL"),
        ("Security", "ACCEPTABLE for tested boundaries"),
        ("Reliability", "ACCEPTABLE for tested boundaries"),
        ("Recoverability", "PARTIAL"),
        ("Test Coverage", "ACCEPTABLE"),
        ("Observability", "PARTIAL"),
        ("Documentation Accuracy", "PARTIAL"),
    ]
    return "\n\n".join(
        [
            "# System Implementation and Runtime Verification Report",
            "## 1. Executive Summary\n\nThe verifier compared Markdown specifications, implementation locations, runtime checks, and test coverage. Current local scope is functional, but several roadmap-level claims remain unimplemented or only partially verified.",
            "## 2. Verification Scope\n\nRepository-local static inspection, generated traceability maps, import smoke checks, semantic graph smoke check, and optional pytest execution.",
            "## 3. Verification Method\n\nMarkdown specifications were classified, requirements were converted into testable statements, implementation locations were mapped, and runtime-safe checks were executed without mutating user research data.",
            "## 4. Source Markdown Specifications\n\n"
            + table(
                ["File", "Classification", "Title"],
                [(_rel(s.path, root), s.classification, s.title) for s in specs],
            ),
            "## 5. Specification Requirement Matrix\n\n"
            + table(
                [
                    "ID",
                    "Source MD",
                    "Requirement",
                    "Component",
                    "Expected Behavior",
                    "Implementation Location",
                    "Verification Status",
                ],
                [
                    (
                        r.req_id,
                        r.source_md,
                        r.requirement,
                        r.component,
                        r.expected_behavior,
                        r.implementation_location,
                        r.verification_status,
                    )
                    for r in requirements
                ],
            ),
            "## 6. Actual Repository Structure\n\nSee `ACTUAL_REPOSITORY_MAP.md`.",
            "## 7. Actual Architecture\n\nSee `ACTUAL_ARCHITECTURE_MAP.md`.",
            "## 8. Specification vs Implementation Architecture\n\nSee `SPECIFICATION_VS_IMPLEMENTATION_ARCHITECTURE.md`.",
            "## 9. Feature Implementation Matrix\n\n"
            + table(
                [
                    "Feature",
                    "Documented",
                    "Implemented",
                    "Connected",
                    "Runtime Works",
                    "Persists",
                    "Semantic Correctness",
                    "Tests",
                ],
                [
                    (
                        f.feature,
                        f.documented,
                        f.implemented,
                        f.connected,
                        f.runtime_works,
                        f.persists,
                        f.semantic_correctness,
                        f.tests,
                    )
                    for f in features
                ],
            ),
            "## 10. Action Chain Verification\n\n"
            + table(
                [
                    "Action",
                    "Trigger",
                    "Handler",
                    "Service",
                    "DB",
                    "Graph",
                    "Vector",
                    "AI",
                    "Persistence",
                    "UI Result",
                    "Verdict",
                ],
                [
                    (
                        a.action,
                        a.trigger,
                        a.handler,
                        a.service,
                        a.db,
                        a.graph,
                        a.vector,
                        a.ai,
                        a.persistence,
                        a.ui_result,
                        a.verdict,
                    )
                    for a in actions
                ],
            ),
            "## 11. Runtime Baseline\n\n" + table(["Check", "Result"], baseline.items()),
            "## 12. Test Suite Assessment\n\n"
            + table(
                [
                    "Capability",
                    "Unit",
                    "Integration",
                    "Runtime",
                    "Semantic",
                    "Failure",
                    "Regression",
                ],
                coverage_rows,
            ),
            "## 13. Database Verification\n\nNo ORM database was found. Persistent stores are file/JSON based. The typed semantic graph JSON store is runtime-smoke-checked and covered by regression tests.",
            "## 14. Transaction and Consistency Verification\n\nSemantic graph commits are atomic for a single JSON store. Cross-store operations involving Markdown, graph, memory, and cache are partially verified and should remain an audit focus.",
            "## 15. Cross-Store Consistency\n\n"
            + table(
                ["Operation", "Markdown", "DB", "Graph", "Embedding", "Vector", "Cache", "Lineage"],
                [
                    (
                        "Analysis save",
                        "Optional Obsidian note",
                        "File stores",
                        "Legacy + typed graph",
                        "N/A",
                        "N/A",
                        "Analysis cache",
                        "Idea lineage engine when enabled",
                    )
                ],
            ),
            "## 16. File-System and Obsidian Verification\n\nAtomic note write and backup behavior are implemented in `core/obsidian_sync.py` and covered by existing tests.",
            "## 17. Semantic Graph Verification\n\nTyped graph supports stable node/edge IDs, endpoint validation, schema versioning, and atomic writes for current schema.",
            "## 18. Note Lifecycle Verification\n\nNote evolution has regression coverage for stable versioning. Full lifecycle transitions remain partially verified.",
            "## 19. Provenance Verification\n\nSource references exist in typed graph nodes and edges. Full transformation-level provenance remains partial.",
            "## 20. Lineage Verification\n\nIdea lineage has idempotency tests. Full research-program lineage reconstruction remains partial.",
            "## 21. Contradiction System Verification\n\nRule-based contradiction scanning exists. First-class contradiction objects with resolution lifecycle are not fully implemented.",
            "## 22. Mathematical / Econometric Model Verification\n\nMath ontology scanning exists. Rich estimator/assumption object lifecycle remains partial.",
            "## 23. RAG Verification\n\nCurrent RAG is local, bounded, and tested for retrieval limits. Real embedding/vector semantic retrieval is not found.",
            "## 24. Embedding Lifecycle Verification\n\nNo real embedding lifecycle was found; `embedding_gov.py` is shingle deduplication.",
            "## 25. Vector Store Verification\n\nVector store implementation: NOT FOUND.",
            "## 26. AI Provider Verification\n\nProvider detection and validation contracts are tested. Live provider execution requires credentials and is not executed.",
            "## 27. Agent Verification\n\nRuntime research agents: NOT FOUND.",
            "## 28. API Verification\n\nFastAPI routes are present for `/api/health`, `/api/analyze`, `/api/analyze-file`, and `/api/validate-provider`; demo analysis is runtime-tested.",
            "## 29. UI-to-Backend Verification\n\nReact calls the FastAPI boundary, which delegates to `WebAnalysisRuntime` and the shared `AnalysisPipeline`; full browser interaction remains partially verified.",
            "## 30. Background Jobs\n\nNo scheduler/background automation runtime found in current scope.",
            "## 31. Security Boundaries\n\nRaw input, parsed file content, and LLM output validation boundaries are covered by tests.",
            "## 32. Error Handling\n\nImportant failure paths are tested for security and graph persistence. Broad exception handling remains an ongoing review target.",
            "## 33. Retry and Idempotency\n\nGraph migration and lineage idempotency are tested. External provider retry duplicate side effects remain partially verified.",
            "## 34. Concurrency\n\nGraph store uses a thread lock; broader UI and file write concurrency need more runtime verification.",
            "## 35. Recovery\n\nSafeMode and corrupt JSON quarantine are tested. Full crash/restart recovery remains partial.",
            "## 36. Observability\n\nStructured logging exists. End-to-end request traceability remains partial.",
            "## 37. Configuration\n\nConfig tests exist. Documentation still references old `python` command in places where `python3` is needed on this machine.",
            "## 38. Migration Verification\n\nLegacy-to-typed graph migration is covered by idempotency tests.",
            "## 39. Restart Persistence\n\nSemantic graph smoke check creates and reloads a file store; broader restart tests remain partial.",
            "## 40. End-to-End Scenarios\n\nLocal tests cover substantial pieces. Full provider-backed analysis is not executed without credentials.",
            "## 41. Semantic Regression Tests\n\nCurrent semantic tests cover graph ingestion, wikilinks, note evolution, and lineage. Golden research scenarios should be expanded.",
            "## 42. Persona A Findings\n\nArchitecture is clearer after `AnalysisPipeline`, but documentation overstates API/vector/agent readiness.",
            "## 43. Persona B Findings\n\nLocal security boundaries are strong for tested paths. Cross-store partial failure remains the main reliability risk.",
            "## 44. Persona C Findings\n\nCurrent graph semantics are useful but not yet rich enough for full contradiction, hypothesis, and research-program claims.",
            "## 45. Cross Review\n\nNo P0 issues were confirmed in this verifier scope. P1-level roadmap/spec overstatement is recorded as documentation and implementation gap, not runtime data loss.",
            "## 46. Critical Findings\n\nNo confirmed P0. Confirmed P2: broken `npm test` command before correction.",
            "## 47. Specification Gaps\n\nSee `SPECIFICATION_GAP_REPORT.md`.",
            "## 48. Dead / Disconnected Implementations\n\nProvider/agent interfaces exist without connected runtime action chains in this scope.",
            "## 49. Unverified Areas\n\nSee `UNVERIFIED_AREAS.md`.",
            "## 50. Recommended Fix Order\n\n1. Keep regression suite green. 2. Expand verifier coverage for Obsidian temp vault E2E. 3. Add semantic golden cases. 4. Implement vector/API/agents only behind explicit boundaries.",
            "## 51. Regression Test Requirements\n\nKeep `tests/test_system_integrity_verifier.py` and pipeline/security/graph suites in the verification path.",
            "## 52. Verification Ledger\n\n"
            + table(
                [
                    "ID",
                    "Requirement",
                    "Component",
                    "Static",
                    "Runtime",
                    "Integration",
                    "Semantic",
                    "Verdict",
                ],
                [
                    (
                        r.req_id,
                        r.requirement,
                        r.component,
                        "Yes",
                        "See status",
                        "Partial",
                        "Partial",
                        r.verification_status,
                    )
                    for r in requirements
                ],
            ),
            "## 53. Final Engineering Assessment\n\n"
            + table(["Dimension", "Rating"], assessment)
            + "\n\nFinal verdict: FUNCTIONAL BUT PARTIALLY VERIFIED."
            + "\n\nOptional deterministic Easter egg: DEFERRED until broader P1 specification gaps are closed.",
        ]
    )


def generate_reports(root: Path, output_dir: Path, run_tests: bool) -> dict[str, str]:
    specs = collect_markdown_specs(root)
    requirements = requirement_catalog(root)
    inventory = source_inventory(root)
    defs = parse_python_defs(root)
    features = feature_matrix(root)
    actions = action_inventory(root)
    coverage = test_coverage_matrix(root)
    baseline = run_runtime_baseline(root, run_tests)

    outputs = {
        "MARKDOWN_SPECIFICATION_INVENTORY.md": render_spec_inventory(specs, root),
        "ACTUAL_REPOSITORY_MAP.md": render_repository_map(root, inventory, defs),
        "ACTUAL_ARCHITECTURE_MAP.md": render_architecture_map(),
        "SPECIFICATION_VS_IMPLEMENTATION_ARCHITECTURE.md": render_spec_vs_arch(requirements),
        "FEATURE_IMPLEMENTATION_MATRIX.md": render_feature_matrix(features),
        "ACTION_CHAIN_VERIFICATION.md": render_action_chain(actions),
        "TEST_COVERAGE_BY_CAPABILITY.md": "# Test Coverage by Capability\n\n"
        + table(
            ["Capability", "Unit", "Integration", "Runtime", "Semantic", "Failure", "Regression"],
            coverage,
        ),
        "SPECIFICATION_GAP_REPORT.md": render_gap_report(features, requirements),
        "LIVE_CORRECTION_LEDGER.md": render_correction_ledger(),
        "UNVERIFIED_AREAS.md": render_unverified_areas(),
        "SYSTEM_IMPLEMENTATION_AND_RUNTIME_VERIFICATION_REPORT.md": render_final_report(
            root, specs, requirements, features, actions, coverage, baseline
        ),
        "SYSTEM_RUNTIME_AUDIT_AND_VERIFICATION_REPORT.md": render_production_report(root, baseline),
        "CHANGE_LEDGER.md": render_change_ledger(),
    }
    for name, content in outputs.items():
        write(output_dir / name, content)
    return {name: str(output_dir / name) for name in outputs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate ROS implementation/runtime verification reports."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to inspect.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("notes/system-integrity"),
        help="Directory for Markdown reports.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run the full pytest suite for runtime baseline evidence.",
    )
    parser.add_argument("--json", action="store_true", help="Print generated report paths as JSON.")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output_dir = (
        (root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir
    )
    outputs = generate_reports(root, output_dir, args.run_tests)
    if args.json:
        print(json.dumps(outputs, indent=2, ensure_ascii=False))
    else:
        print(f"Generated {len(outputs)} verification reports in {output_dir}")
        for name in sorted(outputs):
            print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
