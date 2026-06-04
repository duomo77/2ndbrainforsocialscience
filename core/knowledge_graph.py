"""Typed semantic knowledge graph for long-lived cognitive memory."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _stable_id(prefix: str, *parts: str) -> str:
    normalized = "\x1f".join((part or "").strip().casefold() for part in parts)
    return f"{prefix}_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value and value.strip()))


class NodeType(str, Enum):
    SOURCE = "source"
    CONCEPT = "concept"
    METHOD = "method"
    QUESTION = "question"
    PROJECT = "project"
    INSIGHT = "insight"
    ENTITY = "entity"


class RelationshipType(str, Enum):
    RELATED_TO = "related_to"
    USES = "uses"
    USED_BY = "used_by"
    INSPIRED_BY = "inspired_by"
    DERIVED_FROM = "derived_from"
    EXTENDS = "extends"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    APPLIED_TO = "applied_to"
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"
    ASSOCIATED_WITH = "associated_with"


@dataclass(frozen=True)
class KnowledgeNode:
    node_id: str
    name: str
    node_type: NodeType
    description: str = ""
    aliases: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    importance_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        node_type: NodeType,
        *,
        description: str = "",
        aliases: Iterable[str] = (),
        source_refs: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> "KnowledgeNode":
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("node name is required")
        return cls(
            node_id=_stable_id("node", node_type.value, clean_name),
            name=clean_name,
            node_type=node_type,
            description=description.strip(),
            aliases=_unique(aliases),
            source_refs=_unique(source_refs),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class KnowledgeEdge:
    edge_id: str
    source: str
    target: str
    relationship: RelationshipType
    confidence: float = 0.8
    evidence: str = ""
    source_ref: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        source: str,
        target: str,
        relationship: RelationshipType,
        *,
        confidence: float = 0.8,
        evidence: str = "",
        source_ref: str = "",
    ) -> "KnowledgeEdge":
        if not source or not target:
            raise ValueError("edge endpoints are required")
        if source == target:
            raise ValueError("self-referential edges are not allowed")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("edge confidence must be between 0 and 1")
        return cls(
            edge_id=_stable_id("edge", source, target, relationship.value),
            source=source,
            target=target,
            relationship=relationship,
            confidence=confidence,
            evidence=evidence.strip(),
            source_ref=source_ref.strip(),
        )


@dataclass(frozen=True)
class GraphMutation:
    nodes: tuple[KnowledgeNode, ...] = ()
    edges: tuple[KnowledgeEdge, ...] = ()


@dataclass(frozen=True)
class IngestionReport:
    nodes_upserted: int
    edges_upserted: int
    total_nodes: int
    total_edges: int


class KnowledgeGraphStore:
    """Thread-safe JSON graph store with atomic, validated batch commits."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("unsupported semantic graph schema version")
        self._nodes = {
            raw["node_id"]: KnowledgeNode(
                **{**raw, "node_type": NodeType(raw["node_type"]), "aliases": tuple(raw.get("aliases", ())),
                   "source_refs": tuple(raw.get("source_refs", ()))}
            )
            for raw in data.get("nodes", [])
        }
        self._edges = {
            raw["edge_id"]: KnowledgeEdge(
                **{**raw, "relationship": RelationshipType(raw["relationship"])}
            )
            for raw in data.get("edges", [])
        }

    def _serialize(self, nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge]) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": _now(),
            "nodes": [asdict(nodes[key]) for key in sorted(nodes)],
            "edges": [asdict(edges[key]) for key in sorted(edges)],
        }

    def _save(self, nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(self._serialize(nodes, edges), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @staticmethod
    def _merge_node(existing: KnowledgeNode | None, incoming: KnowledgeNode) -> KnowledgeNode:
        if existing is None:
            return incoming
        if existing.node_type != incoming.node_type:
            raise ValueError(f"node type conflict for {incoming.name}")
        return replace(
            existing,
            description=incoming.description or existing.description,
            aliases=_unique((*existing.aliases, *incoming.aliases)),
            source_refs=_unique((*existing.source_refs, *incoming.source_refs)),
            updated_at=_now(),
            metadata={**existing.metadata, **incoming.metadata},
        )

    @staticmethod
    def _merge_edge(existing: KnowledgeEdge | None, incoming: KnowledgeEdge) -> KnowledgeEdge:
        if existing is None:
            return incoming
        return replace(
            existing,
            confidence=max(existing.confidence, incoming.confidence),
            evidence=incoming.evidence or existing.evidence,
            source_ref=incoming.source_ref or existing.source_ref,
            updated_at=_now(),
        )

    def apply(self, mutation: GraphMutation) -> None:
        with self._lock:
            next_nodes = dict(self._nodes)
            next_edges = dict(self._edges)
            for node in mutation.nodes:
                next_nodes[node.node_id] = self._merge_node(next_nodes.get(node.node_id), node)
            for edge in mutation.edges:
                if edge.source not in next_nodes:
                    raise ValueError(f"edge references unknown source: {edge.source}")
                if edge.target not in next_nodes:
                    raise ValueError(f"edge references unknown target: {edge.target}")
                next_edges[edge.edge_id] = self._merge_edge(next_edges.get(edge.edge_id), edge)
            next_nodes = self._with_importance(next_nodes, next_edges)
            self._save(next_nodes, next_edges)
            self._nodes, self._edges = next_nodes, next_edges

    @staticmethod
    def _with_importance(
        nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge]
    ) -> dict[str, KnowledgeNode]:
        degree = {node_id: 0 for node_id in nodes}
        confidence = {node_id: 0.0 for node_id in nodes}
        for edge in edges.values():
            degree[edge.source] += 1
            degree[edge.target] += 1
            confidence[edge.source] += edge.confidence
            confidence[edge.target] += edge.confidence
        return {
            node_id: replace(
                node,
                importance_score=round(
                    degree[node_id] + confidence[node_id] + min(len(node.source_refs), 5) * 0.25,
                    4,
                ),
            )
            for node_id, node in nodes.items()
        }

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        with self._lock:
            return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> KnowledgeEdge | None:
        with self._lock:
            return self._edges.get(edge_id)

    def rank_nodes(self, limit: int = 20, node_type: NodeType | None = None) -> list[KnowledgeNode]:
        with self._lock:
            nodes = [node for node in self._nodes.values() if node_type is None or node.node_type == node_type]
            return sorted(nodes, key=lambda node: (-node.importance_score, node.name.casefold()))[:max(limit, 0)]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_type = {node_type.value: 0 for node_type in NodeType}
            for node in self._nodes.values():
                by_type[node.node_type.value] += 1
            return {
                "total_nodes": len(self._nodes),
                "total_edges": len(self._edges),
                "nodes_by_type": by_type,
            }


class SemanticMarkdownExtractor:
    """Deterministic extraction layer for LLM-produced Obsidian Markdown."""

    _wikilink = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
    _question = re.compile(r"^\s*(?:[-*]\s*)?(.+\?)\s*$")
    _heading = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
    _relationship = re.compile(
        r"\b(related(?:\s+to)?|uses?|used\s+by|inspired\s+by|derived\s+from|extends?|"
        r"contradicts?|supports?|applied\s+to|depends\s+on|part\s+of|associated\s+with)\s*:",
        re.IGNORECASE,
    )
    _relation_map = {
        "related": RelationshipType.RELATED_TO,
        "related to": RelationshipType.RELATED_TO,
        "use": RelationshipType.USES,
        "uses": RelationshipType.USES,
        "used by": RelationshipType.USED_BY,
        "inspired by": RelationshipType.INSPIRED_BY,
        "derived from": RelationshipType.DERIVED_FROM,
        "extend": RelationshipType.EXTENDS,
        "extends": RelationshipType.EXTENDS,
        "contradict": RelationshipType.CONTRADICTS,
        "contradicts": RelationshipType.CONTRADICTS,
        "support": RelationshipType.SUPPORTS,
        "supports": RelationshipType.SUPPORTS,
        "applied to": RelationshipType.APPLIED_TO,
        "depends on": RelationshipType.DEPENDS_ON,
        "part of": RelationshipType.PART_OF,
        "associated with": RelationshipType.ASSOCIATED_WITH,
    }

    def extract(self, title: str, markdown: str, source_type: str, source_ref: str = "") -> GraphMutation:
        source = KnowledgeNode.create(
            title,
            NodeType.SOURCE,
            source_refs=(source_ref,),
            metadata={"source_type": source_type},
        )
        nodes: dict[str, KnowledgeNode] = {source.node_id: source}
        edges: dict[str, KnowledgeEdge] = {}
        section = ""

        for raw_line in (markdown or "").splitlines():
            heading = self._heading.match(raw_line)
            if heading:
                section = heading.group(1).casefold()
            links = _unique(self._wikilink.findall(raw_line))
            relation_match = self._relationship.search(raw_line)
            relationship = (
                self._relation_map[relation_match.group(1).casefold()]
                if relation_match else RelationshipType.RELATED_TO
            )
            for name in links:
                node_type = NodeType.METHOD if "method" in section else NodeType.CONCEPT
                node = KnowledgeNode.create(name, node_type, source_refs=(source_ref,))
                nodes[node.node_id] = node
                edge = KnowledgeEdge.create(
                    source.node_id,
                    node.node_id,
                    relationship,
                    confidence=0.9 if relation_match else 0.75,
                    evidence=raw_line.strip(),
                    source_ref=source_ref,
                )
                edges[edge.edge_id] = edge

            question = self._question.match(raw_line)
            if question and ("question" in section or not links):
                node = KnowledgeNode.create(question.group(1), NodeType.QUESTION, source_refs=(source_ref,))
                nodes[node.node_id] = node
                edge = KnowledgeEdge.create(
                    node.node_id,
                    source.node_id,
                    RelationshipType.DERIVED_FROM,
                    confidence=0.85,
                    evidence=raw_line.strip(),
                    source_ref=source_ref,
                )
                edges[edge.edge_id] = edge

        return GraphMutation(nodes=tuple(nodes.values()), edges=tuple(edges.values()))


class KnowledgeGraphService:
    def __init__(self, store: KnowledgeGraphStore, extractor: SemanticMarkdownExtractor | None = None):
        self.store = store
        self.extractor = extractor or SemanticMarkdownExtractor()

    def ingest_markdown(
        self, title: str, markdown: str, source_type: str, source_ref: str = ""
    ) -> IngestionReport:
        mutation = self.extractor.extract(title, markdown, source_type, source_ref)
        self.store.apply(mutation)
        stats = self.store.stats()
        return IngestionReport(
            nodes_upserted=len(mutation.nodes),
            edges_upserted=len(mutation.edges),
            total_nodes=stats["total_nodes"],
            total_edges=stats["total_edges"],
        )


_service: KnowledgeGraphService | None = None
_service_lock = threading.Lock()


def get_knowledge_graph_service(data_dir: Path | None = None) -> KnowledgeGraphService:
    global _service
    with _service_lock:
        if _service is None:
            root = data_dir or (Path.home() / ".ros_memory")
            _service = KnowledgeGraphService(KnowledgeGraphStore(root / "semantic_knowledge_graph.json"))
        return _service

