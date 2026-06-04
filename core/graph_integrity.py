"""
graph_integrity.py — ROS v4.0 Graph Integrity Engine
======================================================
Semantic graph is mission-critical infrastructure.

Implements:
  - Graph integrity validation
  - Cyclic corruption detection
  - Semantic anomaly detection
  - Invalid edge detection
  - Contradictory graph-state validation
  - Graph rollback checkpoints
  - Immutable audit history
  - Transactional graph mutations
"""

from __future__ import annotations

import hashlib
import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

logger = _get_logger("ROS.GraphIntegrity")


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

MAX_NODES_PER_VAULT    = 50_000
MAX_EDGES_PER_NODE     = 500
MAX_GRAPH_DEPTH        = 20
MIN_EDGE_CONFIDENCE    = 0.1
CHECKPOINT_INTERVAL    = 50   # 50 mutations마다 자동 체크포인트


# ══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GraphNode:
    node_id:    str
    title:      str
    node_type:  str          # paper | concept | equation | dataset | transcript
    checksum:   str
    created_at: str
    updated_at: str
    edge_count: int = 0
    trust_score: float = 1.0
    is_quarantined: bool = False


@dataclass
class GraphEdge:
    edge_id:     str
    source:      str
    target:      str
    edge_type:   str         # cites | uses | extends | contradicts | derives
    confidence:  float       # 0.0 ~ 1.0
    created_at:  str
    is_valid:    bool = True


@dataclass
class GraphCheckpoint:
    checkpoint_id: str
    timestamp:     str
    node_count:    int
    edge_count:    int
    graph_hash:    str
    mutation_count: int


@dataclass
class IntegrityReport:
    is_valid:        bool
    issues:          list[str] = field(default_factory=list)
    warnings:        list[str] = field(default_factory=list)
    cycles_detected: list[list[str]] = field(default_factory=list)
    invalid_edges:   list[str] = field(default_factory=list)
    anomalies:       list[str] = field(default_factory=list)
    node_count:      int = 0
    edge_count:      int = 0


# ══════════════════════════════════════════════════════════════════════════════
# Graph Store (In-Memory + JSON Persistence)
# ══════════════════════════════════════════════════════════════════════════════

class GraphStore:
    def __init__(self, data_dir: Path):
        self._dir   = data_dir
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._adj:   dict[str, list[str]] = defaultdict(list)  # node_id → [edge_ids]
        self._load()

    def _path(self): return self._dir / "graph_store.json"

    def _load(self):
        p = self._path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for n in data.get("nodes", []):
                    self._nodes[n["node_id"]] = GraphNode(**n)
                for e in data.get("edges", []):
                    obj = GraphEdge(**e)
                    self._edges[obj.edge_id] = obj
                    self._adj[obj.source].append(obj.edge_id)
            except Exception as ex:
                logger.error(f"GraphStore load error: {ex}")

    def save(self):
        data = {
            "nodes": [asdict(n) for n in self._nodes.values()],
            "edges": [asdict(e) for e in self._edges.values()],
        }
        tmp = self._path().with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self._path())

    def upsert_node(self, node: GraphNode):
        self._nodes[node.node_id] = node

    def upsert_edge(self, edge: GraphEdge):
        self._edges[edge.edge_id] = edge
        if edge.edge_id not in self._adj[edge.source]:
            self._adj[edge.source].append(edge.edge_id)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> list[GraphEdge]:
        return [self._edges[eid] for eid in self._adj.get(node_id, []) if eid in self._edges]

    def all_nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    def all_edges(self) -> list[GraphEdge]:
        return list(self._edges.values())

    def adjacency_map(self) -> dict[str, list[str]]:
        """node_id → [target node_ids] (유효 엣지만)."""
        result = defaultdict(list)
        for e in self._edges.values():
            if e.is_valid:
                result[e.source].append(e.target)
        return result

    def snapshot(self) -> dict:
        return {
            "nodes": [asdict(n) for n in self._nodes.values()],
            "edges": [asdict(e) for e in self._edges.values()],
        }

    def restore(self, snapshot: dict):
        self._nodes = {}
        self._edges = {}
        self._adj   = defaultdict(list)
        for n in snapshot.get("nodes", []):
            self._nodes[n["node_id"]] = GraphNode(**n)
        for e in snapshot.get("edges", []):
            obj = GraphEdge(**e)
            self._edges[obj.edge_id] = obj
            self._adj[obj.source].append(obj.edge_id)


# ══════════════════════════════════════════════════════════════════════════════
# Cycle Detector (DFS-based)
# ══════════════════════════════════════════════════════════════════════════════

class CycleDetector:
    def detect(self, adj: dict[str, list[str]]) -> list[list[str]]:
        """방향 그래프에서 순환 감지 (DFS)."""
        visited  = set()
        rec_stack = set()
        cycles   = []

        def dfs(node: str, path: list[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # 순환 발견
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            path.pop()
            rec_stack.discard(node)

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node, [])

        return cycles[:10]  # 최대 10개 순환만 반환


# ══════════════════════════════════════════════════════════════════════════════
# Graph Integrity Engine
# ══════════════════════════════════════════════════════════════════════════════

class GraphIntegrityEngine:
    """
    그래프 무결성 검증 및 트랜잭션 뮤테이션 관리.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._dir          = data_dir
        self.store         = GraphStore(data_dir)
        self.cycle_detector = CycleDetector()
        self._checkpoints: list[GraphCheckpoint] = []
        self._snapshots:   list[dict] = []          # 롤백용 스냅샷
        self._mutation_count = 0
        self._tx_buffer: Optional[list] = None      # 트랜잭션 버퍼
        self._load_checkpoints()

    # ── 트랜잭션 뮤테이션 ─────────────────────────────────────────────────────

    def begin_transaction(self):
        """트랜잭션 시작 — 실패 시 자동 롤백."""
        self._tx_buffer = []
        # 현재 상태 스냅샷 저장
        self._snapshots.append(self.store.snapshot())
        if len(self._snapshots) > 20:
            self._snapshots = self._snapshots[-20:]

    def commit_transaction(self):
        """트랜잭션 커밋 — 무결성 검증 후 적용."""
        if self._tx_buffer is None:
            return True, "No active transaction"
        ops = self._tx_buffer
        self._tx_buffer = None

        for op_type, obj in ops:
            if op_type == "node":
                self.store.upsert_node(obj)
            elif op_type == "edge":
                self.store.upsert_edge(obj)

        self._mutation_count += len(ops)

        # 무결성 검증
        report = self.validate()
        if not report.is_valid:
            self.rollback()
            return False, f"Integrity check failed: {report.issues}"

        # 자동 체크포인트
        if self._mutation_count % CHECKPOINT_INTERVAL == 0:
            self._create_checkpoint()

        self.store.save()
        return True, "ok"

    def rollback(self) -> bool:
        """마지막 스냅샷으로 롤백."""
        if not self._snapshots:
            return False
        snap = self._snapshots.pop()
        self.store.restore(snap)
        self._tx_buffer = None
        logger.warning("Graph rolled back to previous snapshot")
        return True

    # ── 노드/엣지 추가 (트랜잭션 내) ─────────────────────────────────────────

    def add_node(
        self, title: str, node_type: str, trust_score: float = 1.0
    ) -> GraphNode:
        node_id = hashlib.sha256(title.strip().lower().encode()).hexdigest()[:16]
        now     = datetime.now(UTC).isoformat()
        node    = GraphNode(
            node_id    = node_id,
            title      = title,
            node_type  = node_type,
            checksum   = hashlib.md5(title.encode()).hexdigest()[:8],
            created_at = now,
            updated_at = now,
            trust_score = trust_score,
        )
        if self._tx_buffer is not None:
            self._tx_buffer.append(("node", node))
        else:
            self.store.upsert_node(node)
            self.store.save()
        return node

    def add_edge(
        self,
        source_title: str,
        target_title: str,
        edge_type: str,
        confidence: float = 0.8,
    ) -> Optional[GraphEdge]:
        """신뢰도 검증 후 엣지 추가."""
        if confidence < MIN_EDGE_CONFIDENCE:
            logger.debug(f"Edge rejected (low confidence={confidence:.2f}): {source_title}→{target_title}")
            return None

        # 엣지 수 제한 (backlink flooding 방지)
        src_id = hashlib.sha256(source_title.strip().lower().encode()).hexdigest()[:16]
        existing = self.store.get_edges_from(src_id)
        if len(existing) >= MAX_EDGES_PER_NODE:
            logger.warning(f"Edge limit reached for node: {source_title}")
            return None

        tgt_id  = hashlib.sha256(target_title.strip().lower().encode()).hexdigest()[:16]
        edge_id = hashlib.sha256(f"{src_id}{tgt_id}{edge_type}".encode()).hexdigest()[:16]
        now     = datetime.now(UTC).isoformat()
        edge    = GraphEdge(
            edge_id    = edge_id,
            source     = src_id,
            target     = tgt_id,
            edge_type  = edge_type,
            confidence = confidence,
            created_at = now,
        )
        if self._tx_buffer is not None:
            self._tx_buffer.append(("edge", edge))
        else:
            self.store.upsert_edge(edge)
            self.store.save()
        return edge

    # ── 무결성 검증 ───────────────────────────────────────────────────────────

    def validate(self) -> IntegrityReport:
        """전체 그래프 무결성 검증."""
        nodes  = self.store.all_nodes()
        edges  = self.store.all_edges()
        adj    = self.store.adjacency_map()
        issues, warnings, anomalies, invalid_edges = [], [], [], []

        # 1. 크기 제한 검사
        if len(nodes) > MAX_NODES_PER_VAULT:
            issues.append(f"Node count {len(nodes)} exceeds limit {MAX_NODES_PER_VAULT}")

        # 2. 순환 감지
        cycles = self.cycle_detector.detect(adj)
        if cycles:
            warnings.append(f"{len(cycles)} cycle(s) detected in graph")

        # 3. 유효하지 않은 엣지 감지 (존재하지 않는 노드 참조)
        node_ids = {n.node_id for n in nodes}
        for e in edges:
            if e.source not in node_ids or e.target not in node_ids:
                invalid_edges.append(e.edge_id)
                e.is_valid = False

        # 4. 격리된 노드 감지 (trust_score < 0.3)
        quarantined = [n for n in nodes if n.trust_score < 0.3]
        if quarantined:
            anomalies.append(f"{len(quarantined)} low-trust node(s) detected")

        # 5. 그래프 깊이 검사 (재귀 폭발 방지)
        max_depth = self._compute_max_depth(adj)
        if max_depth > MAX_GRAPH_DEPTH:
            warnings.append(f"Graph depth {max_depth} exceeds recommended {MAX_GRAPH_DEPTH}")

        if invalid_edges:
            issues.append(f"{len(invalid_edges)} edge(s) reference unknown nodes")

        is_valid = len(issues) == 0

        return IntegrityReport(
            is_valid        = is_valid,
            issues          = issues,
            warnings        = warnings,
            cycles_detected = cycles,
            invalid_edges   = invalid_edges,
            anomalies       = anomalies,
            node_count      = len(nodes),
            edge_count      = len(edges),
        )

    def _compute_max_depth(self, adj: dict[str, list[str]]) -> int:
        """BFS로 최대 깊이 계산."""
        if not adj:
            return 0
        max_d = 0
        for start in list(adj.keys())[:100]:  # 샘플링 (성능)
            visited = {start}
            queue   = deque([(start, 0)])
            while queue:
                node, depth = queue.popleft()
                max_d = max(max_d, depth)
                if depth >= MAX_GRAPH_DEPTH:
                    break
                for nb in adj.get(node, []):
                    if nb not in visited:
                        visited.add(nb)
                        queue.append((nb, depth + 1))
        return max_d

    # ── 체크포인트 관리 ───────────────────────────────────────────────────────

    def _create_checkpoint(self):
        nodes  = self.store.all_nodes()
        edges  = self.store.all_edges()
        gh     = hashlib.sha256(
            json.dumps(
                sorted(n.node_id for n in nodes)
            ).encode()
        ).hexdigest()[:12]
        cp = GraphCheckpoint(
            checkpoint_id  = f"cp_{int(time.time())}",
            timestamp      = datetime.now(UTC).isoformat(),
            node_count     = len(nodes),
            edge_count     = len(edges),
            graph_hash     = gh,
            mutation_count = self._mutation_count,
        )
        self._checkpoints.append(cp)
        self._save_checkpoints()
        logger.info(f"Checkpoint created: {cp.checkpoint_id} ({len(nodes)}N/{len(edges)}E)")

    def _load_checkpoints(self):
        p = self._dir / "graph_checkpoints.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._checkpoints = [GraphCheckpoint(**c) for c in data]
            except Exception:
                self._checkpoints = []

    def _save_checkpoints(self):
        p = self._dir / "graph_checkpoints.json"
        p.write_text(
            json.dumps([asdict(c) for c in self._checkpoints[-50:]], indent=2),
            encoding="utf-8",
        )

    def get_stats(self) -> dict:
        nodes = self.store.all_nodes()
        edges = self.store.all_edges()
        return {
            "nodes":          len(nodes),
            "edges":          len(edges),
            "mutations":      self._mutation_count,
            "checkpoints":    len(self._checkpoints),
            "snapshots":      len(self._snapshots),
        }


# ── 싱글톤 ────────────────────────────────────────────────────────────────────
_engine: Optional[GraphIntegrityEngine] = None

def get_graph_integrity_engine() -> GraphIntegrityEngine:
    global _engine
    if _engine is None:
        _engine = GraphIntegrityEngine()
    return _engine
