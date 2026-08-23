"""
graph.py — Knowledge Graph Integration (EPIC 09)
================================================
Lifts a :class:`ScientificContext` into the ROS semantic knowledge graph
(``core.knowledge_graph``):

  * seed paper → SOURCE node
  * every retained context paper → SOURCE node with category metadata
  * one typed edge per paper, derived from its primary category:

      contradictory      → CONTRADICTS
      follow-up          → EXTENDS
      influential        → INSPIRED_BY
      replication        → SUPPORTS (CONTRADICTS when also contradictory)
      reviews / related  → RELATED_TO

Edge confidence tracks classification relevance; edge evidence carries
the classifier rationale, so graph queries remain auditable.
"""

from __future__ import annotations


from core.knowledge_graph import (
    GraphMutation,
    KnowledgeEdge,
    KnowledgeGraphService,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)
from literature.context.models import ContextCategory, ContextPaper, ScientificContext

CATEGORY_RELATIONSHIP = {
    ContextCategory.CONTRADICTORY: RelationshipType.CONTRADICTS,
    ContextCategory.FOLLOW_UP: RelationshipType.EXTENDS,
    ContextCategory.INFLUENTIAL: RelationshipType.INSPIRED_BY,
    ContextCategory.REPLICATION: RelationshipType.SUPPORTS,
    ContextCategory.REVIEW: RelationshipType.RELATED_TO,
    ContextCategory.SYSTEMATIC_REVIEW: RelationshipType.RELATED_TO,
    ContextCategory.META_ANALYSIS: RelationshipType.RELATED_TO,
    ContextCategory.RELATED: RelationshipType.RELATED_TO,
}


def build_graph_mutation(context: ScientificContext, source_ref: str = "") -> GraphMutation:
    """Deterministic seed→context mutation for the knowledge graph store."""
    seed_title = (context.seed.title or context.seed.doi or "Imported Document").strip()
    seed_node = KnowledgeNode.create(
        seed_title,
        NodeType.SOURCE,
        source_refs=(source_ref,) if source_ref else (),
        metadata={
            "source_type": "scientific_context",
            "doi": context.seed.doi or "",
            "year": context.seed.year or "",
        },
    )

    nodes = {seed_node.node_id: seed_node}
    edges = {}

    for paper in context.papers:
        title = paper.title.strip()
        if not title:
            continue
        node = KnowledgeNode.create(
            title,
            NodeType.SOURCE,
            source_refs=(source_ref,) if source_ref else (),
            metadata=_paper_metadata(paper),
        )
        nodes[node.node_id] = node

        relationship = CATEGORY_RELATIONSHIP.get(
            paper.primary_category, RelationshipType.RELATED_TO
        )
        if paper.primary_category == ContextCategory.REPLICATION and paper.has(
            ContextCategory.CONTRADICTORY
        ):
            relationship = RelationshipType.CONTRADICTS

        edge = KnowledgeEdge.create(
            seed_node.node_id,
            node.node_id,
            relationship,
            confidence=_edge_confidence(paper),
            evidence=paper.rationale[:400],
            source_ref=source_ref,
        )
        edges[edge.edge_id] = edge

    return GraphMutation(nodes=tuple(nodes.values()), edges=tuple(edges.values()))


def ingest_scientific_context(
    service: KnowledgeGraphService,
    context: ScientificContext,
    source_ref: str = "",
) -> dict:
    """Apply a context mutation through the given graph service."""
    mutation = build_graph_mutation(context, source_ref=source_ref)
    service.store.apply(mutation)
    stats = service.store.stats()
    return {
        "nodes_upserted": len(mutation.nodes),
        "edges_upserted": len(mutation.edges),
        "total_nodes": stats["total_nodes"],
        "total_edges": stats["total_edges"],
    }


# ── internals ────────────────────────────────────────────────────────────────


def _paper_metadata(paper: ContextPaper) -> dict:
    record = paper.paper
    return {
        "source_type": "scientific_context_paper",
        "primary_category": paper.primary_category.value,
        "categories": [category.value for category in paper.categories],
        "relevance": paper.relevance,
        "doi": record.doi or "",
        "year": record.year or "",
        "citation_count": record.citation_count if record.citation_count is not None else "",
        "providers": ",".join(paper.sources),
    }


def _edge_confidence(paper: ContextPaper) -> float:
    return round(min(0.95, 0.5 + 0.4 * max(0.0, min(1.0, paper.relevance))), 4)
