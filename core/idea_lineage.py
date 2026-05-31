"""
idea_lineage.py — Idea Lineage Tracking System (ROS v3.0)
==========================================================
아이디어 계보 추적 - git commit graph 방식의 진화 추적.

idea A
→ modified by note B
→ formalized in note C
→ became model D
→ became paper E

특징:
- 불변 계보 ID (immutable lineage IDs)
- 의미론적 차이 추적 (semantic diffs)
- 그래프 재생 (graph replay)
- 역사적 재구성 (historical reconstruction)
- 분기 연구 가설 (branching research hypotheses)
"""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


# ── 변환 유형 ─────────────────────────────────────────────────────────────────

class TransformationType(str, Enum):
    ORIGIN       = "origin"        # 최초 생성
    REFINEMENT   = "refinement"    # 개념 정제
    FORMALIZATION = "formalization" # 수식화
    EXTENSION    = "extension"     # 확장
    CONTRADICTION = "contradiction" # 반박/수정
    SYNTHESIS    = "synthesis"     # 합성
    APPLICATION  = "application"   # 응용
    GENERALIZATION = "generalization" # 일반화
    SPECIALIZATION = "specialization" # 특수화
    ABANDONED    = "abandoned"     # 폐기


TRANSFORM_ICONS = {
    TransformationType.ORIGIN:         "🌱",
    TransformationType.REFINEMENT:     "✏️",
    TransformationType.FORMALIZATION:  "📐",
    TransformationType.EXTENSION:      "🔭",
    TransformationType.CONTRADICTION:  "⚡",
    TransformationType.SYNTHESIS:      "🔗",
    TransformationType.APPLICATION:    "🔧",
    TransformationType.GENERALIZATION: "🌐",
    TransformationType.SPECIALIZATION: "🔬",
    TransformationType.ABANDONED:      "🗑️",
}


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class LineageNode:
    """아이디어 계보 그래프의 단일 노드."""
    lineage_id:    str           # 불변 ID
    title:         str
    content_hash:  str           # 내용 체크섬
    created_at:    str
    parent_ids:    list[str] = field(default_factory=list)
    child_ids:     list[str] = field(default_factory=list)
    transform_type: str = TransformationType.ORIGIN.value
    transform_desc: str = ""
    semantic_diff:  str = ""     # 이전 버전과의 의미론적 차이
    branch_label:   str = ""     # 분기 이름 (예: "IV approach", "DML approach")
    is_abandoned:   bool = False
    tags:           list[str] = field(default_factory=list)
    note_stage:     str = "fleeting_note"


@dataclass
class LineageBranch:
    """연구 가설 분기."""
    branch_id:   str
    name:        str
    root_id:     str             # 분기 시작점
    description: str
    created_at:  str
    is_active:   bool = True
    nodes:       list[str] = field(default_factory=list)


# ── Lineage Store ─────────────────────────────────────────────────────────────

class LineageStore:
    """아이디어 계보 그래프 영속화."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir  = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._nodes_path   = self._dir / "lineage_nodes.json"
        self._branches_path = self._dir / "lineage_branches.json"
        self._nodes: dict[str, dict]    = {}
        self._branches: dict[str, dict] = {}
        self._load()

    def _load(self):
        for path, attr in [(self._nodes_path, "_nodes"), (self._branches_path, "_branches")]:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        setattr(self, attr, json.load(f))
                except Exception:
                    setattr(self, attr, {})

    def _save(self):
        for path, attr in [(self._nodes_path, "_nodes"), (self._branches_path, "_branches")]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(getattr(self, attr), f, ensure_ascii=False, indent=2)

    def add_node(self, node: LineageNode):
        self._nodes[node.lineage_id] = asdict(node)
        self._save()

    def get_node(self, lineage_id: str) -> Optional[LineageNode]:
        d = self._nodes.get(lineage_id)
        return LineageNode(**d) if d else None

    def find_by_title(self, title: str) -> Optional[LineageNode]:
        for d in self._nodes.values():
            if d["title"] == title:
                return LineageNode(**d)
        return None

    def all_nodes(self) -> list[LineageNode]:
        return [LineageNode(**d) for d in self._nodes.values()]

    def add_branch(self, branch: LineageBranch):
        self._branches[branch.branch_id] = asdict(branch)
        self._save()

    def all_branches(self) -> list[LineageBranch]:
        return [LineageBranch(**d) for d in self._branches.values()]

    def update_node(self, node: LineageNode):
        self._nodes[node.lineage_id] = asdict(node)
        self._save()


# ── Lineage Engine ────────────────────────────────────────────────────────────

class IdeaLineageEngine:
    """
    아이디어 계보 추적 엔진.
    git commit graph 방식으로 아이디어 진화를 추적.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.store = LineageStore(data_dir)

    def _make_lineage_id(self, title: str, timestamp: str) -> str:
        """불변 계보 ID 생성."""
        key = f"{title.strip().lower()}|{timestamp}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _content_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def register_idea(
        self,
        title: str,
        content: str,
        parent_titles: list[str] = None,
        transform_type: TransformationType = TransformationType.ORIGIN,
        transform_desc: str = "",
        branch_label: str = "",
        tags: list[str] = None,
        note_stage: str = "fleeting_note",
    ) -> LineageNode:
        """새 아이디어 노드 등록."""
        now = datetime.utcnow().isoformat()
        lineage_id = self._make_lineage_id(title, now)

        # 부모 노드 ID 해석
        parent_ids = []
        for pt in (parent_titles or []):
            parent = self.store.find_by_title(pt)
            if parent:
                parent_ids.append(parent.lineage_id)

        # 의미론적 차이 계산
        semantic_diff = ""
        if parent_ids:
            parent = self.store.get_node(parent_ids[0])
            if parent:
                semantic_diff = self._compute_semantic_diff(
                    parent.title, title, transform_type
                )

        node = LineageNode(
            lineage_id     = lineage_id,
            title          = title,
            content_hash   = self._content_hash(content),
            created_at     = now,
            parent_ids     = parent_ids,
            transform_type = transform_type.value,
            transform_desc = transform_desc or transform_type.value,
            semantic_diff  = semantic_diff,
            branch_label   = branch_label,
            tags           = tags or [],
            note_stage     = note_stage,
        )

        # 부모 노드에 자식 등록
        for pid in parent_ids:
            parent_node = self.store.get_node(pid)
            if parent_node and lineage_id not in parent_node.child_ids:
                parent_node.child_ids.append(lineage_id)
                self.store.update_node(parent_node)

        self.store.add_node(node)
        return node

    def _compute_semantic_diff(
        self, parent_title: str, child_title: str, transform: TransformationType
    ) -> str:
        """의미론적 차이 설명 생성."""
        templates = {
            TransformationType.REFINEMENT:    f'"{parent_title}" → 개념 정제 → "{child_title}"',
            TransformationType.FORMALIZATION: f'"{parent_title}" → 수식화 → "{child_title}"',
            TransformationType.EXTENSION:     f'"{parent_title}" → 확장 → "{child_title}"',
            TransformationType.SYNTHESIS:     f'"{parent_title}" + 다른 개념 → 합성 → "{child_title}"',
            TransformationType.APPLICATION:   f'"{parent_title}" → 응용 → "{child_title}"',
            TransformationType.GENERALIZATION: f'"{parent_title}" → 일반화 → "{child_title}"',
        }
        return templates.get(transform, f'"{parent_title}" → "{child_title}"')

    def create_branch(
        self, root_title: str, branch_name: str, description: str
    ) -> Optional[LineageBranch]:
        """연구 가설 분기 생성."""
        root = self.store.find_by_title(root_title)
        if not root:
            return None
        branch_id = hashlib.sha256(f"{root_title}|{branch_name}".encode()).hexdigest()[:12]
        branch = LineageBranch(
            branch_id   = branch_id,
            name        = branch_name,
            root_id     = root.lineage_id,
            description = description,
            created_at  = datetime.utcnow().isoformat(),
            nodes       = [root.lineage_id],
        )
        self.store.add_branch(branch)
        return branch

    def get_ancestry_chain(self, title: str, max_depth: int = 10) -> list[LineageNode]:
        """특정 노트의 조상 체인 반환 (최신 → 최초)."""
        node = self.store.find_by_title(title)
        if not node:
            return []
        chain = [node]
        visited = {node.lineage_id}
        depth = 0
        while node.parent_ids and depth < max_depth:
            parent = self.store.get_node(node.parent_ids[0])
            if not parent or parent.lineage_id in visited:
                break
            chain.append(parent)
            visited.add(parent.lineage_id)
            node = parent
            depth += 1
        return chain

    def get_descendant_tree(self, title: str, max_depth: int = 5) -> dict:
        """특정 노트의 후손 트리 반환."""
        node = self.store.find_by_title(title)
        if not node:
            return {}

        def _build_tree(n: LineageNode, depth: int) -> dict:
            if depth >= max_depth:
                return {"title": n.title, "children": []}
            children = []
            for cid in n.child_ids:
                child = self.store.get_node(cid)
                if child:
                    children.append(_build_tree(child, depth + 1))
            return {
                "title":    n.title,
                "stage":    n.note_stage,
                "transform": n.transform_type,
                "children": children,
            }

        return _build_tree(node, 0)

    def format_lineage_markdown(self, title: str) -> str:
        """계보를 Markdown 형식으로 포맷."""
        chain = self.get_ancestry_chain(title)
        if not chain:
            return ""

        lines = ["\n## 🧬 Idea Lineage\n"]
        for i, node in enumerate(reversed(chain)):
            icon = TRANSFORM_ICONS.get(TransformationType(node.transform_type), "→")
            indent = "  " * i
            if i == 0:
                lines.append(f"{indent}{icon} **{node.title}** _(origin)_")
            else:
                lines.append(f"{indent}↓ `{node.transform_type}`")
                lines.append(f"{indent}{icon} **{node.title}**")
            if node.semantic_diff:
                lines.append(f"{indent}  _{node.semantic_diff}_")

        # 후손 표시
        desc_tree = self.get_descendant_tree(title, max_depth=3)
        if desc_tree.get("children"):
            lines.append("\n### Descendants")
            lines.append(self._tree_to_md(desc_tree, 0))

        return "\n".join(lines)

    def _tree_to_md(self, tree: dict, depth: int) -> str:
        indent = "  " * depth
        lines  = [f"{indent}- [[{tree['title']}]] `{tree.get('stage','')}`"]
        for child in tree.get("children", []):
            lines.append(self._tree_to_md(child, depth + 1))
        return "\n".join(lines)

    def get_abandoned_branches(self) -> list[LineageNode]:
        """폐기된 아이디어 분기 반환."""
        return [n for n in self.store.all_nodes() if n.is_abandoned]

    def get_graph_data(self) -> dict:
        """그래프 시각화용 데이터 반환."""
        nodes = []
        edges = []
        for n in self.store.all_nodes():
            nodes.append({
                "id":    n.lineage_id,
                "label": n.title[:40],
                "stage": n.note_stage,
                "transform": n.transform_type,
            })
            for cid in n.child_ids:
                edges.append({
                    "source": n.lineage_id,
                    "target": cid,
                    "type":   n.transform_type,
                })
        return {"nodes": nodes, "edges": edges}


# ── 싱글톤 접근 ───────────────────────────────────────────────────────────────
_engine: Optional[IdeaLineageEngine] = None

def get_lineage_engine() -> IdeaLineageEngine:
    global _engine
    if _engine is None:
        _engine = IdeaLineageEngine()
    return _engine
