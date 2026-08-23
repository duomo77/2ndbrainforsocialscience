"""
graph_migration.py — Legacy → Typed Graph Migration (audit C-02, Stage 1)
==========================================================================
One-time, idempotent migration of the legacy concept graph
(``~/.ros_memory/knowledge_graph.json``) into the typed semantic knowledge
graph (``KnowledgeGraphService``), which the audit designates as the
canonical store going forward.

Design constraints:
  - Idempotent: a sentinel file records completion; re-runs are no-ops.
    ``force=True`` re-migrates safely (typed node/edge IDs are stable, so
    re-application upserts instead of duplicating).
  - Non-destructive: the legacy file is never modified or deleted; it stays
    readable until all consumers are rewired (later stages of C-02).
  - Fail-isolated: callers wrap this in try/except — migration problems must
    never block an analysis run.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from core import memory
from core.knowledge_graph import (
    GraphMutation,
    KnowledgeEdge,
    KnowledgeGraphService,
    KnowledgeNode,
    NodeType,
    RelationshipType,
)

MIGRATION_SOURCE_REF = "legacy-migration"
_LEGACY_TYPE_MAP = {
    "note": NodeType.SOURCE,
    "concept": NodeType.CONCEPT,
}
_EXPLICIT_CONFIDENCE = 0.6   # migrated edges carry no provenance → lower trust
_IMPLICIT_CONFIDENCE = 0.5


def _default_sentinel_path() -> Path:
    return memory.MEMORY_DIR / ".legacy_graph_migrated.json"


def migrate_legacy_to_typed(
    service: Optional[KnowledgeGraphService] = None,
    sentinel_path: Optional[Path] = None,
    force: bool = False,
) -> dict:
    """Migrate the legacy graph into the typed store.

    Returns a summary dict: ``{"status", "nodes", "edges", ...}``.
    """
    sentinel = sentinel_path or _default_sentinel_path()
    if sentinel.exists() and not force:
        return {"status": "skipped", "reason": "already migrated"}

    legacy = memory.load_graph()
    if not isinstance(legacy, dict) or not legacy:
        _write_sentinel(sentinel, 0, 0)
        return {"status": "empty", "nodes": 0, "edges": 0}

    if service is None:
        from core.knowledge_graph import get_knowledge_graph_service

        service = get_knowledge_graph_service()

    nodes: dict[str, KnowledgeNode] = {}
    edges: dict[str, KnowledgeEdge] = {}

    for title, record in legacy.items():
        if not str(title).strip():
            continue
        record = record if isinstance(record, dict) else {}
        node_type = _LEGACY_TYPE_MAP.get(record.get("type", "concept"), NodeType.CONCEPT)
        node = KnowledgeNode.create(
            str(title),
            node_type,
            source_refs=(MIGRATION_SOURCE_REF,),
            metadata={
                "migrated_from": "legacy_knowledge_graph",
                "note_path": record.get("note_path", ""),
                "tags": record.get("tags", []),
            },
        )
        nodes[node.node_id] = node

        source_id = node.node_id
        for targets, confidence in (
            (record.get("edges", []), _EXPLICIT_CONFIDENCE),
            (record.get("implicit_edges", []), _IMPLICIT_CONFIDENCE),
        ):
            for target in targets or []:
                target_name = str(target).strip()
                if not target_name or target_name == title:
                    continue
                target_node = _ensure_node(nodes, target_name, legacy)
                edge = KnowledgeEdge.create(
                    source_id,
                    target_node.node_id,
                    RelationshipType.RELATED_TO,
                    confidence=confidence,
                    evidence="migrated from legacy knowledge_graph.json",
                    source_ref=MIGRATION_SOURCE_REF,
                )
                edges[edge.edge_id] = edge

    service.store.apply(GraphMutation(nodes=tuple(nodes.values()), edges=tuple(edges.values())))
    _write_sentinel(sentinel, len(nodes), len(edges))
    return {"status": "migrated", "nodes": len(nodes), "edges": len(edges)}


def _ensure_node(nodes: dict, name: str, legacy: dict) -> KnowledgeNode:
    """Reuse an already-created node, or create a placeholder for the target."""
    for existing in nodes.values():
        if existing.name == name:
            return existing
    record = legacy.get(name) if isinstance(legacy.get(name), dict) else {}
    node_type = _LEGACY_TYPE_MAP.get(record.get("type", "concept"), NodeType.CONCEPT)
    node = KnowledgeNode.create(
        name,
        node_type,
        source_refs=(MIGRATION_SOURCE_REF,),
        metadata={"migrated_from": "legacy_knowledge_graph"},
    )
    nodes[node.node_id] = node
    return node


def _write_sentinel(sentinel: Path, node_count: int, edge_count: int) -> None:
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(
        json.dumps(
            {
                "migrated_at": datetime.now(UTC).isoformat(),
                "nodes": node_count,
                "edges": edge_count,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
