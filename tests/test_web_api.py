from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import app as app_mod
from api.app import create_app
from api import runtime as runtime_mod
from core.analysis_pipeline import PipelineOutcome
from core.contracts import Ok


def _disable_optional_engines(monkeypatch):
    for name in (
        "get_cache_engine",
        "get_incremental_engine",
        "get_fault_recovery_engine",
        "get_resource_governor",
        "get_rag_engine",
        "get_rag_observability",
        "get_graph_integrity_engine",
        "get_memory_trust_engine",
        "get_evolution_engine",
        "get_contradiction_engine",
        "get_math_engine",
    ):
        monkeypatch.setattr(runtime_mod._el, name, lambda *args, **kwargs: None)

    gate = SimpleNamespace(
        validate_input=lambda content, source="unknown": SimpleNamespace(
            is_safe=True,
            threats=[],
            sanitized_content=content,
            trust_score=1.0,
        ),
        validate_llm_output=lambda content: SimpleNamespace(
            is_safe=True,
            threats=[],
            sanitized_content=content,
        ),
        validate_title=lambda title: "".join(
            character for character in title if character not in "\r\n"
        ),
    )
    monkeypatch.setattr(runtime_mod._el, "get_security_layer", lambda: gate)
    monkeypatch.setattr(runtime_mod.memory, "get_concept_list", lambda: [])
    monkeypatch.setattr(runtime_mod.memory, "load_profile", lambda: {})
    monkeypatch.setattr(runtime_mod.memory, "update_graph", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_mod.memory, "register_concepts", lambda *args, **kwargs: None)


def test_health_endpoint_reports_fastapi_runtime():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["runtime"] == "fastapi"


def test_demo_analysis_endpoint_runs_without_pyqt_or_api_key(monkeypatch):
    _disable_optional_engines(monkeypatch)
    monkeypatch.setattr(
        runtime_mod.WebAnalysisRuntime,
        "update_semantic_graph",
        lambda self, title, markdown: self._event(
            "engine", "semantic_graph", {"nodes": 1, "edges": 0}
        ),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/analyze",
        json={
            "input_type": "notes",
            "raw_text": "Causal inference uses [[Treatment Effect]] assumptions.",
            "metadata": {"title": "Web Smoke"},
            "model": "demo-local",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Web Smoke"
    assert "epistemic_mode: local-demo" in body["markdown"]
    assert "ai_generated: true" in body["markdown"]
    assert "human_verified: false" in body["markdown"]
    assert "[[Treatment Effect]]" in body["markdown"]
    assert any(event["kind"] == "status" for event in body["events"])


def test_paper_demo_response_includes_deep_context(monkeypatch):
    _disable_optional_engines(monkeypatch)
    monkeypatch.setattr(
        runtime_mod.WebAnalysisRuntime,
        "update_semantic_graph",
        lambda self, title, markdown: self._event(
            "engine", "semantic_graph", {"nodes": 1, "edges": 0}
        ),
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/analyze",
        json={
            "input_type": "paper",
            "raw_text": "Research question: Does policy affect employment? We use DID and parallel trends.",
            "metadata": {"title": "Policy Paper"},
            "model": "demo-local",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "type: paper" in body["markdown"]
    assert "[[Policy Paper - Deep Research Context]]" in body["markdown"]
    assert "type: research_context" in body["deep_context_markdown"]
    assert body["deep_context_path"] == ""


def test_file_upload_honors_multipart_analysis_fields(monkeypatch):
    captured = {}

    def fake_analysis(request):
        captured["request"] = request
        return Ok(PipelineOutcome(markdown="# uploaded", title=request.metadata["title"])), []

    monkeypatch.setattr(app_mod, "run_web_analysis", fake_analysis)
    client = TestClient(create_app())

    response = client.post(
        "/api/analyze-file",
        data={
            "input_type": "notes",
            "title": "Chosen Title",
            "model": "demo-local",
            "topic_override": "Political Economy",
        },
        files={"file": ("uploaded.md", b"research note", "text/markdown")},
    )

    assert response.status_code == 200
    request = captured["request"]
    assert request.input_type == "notes"
    assert request.metadata == {"title": "Chosen Title", "source_ref": "uploaded.md"}
    assert request.model == "demo-local"
    assert request.topic_override == "Political Economy"


def test_file_upload_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr(app_mod, "MAX_UPLOAD_BYTES", 4)
    client = TestClient(create_app())

    response = client.post(
        "/api/analyze-file",
        files={"file": ("too-large.md", b"12345", "text/markdown")},
    )

    assert response.status_code == 413


def test_file_upload_rejects_unsupported_extension():
    client = TestClient(create_app())

    response = client.post(
        "/api/analyze-file",
        files={"file": ("payload.exe", b"not executable", "application/octet-stream")},
    )

    assert response.status_code == 415
