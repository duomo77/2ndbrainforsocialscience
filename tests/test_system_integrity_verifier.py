from __future__ import annotations

import json
from pathlib import Path

from tools.verify_system_integrity import generate_reports, main


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_repo(root) -> None:
    _write(root / "README.md", "# README\n\nRun tests with python3 -m pytest -q.")
    _write(root / "ARCHITECTURE.md", "# Architecture\n\nSecurity, RAG, and graph notes.")
    _write(root / "REFACTOR_PLAN.md", "# Refactor Plan\n\nPipeline roadmap.")
    _write(root / "main.py", "from ui.main_window import MainWindow\n")
    _write(root / "ui" / "main_window.py", "class MainWindow:\n    pass\n")
    _write(
        root / "core" / "analysis_pipeline.py",
        "requires_transcription = True\n"
        "def validates_llm_output_before_mutation():\n"
        "    return True\n",
    )
    _write(
        root / "core" / "parsers.py",
        "requires_transcription = True\n",
    )
    _write(root / "core" / "security.py", "class SecurityLayer:\n    pass\n")
    _write(
        root / "core" / "obsidian_sync.py",
        "tmp_path = 'note.tmp'\n",
    )
    _write(root / "core" / "knowledge_graph.py", "class KnowledgeGraphStore:\n    pass\n")
    _write(root / "core" / "rag_engine.py", "class ROSRAGEngine:\n    pass\n")
    _write(root / "core" / "embedding_gov.py", "# No embeddings are involved yet\n")
    _write(
        root / "tests" / "test_analysis_pipeline.py",
        "def test_validates_llm_output_before_mutation():\n    pass\n",
    )
    _write(
        root / "tests" / "test_phase1_hardening.py",
        "class AtomicWrite:\n    pass\n",
    )
    _write(
        root / "tests" / "test_semantic_knowledge_graph.py",
        "def test_rejects_dangling_edges():\n    pass\n",
    )
    _write(root / "tests" / "test_rag_retrieval_bounds.py", "def test_bounds():\n    pass\n")
    _write(root / "tests" / "test_performance_hot_paths.py", "def test_hot_path():\n    pass\n")
    _write(
        root / "package.json",
        json.dumps({"scripts": {"test": "python3 -m pytest -q"}}, indent=2),
    )
    _write(root / "pytest.ini", "[pytest]\ntestpaths = tests\n")


def test_generate_reports_writes_required_integrity_artifacts(tmp_path):
    _minimal_repo(tmp_path)
    output_dir = tmp_path / "notes" / "system-integrity"

    outputs = generate_reports(tmp_path, output_dir, run_tests=False)

    expected = {
        "MARKDOWN_SPECIFICATION_INVENTORY.md",
        "ACTUAL_REPOSITORY_MAP.md",
        "ACTUAL_ARCHITECTURE_MAP.md",
        "SPECIFICATION_VS_IMPLEMENTATION_ARCHITECTURE.md",
        "FEATURE_IMPLEMENTATION_MATRIX.md",
        "ACTION_CHAIN_VERIFICATION.md",
        "TEST_COVERAGE_BY_CAPABILITY.md",
        "SPECIFICATION_GAP_REPORT.md",
        "LIVE_CORRECTION_LEDGER.md",
        "UNVERIFIED_AREAS.md",
        "SYSTEM_IMPLEMENTATION_AND_RUNTIME_VERIFICATION_REPORT.md",
        "SYSTEM_RUNTIME_AUDIT_AND_VERIFICATION_REPORT.md",
        "CHANGE_LEDGER.md",
    }
    assert expected == set(outputs)
    for path in outputs.values():
        assert Path(path).exists()

    final_report = (
        output_dir / "SYSTEM_IMPLEMENTATION_AND_RUNTIME_VERIFICATION_REPORT.md"
    ).read_text(encoding="utf-8")
    spec_vs = (output_dir / "SPECIFICATION_VS_IMPLEMENTATION_ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    assert "Final verdict: FUNCTIONAL BUT PARTIALLY VERIFIED" in final_report
    assert "REQ-011" in spec_vs
    assert "RUNTIME VERIFIED" in spec_vs


def test_cli_generates_reports(tmp_path):
    _minimal_repo(tmp_path)
    output_dir = tmp_path / "audit"

    assert main(["--root", str(tmp_path), "--output-dir", str(output_dir)]) == 0
    assert (output_dir / "SYSTEM_IMPLEMENTATION_AND_RUNTIME_VERIFICATION_REPORT.md").exists()
