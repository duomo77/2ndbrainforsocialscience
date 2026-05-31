"""
research_tension.py — Research Tension Detection & Graph DB (ROS v3.0)
=======================================================================
메타 연구 추론 엔진 + 통합 지식 그래프 DB.

감지 대상:
- 구조적 엄밀성 vs 실증적 실행 가능성
- 해석 가능성 vs 예측력
- 식별 강도 vs 외부 타당성
- 이론적 우아함 vs 계산 가능성
- DSGE 규율 vs 축약형 유연성

출력:
- 긴장 보고서 (tension reports)
- 개념적 병목 경보 (conceptual bottleneck alerts)
- 숨겨진 가정 맵 (hidden assumption maps)
- 방법론적 위험 경고 (methodological risk warnings)
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


# ── 긴장 유형 ─────────────────────────────────────────────────────────────────

class TensionType(str, Enum):
    RIGOR_VS_TRACTABILITY   = "rigor_vs_tractability"
    INTERPRET_VS_PREDICT    = "interpretability_vs_prediction"
    IDENTIFICATION_VS_EV    = "identification_vs_external_validity"
    ELEGANCE_VS_COMPUTATION = "elegance_vs_computation"
    DSGE_VS_REDUCED         = "dsge_vs_reduced_form"
    THEORY_VS_DATA          = "theory_vs_data"
    INTERNAL_VS_EXTERNAL    = "internal_vs_external_validity"
    EFFICIENCY_VS_ROBUSTNESS = "efficiency_vs_robustness"
    MICRO_VS_MACRO          = "micro_vs_macro_foundations"
    SHORT_VS_LONG_RUN       = "short_vs_long_run"


TENSION_DESCRIPTIONS = {
    TensionType.RIGOR_VS_TRACTABILITY:
        "구조적 엄밀성 vs 실증적 실행 가능성: 이론적으로 완전한 모델이 추정 불가능할 수 있음",
    TensionType.INTERPRET_VS_PREDICT:
        "해석 가능성 vs 예측력: ML 모델의 블랙박스 vs 경제학적 해석 가능성",
    TensionType.IDENTIFICATION_VS_EV:
        "식별 강도 vs 외부 타당성: 강한 식별이 특수한 국지적 효과만 추정할 수 있음",
    TensionType.ELEGANCE_VS_COMPUTATION:
        "이론적 우아함 vs 계산 가능성: 닫힌 형태 해가 없는 구조 모델",
    TensionType.DSGE_VS_REDUCED:
        "DSGE 규율 vs 축약형 유연성: 루카스 비판 vs 실증적 유연성",
    TensionType.THEORY_VS_DATA:
        "이론 vs 데이터: 이론적 예측과 실증 결과의 불일치",
    TensionType.INTERNAL_VS_EXTERNAL:
        "내부 타당성 vs 외부 타당성: 인과 식별의 엄밀성이 일반화를 제한",
    TensionType.EFFICIENCY_VS_ROBUSTNESS:
        "효율성 vs 강건성: 효율적 추정량이 가정 위반에 취약",
    TensionType.MICRO_VS_MACRO:
        "미시적 기초 vs 거시 집계: 개인 행동의 집계 문제",
    TensionType.SHORT_VS_LONG_RUN:
        "단기 vs 장기 효과: 동태적 효과와 정태적 추정의 불일치",
}

TENSION_ICONS = {
    TensionType.RIGOR_VS_TRACTABILITY:   "⚖️",
    TensionType.INTERPRET_VS_PREDICT:    "🔍",
    TensionType.IDENTIFICATION_VS_EV:    "🎯",
    TensionType.ELEGANCE_VS_COMPUTATION: "💻",
    TensionType.DSGE_VS_REDUCED:         "🏛️",
    TensionType.THEORY_VS_DATA:          "📊",
    TensionType.INTERNAL_VS_EXTERNAL:    "🌐",
    TensionType.EFFICIENCY_VS_ROBUSTNESS: "🛡️",
    TensionType.MICRO_VS_MACRO:          "🔬",
    TensionType.SHORT_VS_LONG_RUN:       "⏱️",
}

# 긴장 감지 패턴
TENSION_PATTERNS = [
    {
        "type": TensionType.IDENTIFICATION_VS_EV,
        "side_a": ["LATE", "local average treatment effect", "complier"],
        "side_b": ["policy implication", "external validity", "generalization", "ATE"],
        "alert": "LATE는 complier에게만 적용됨 — 정책 일반화 주의",
    },
    {
        "type": TensionType.RIGOR_VS_TRACTABILITY,
        "side_a": ["structural model", "DSGE", "equilibrium"],
        "side_b": ["computational burden", "approximation", "linearization"],
        "alert": "구조 모델의 계산 부담 — 근사 방법 사용 시 이론적 엄밀성 손실",
    },
    {
        "type": TensionType.INTERPRET_VS_PREDICT,
        "side_a": ["random forest", "neural network", "XGBoost", "black box"],
        "side_b": ["coefficient", "marginal effect", "economic interpretation"],
        "alert": "ML 예측력 vs 경제학적 해석 가능성 충돌",
    },
    {
        "type": TensionType.DSGE_VS_REDUCED,
        "side_a": ["DSGE", "structural VAR", "Lucas critique"],
        "side_b": ["reduced form", "local projection", "VAR", "regression"],
        "alert": "DSGE 구조 가정이 축약형 추정과 충돌 가능",
    },
    {
        "type": TensionType.EFFICIENCY_VS_ROBUSTNESS,
        "side_a": ["efficient", "MLE", "GLS", "optimal"],
        "side_b": ["robust", "heteroskedasticity", "misspecification", "HAC"],
        "alert": "효율적 추정량이 모델 오명세에 취약",
    },
    {
        "type": TensionType.SHORT_VS_LONG_RUN,
        "side_a": ["short run", "immediate effect", "impact"],
        "side_b": ["long run", "dynamic effect", "persistence", "adjustment"],
        "alert": "단기 효과 추정이 장기 동태를 포착하지 못할 수 있음",
    },
    {
        "type": TensionType.MICRO_VS_MACRO,
        "side_a": ["individual", "household", "firm level"],
        "side_b": ["aggregate", "macro", "general equilibrium effect"],
        "alert": "미시 추정의 집계 문제 — GE 효과 미포함",
    },
]


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class TensionAlert:
    """연구 긴장 경보."""
    alert_id:     str
    tension_type: str
    description:  str
    alert_message: str
    evidence_a:   str   # side_a 근거
    evidence_b:   str   # side_b 근거
    severity:     str   # "high" | "medium" | "low"
    note_title:   str
    detected_at:  str
    acknowledged: bool = False


@dataclass
class KnowledgeGraphNode:
    """통합 지식 그래프 노드."""
    node_id:    str
    label:      str
    node_type:  str   # "paper" | "concept" | "method" | "dataset" | "equation" | "tension"
    properties: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass
class KnowledgeGraphEdge:
    """통합 지식 그래프 엣지."""
    edge_id:    str
    source_id:  str
    target_id:  str
    edge_type:  str   # "uses" | "contradicts" | "extends" | "cites" | "depends_on" | "tension"
    weight:     float = 1.0
    properties: dict = field(default_factory=dict)
    created_at: str = ""


# ── Graph DB ──────────────────────────────────────────────────────────────────

class KnowledgeGraphDB:
    """
    통합 지식 그래프 데이터베이스.
    모든 인지 엔진의 결과를 단일 그래프로 통합.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir  = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._nodes_path = self._dir / "kg_nodes.json"
        self._edges_path = self._dir / "kg_edges.json"
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, dict] = {}
        self._load()

    def _load(self):
        for path, attr in [(self._nodes_path, "_nodes"), (self._edges_path, "_edges")]:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        setattr(self, attr, json.load(f))
                except Exception:
                    setattr(self, attr, {})

    def _save(self):
        for path, attr in [(self._nodes_path, "_nodes"), (self._edges_path, "_edges")]:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(getattr(self, attr), f, ensure_ascii=False, indent=2)

    def add_node(self, node: KnowledgeGraphNode):
        self._nodes[node.node_id] = asdict(node)
        self._save()

    def add_edge(self, edge: KnowledgeGraphEdge):
        self._edges[edge.edge_id] = asdict(edge)
        self._save()

    def get_node(self, node_id: str) -> Optional[KnowledgeGraphNode]:
        d = self._nodes.get(node_id)
        return KnowledgeGraphNode(**d) if d else None

    def find_node_by_label(self, label: str) -> Optional[KnowledgeGraphNode]:
        for d in self._nodes.values():
            if d["label"].lower() == label.lower():
                return KnowledgeGraphNode(**d)
        return None

    def get_neighbors(self, node_id: str) -> list[tuple[KnowledgeGraphNode, str]]:
        """노드의 이웃 노드 반환 (노드, 엣지 유형)."""
        neighbors = []
        for d in self._edges.values():
            if d["source_id"] == node_id:
                target = self.get_node(d["target_id"])
                if target:
                    neighbors.append((target, d["edge_type"]))
            elif d["target_id"] == node_id:
                source = self.get_node(d["source_id"])
                if source:
                    neighbors.append((source, d["edge_type"]))
        return neighbors

    def get_graph_stats(self) -> dict:
        node_types = {}
        edge_types = {}
        for d in self._nodes.values():
            node_types[d["node_type"]] = node_types.get(d["node_type"], 0) + 1
        for d in self._edges.values():
            edge_types[d["edge_type"]] = edge_types.get(d["edge_type"], 0) + 1
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types":  node_types,
            "edge_types":  edge_types,
        }

    def export_for_visualization(self) -> dict:
        """그래프 시각화용 데이터 내보내기."""
        nodes = []
        edges = []
        for d in self._nodes.values():
            nodes.append({
                "id":    d["node_id"],
                "label": d["label"][:50],
                "type":  d["node_type"],
            })
        for d in self._edges.values():
            edges.append({
                "source": d["source_id"],
                "target": d["target_id"],
                "type":   d["edge_type"],
                "weight": d.get("weight", 1.0),
            })
        return {"nodes": nodes, "edges": edges}

    def add_paper_node(self, title: str, properties: dict = None) -> KnowledgeGraphNode:
        node_id = "paper_" + hashlib.sha256(title.encode()).hexdigest()[:12]
        node = KnowledgeGraphNode(
            node_id    = node_id,
            label      = title,
            node_type  = "paper",
            properties = properties or {},
            created_at = datetime.utcnow().isoformat(),
        )
        self.add_node(node)
        return node

    def add_concept_node(self, concept: str, node_type: str = "concept") -> KnowledgeGraphNode:
        node_id = f"{node_type}_" + hashlib.sha256(concept.encode()).hexdigest()[:12]
        existing = self.get_node(node_id)
        if existing:
            return existing
        node = KnowledgeGraphNode(
            node_id    = node_id,
            label      = concept,
            node_type  = node_type,
            created_at = datetime.utcnow().isoformat(),
        )
        self.add_node(node)
        return node

    def link_nodes(
        self, source_id: str, target_id: str, edge_type: str, weight: float = 1.0
    ) -> KnowledgeGraphEdge:
        edge_id = hashlib.sha256(f"{source_id}|{target_id}|{edge_type}".encode()).hexdigest()[:12]
        edge = KnowledgeGraphEdge(
            edge_id    = edge_id,
            source_id  = source_id,
            target_id  = target_id,
            edge_type  = edge_type,
            weight     = weight,
            created_at = datetime.utcnow().isoformat(),
        )
        self.add_edge(edge)
        return edge


# ── Research Tension Engine ───────────────────────────────────────────────────

class ResearchTensionEngine:
    """
    메타 연구 추론 엔진.
    연구 방향 드리프트, 미해결 긴장, 방법론 단편화를 지속적으로 모니터링.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir  = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._alerts_path = self._dir / "tension_alerts.json"
        self._alerts: dict[str, dict] = {}
        self._load()
        self.graph_db = KnowledgeGraphDB(data_dir)

    def _load(self):
        if self._alerts_path.exists():
            try:
                with open(self._alerts_path, "r", encoding="utf-8") as f:
                    self._alerts = json.load(f)
            except Exception:
                self._alerts = {}

    def _save(self):
        with open(self._alerts_path, "w", encoding="utf-8") as f:
            json.dump(self._alerts, f, ensure_ascii=False, indent=2)

    def scan_tensions(self, content: str, note_title: str) -> list[TensionAlert]:
        """내용에서 연구 긴장 자동 스캔."""
        content_lower = content.lower()
        detected = []

        for pattern in TENSION_PATTERNS:
            has_a = any(kw.lower() in content_lower for kw in pattern["side_a"])
            has_b = any(kw.lower() in content_lower for kw in pattern["side_b"])

            if has_a and has_b:
                # 근거 추출
                ev_a = next(
                    (line.strip()[:150] for line in content.split("\n")
                     if any(kw.lower() in line.lower() for kw in pattern["side_a"])),
                    ""
                )
                ev_b = next(
                    (line.strip()[:150] for line in content.split("\n")
                     if any(kw.lower() in line.lower() for kw in pattern["side_b"])),
                    ""
                )

                alert_id = hashlib.sha256(
                    f"{note_title}|{pattern['type'].value}".encode()
                ).hexdigest()[:12]

                severity = "high" if pattern["type"] in [
                    TensionType.IDENTIFICATION_VS_EV,
                    TensionType.DSGE_VS_REDUCED,
                ] else "medium"

                alert = TensionAlert(
                    alert_id      = alert_id,
                    tension_type  = pattern["type"].value,
                    description   = TENSION_DESCRIPTIONS[pattern["type"]],
                    alert_message = pattern["alert"],
                    evidence_a    = ev_a,
                    evidence_b    = ev_b,
                    severity      = severity,
                    note_title    = note_title,
                    detected_at   = datetime.utcnow().isoformat(),
                )
                self._alerts[alert_id] = asdict(alert)
                detected.append(alert)

        self._save()
        return detected

    def get_unacknowledged(self) -> list[TensionAlert]:
        return [
            TensionAlert(**d) for d in self._alerts.values()
            if not d.get("acknowledged", False)
        ]

    def acknowledge(self, alert_id: str):
        if alert_id in self._alerts:
            self._alerts[alert_id]["acknowledged"] = True
            self._save()

    def generate_tension_report(self, note_title: str) -> str:
        """특정 노트의 긴장 보고서 생성."""
        alerts = [
            TensionAlert(**d) for d in self._alerts.values()
            if d["note_title"] == note_title
        ]
        if not alerts:
            return ""

        lines = ["\n## 🔭 Research Tension Analysis\n"]
        lines.append("> *Scientific cognition co-processor output*\n")

        high   = [a for a in alerts if a.severity == "high"]
        medium = [a for a in alerts if a.severity == "medium"]
        low    = [a for a in alerts if a.severity == "low"]

        for severity_label, group in [("🔴 High", high), ("🟠 Medium", medium), ("🟡 Low", low)]:
            if group:
                lines.append(f"### {severity_label} Severity Tensions\n")
                for alert in group:
                    icon = TENSION_ICONS.get(TensionType(alert.tension_type), "⚡")
                    lines.append(f"#### {icon} {alert.tension_type.replace('_', ' ').title()}")
                    lines.append(f"**Core Tension**: {alert.description}")
                    lines.append(f"**Alert**: _{alert.alert_message}_")
                    if alert.evidence_a:
                        lines.append(f"**Evidence A**: `{alert.evidence_a[:120]}`")
                    if alert.evidence_b:
                        lines.append(f"**Evidence B**: `{alert.evidence_b[:120]}`")
                    lines.append("")

        return "\n".join(lines)

    def generate_global_tension_report(self) -> str:
        """전체 볼트의 긴장 현황 보고서."""
        all_alerts = [TensionAlert(**d) for d in self._alerts.values()]
        if not all_alerts:
            return "# Research Tension Dashboard\n\n_No tensions detected yet._"

        by_type: dict[str, int] = {}
        for a in all_alerts:
            by_type[a.tension_type] = by_type.get(a.tension_type, 0) + 1

        lines = [
            "# 🔭 Research Tension Dashboard\n",
            f"**Total Alerts**: {len(all_alerts)}  |  "
            f"**Unacknowledged**: {len(self.get_unacknowledged())}\n",
            "## Tension Distribution\n",
        ]
        for ttype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            icon = TENSION_ICONS.get(TensionType(ttype), "⚡")
            bar  = "█" * min(count, 20)
            lines.append(f"- {icon} `{ttype}`: {count} {bar}")

        lines.append("\n## Methodological Risk Warnings\n")
        high_alerts = [a for a in all_alerts if a.severity == "high" and not a.acknowledged]
        if high_alerts:
            for a in high_alerts[:5]:
                lines.append(f"- 🔴 **{a.note_title}**: {a.alert_message}")
        else:
            lines.append("_No critical warnings._")

        return "\n".join(lines)

    def integrate_all_engines(
        self,
        note_title: str,
        content: str,
        wikilinks: list[str],
        math_objects: list,
        contradictions: list,
        lineage_node=None,
        evolution_record=None,
    ) -> str:
        """
        5개 엔진 결과를 통합 지식 그래프에 등록.
        논문 노드 → 개념/수식/모순/긴장 노드 연결.
        """
        # 논문 노드 등록
        paper_node = self.graph_db.add_paper_node(note_title, {
            "stage": evolution_record.current_stage if evolution_record else "fleeting_note",
        })

        # WikiLink 개념 연결
        for link in wikilinks:
            concept_node = self.graph_db.add_concept_node(link, "concept")
            self.graph_db.link_nodes(paper_node.node_id, concept_node.node_id, "uses")

        # 수학 객체 연결
        for obj in math_objects:
            math_node = self.graph_db.add_concept_node(obj.name, "math_object")
            self.graph_db.link_nodes(paper_node.node_id, math_node.node_id, "uses_math")

        # 모순 연결
        for c in contradictions:
            c_node = self.graph_db.add_concept_node(
                f"CONTRADICTION:{c.contradiction_type}", "contradiction"
            )
            self.graph_db.link_nodes(paper_node.node_id, c_node.node_id, "contradicts")

        # 긴장 스캔 및 연결
        tensions = self.scan_tensions(content, note_title)
        for t in tensions:
            t_node = self.graph_db.add_concept_node(
                f"TENSION:{t.tension_type}", "tension"
            )
            self.graph_db.link_nodes(paper_node.node_id, t_node.node_id, "tension")

        return paper_node.node_id


# ── 싱글톤 접근 ───────────────────────────────────────────────────────────────
_tension_engine: Optional[ResearchTensionEngine] = None
_graph_db: Optional[KnowledgeGraphDB] = None

def get_tension_engine() -> ResearchTensionEngine:
    global _tension_engine
    if _tension_engine is None:
        _tension_engine = ResearchTensionEngine()
    return _tension_engine

def get_graph_db() -> KnowledgeGraphDB:
    global _graph_db
    if _graph_db is None:
        _graph_db = KnowledgeGraphDB()
    return _graph_db
