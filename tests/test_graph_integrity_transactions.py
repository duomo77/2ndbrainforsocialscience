from __future__ import annotations

from core.graph_integrity import GraphIntegrityEngine


def test_graph_integrity_engine_initializes_mutation_counter(tmp_path):
    engine = GraphIntegrityEngine(tmp_path)

    assert engine.get_stats()["mutations"] == 0


def test_graph_integrity_transaction_rejects_dangling_edge_and_rolls_back(tmp_path):
    engine = GraphIntegrityEngine(tmp_path)
    engine.begin_transaction()
    engine.add_node("Known Source", "paper")
    engine.add_edge("Known Source", "Missing Target", "related_to")

    ok, message = engine.commit_transaction()

    assert not ok
    assert "Integrity check failed" in message
    assert engine.get_stats()["nodes"] == 0
    assert engine.get_stats()["edges"] == 0

