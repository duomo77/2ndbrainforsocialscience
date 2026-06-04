from __future__ import annotations

from types import SimpleNamespace

from core.worker import AnalysisWorker


def _worker():
    return AnalysisWorker(
        api_key="key",
        base_url="",
        model="model",
        input_type="paper",
        file_path="paper.md",
        raw_text="",
        metadata={"title": "Paper A"},
        vault_path="",
        auto_save=False,
        topic_override="",
    )


def test_worker_emits_semantic_graph_metrics(monkeypatch, qt_app):
    worker = _worker()
    events = []
    worker.engine_update.connect(lambda name, data: events.append((name, data)))
    service = SimpleNamespace(
        ingest_markdown=lambda *args, **kwargs: SimpleNamespace(
            total_nodes=4, total_edges=3, nodes_upserted=4, edges_upserted=3
        )
    )
    monkeypatch.setattr("core.knowledge_graph.get_knowledge_graph_service", lambda: service)

    worker._update_semantic_graph("Paper A", "# Paper A\n[[Causal Inference]]")

    assert events == [
        (
            "semantic_graph",
            {"nodes": 4, "edges": 3, "nodes_upserted": 4, "edges_upserted": 3},
        )
    ]


def test_worker_reports_semantic_graph_failure_without_raising(monkeypatch, qt_app):
    worker = _worker()
    statuses = []
    worker.status_update.connect(statuses.append)

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr("core.knowledge_graph.get_knowledge_graph_service", fail)

    worker._update_semantic_graph("Paper A", "# Paper A")

    assert any("Semantic graph" in status and "disk full" in status for status in statuses)

