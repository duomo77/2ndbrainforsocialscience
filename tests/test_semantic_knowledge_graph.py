from __future__ import annotations

import json

import pytest

from core.knowledge_graph import (
    GraphMutation,
    KnowledgeEdge,
    KnowledgeGraphService,
    KnowledgeGraphStore,
    KnowledgeNode,
    NodeType,
    RelationshipType,
    SemanticMarkdownExtractor,
)


def test_store_persists_typed_nodes_and_weighted_edges_atomically(tmp_path):
    store = KnowledgeGraphStore(tmp_path / "semantic_graph.json")
    source = KnowledgeNode.create("Paper A", NodeType.SOURCE, source_refs=("paper-a.md",))
    method = KnowledgeNode.create("Difference in Differences", NodeType.METHOD)
    edge = KnowledgeEdge.create(
        source.node_id,
        method.node_id,
        RelationshipType.USES,
        confidence=0.91,
        source_ref="paper-a.md",
    )

    store.apply(GraphMutation(nodes=(source, method), edges=(edge,)))

    restored = KnowledgeGraphStore(tmp_path / "semantic_graph.json")
    assert restored.get_node(method.node_id).node_type == NodeType.METHOD
    assert restored.get_edge(edge.edge_id).confidence == pytest.approx(0.91)
    assert json.loads((tmp_path / "semantic_graph.json").read_text(encoding="utf-8"))["schema_version"] == 1


def test_store_rejects_dangling_edges_without_partial_writes(tmp_path):
    graph_file = tmp_path / "semantic_graph.json"
    store = KnowledgeGraphStore(graph_file)
    source = KnowledgeNode.create("Paper A", NodeType.SOURCE)
    missing = KnowledgeNode.create("Missing", NodeType.CONCEPT)
    edge = KnowledgeEdge.create(source.node_id, missing.node_id, RelationshipType.RELATED_TO)

    with pytest.raises(ValueError, match="unknown target"):
        store.apply(GraphMutation(nodes=(source,), edges=(edge,)))

    assert store.stats()["total_nodes"] == 0
    assert not graph_file.exists()


def test_markdown_extractor_creates_first_class_methods_questions_and_relationships():
    markdown = """---
title: Minimum Wage Study
type: paper
---
# Minimum Wage Study
## Methods
- Uses [[Difference in Differences]]
## Knowledge Graph Connections
- Extends: [[Policy Evaluation]]
- Contradicts: [[Perfect Competition]]
## Open Research Questions
- How do effects vary by region?
"""

    mutation = SemanticMarkdownExtractor().extract(
        title="Minimum Wage Study",
        markdown=markdown,
        source_type="paper",
        source_ref="minimum-wage.md",
    )
    nodes = {node.name: node for node in mutation.nodes}
    edges = {(edge.source, edge.target, edge.relationship) for edge in mutation.edges}

    assert nodes["Difference in Differences"].node_type == NodeType.METHOD
    assert nodes["How do effects vary by region?"].node_type == NodeType.QUESTION
    assert (
        nodes["Minimum Wage Study"].node_id,
        nodes["Policy Evaluation"].node_id,
        RelationshipType.EXTENDS,
    ) in edges
    assert (
        nodes["Minimum Wage Study"].node_id,
        nodes["Perfect Competition"].node_id,
        RelationshipType.CONTRADICTS,
    ) in edges


def test_service_ingestion_is_idempotent_and_updates_importance(tmp_path):
    service = KnowledgeGraphService(KnowledgeGraphStore(tmp_path / "semantic_graph.json"))
    markdown = "# Note\nConnects to [[Causal Inference]] and [[Regression]]."

    first = service.ingest_markdown("Research Note", markdown, "notes", "note.md")
    second = service.ingest_markdown("Research Note", markdown, "notes", "note.md")

    assert first.nodes_upserted == 3
    assert second.nodes_upserted == 3
    assert service.store.stats()["total_nodes"] == 3
    assert service.store.stats()["total_edges"] == 2
    ranked = service.store.rank_nodes(limit=3)
    assert ranked[0].importance_score >= ranked[-1].importance_score

