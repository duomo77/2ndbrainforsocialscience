"""
math_ontology.py — Mathematical Object Linking Engine (ROS v3.0)
=================================================================
경제학/계량경제학 수학 온톨로지 엔진.

자동 식별 및 연결:
- 정리 (theorems)
- 점근 가정 (asymptotic assumptions)
- 분포 (distributions)
- 추정량 (estimators)
- 수렴 개념 (convergence concepts)
- 확률 과정 (stochastic processes)
- 최적화 구조 (optimization structures)
- 균형 객체 (equilibrium objects)

예시:
Asymptotic normality
↳ CLT
↳ weak convergence
↳ empirical process theory
↳ kernel estimation
↳ local polynomial estimation
"""

from __future__ import annotations

import re
import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime


# ── 수학 객체 유형 ────────────────────────────────────────────────────────────

class MathObjectType(str, Enum):
    THEOREM        = "theorem"
    ESTIMATOR      = "estimator"
    DISTRIBUTION   = "distribution"
    ASSUMPTION     = "assumption"
    CONVERGENCE    = "convergence"
    PROCESS        = "stochastic_process"
    OPTIMIZATION   = "optimization"
    EQUILIBRIUM    = "equilibrium"
    OPERATOR       = "operator"
    STATISTIC      = "test_statistic"


MATH_TYPE_ICONS = {
    MathObjectType.THEOREM:      "📐",
    MathObjectType.ESTIMATOR:    "🎯",
    MathObjectType.DISTRIBUTION: "📊",
    MathObjectType.ASSUMPTION:   "⚙️",
    MathObjectType.CONVERGENCE:  "→",
    MathObjectType.PROCESS:      "〰️",
    MathObjectType.OPTIMIZATION: "⬆️",
    MathObjectType.EQUILIBRIUM:  "⚖️",
    MathObjectType.OPERATOR:     "∇",
    MathObjectType.STATISTIC:    "🔢",
}


# ── 내장 수학 온톨로지 (경제학/계량경제학 핵심 개념) ─────────────────────────

BUILTIN_MATH_ONTOLOGY: list[dict] = [
    # ── 점근 이론 계층 ──
    {
        "name": "Asymptotic Normality",
        "type": MathObjectType.CONVERGENCE,
        "latex": r"\sqrt{n}(\hat{\theta} - \theta_0) \xrightarrow{d} \mathcal{N}(0, V)",
        "depends_on": ["CLT", "Slutsky Theorem"],
        "required_by": ["OLS", "MLE", "GMM", "2SLS", "DML"],
        "tags": ["asymptotics", "inference"],
    },
    {
        "name": "CLT",
        "type": MathObjectType.THEOREM,
        "latex": r"\frac{\bar{X}_n - \mu}{\sigma/\sqrt{n}} \xrightarrow{d} \mathcal{N}(0,1)",
        "depends_on": ["i.i.d.", "Finite Variance"],
        "required_by": ["Asymptotic Normality", "t-test", "F-test"],
        "tags": ["asymptotics", "probability"],
    },
    {
        "name": "Weak Convergence",
        "type": MathObjectType.CONVERGENCE,
        "latex": r"X_n \xrightarrow{d} X",
        "depends_on": ["CLT", "Continuous Mapping Theorem"],
        "required_by": ["Asymptotic Normality", "Empirical Process Theory"],
        "tags": ["asymptotics", "functional"],
    },
    {
        "name": "Empirical Process Theory",
        "type": MathObjectType.THEOREM,
        "latex": r"\mathbb{G}_n(f) = \frac{1}{\sqrt{n}}\sum_{i=1}^n (f(X_i) - Ef(X_i))",
        "depends_on": ["Weak Convergence", "Donsker Theorem"],
        "required_by": ["Kernel Estimation", "Semiparametric Efficiency", "DML"],
        "tags": ["semiparametrics", "nonparametrics"],
    },
    # ── 추정량 계층 ──
    {
        "name": "OLS",
        "type": MathObjectType.ESTIMATOR,
        "latex": r"\hat{\beta}_{OLS} = (X'X)^{-1}X'Y",
        "depends_on": ["Gauss-Markov", "Exogeneity"],
        "required_by": ["FWL Theorem", "Frisch-Waugh"],
        "tags": ["regression", "linear"],
    },
    {
        "name": "2SLS",
        "type": MathObjectType.ESTIMATOR,
        "latex": r"\hat{\beta}_{2SLS} = (X'P_Z X)^{-1}X'P_Z Y",
        "depends_on": ["Exclusion Restriction", "Relevance", "Exogeneity"],
        "required_by": ["LATE", "IV Inference"],
        "tags": ["IV", "endogeneity"],
    },
    {
        "name": "GMM",
        "type": MathObjectType.ESTIMATOR,
        "latex": r"\hat{\theta}_{GMM} = \arg\min_\theta g_n(\theta)'W g_n(\theta)",
        "depends_on": ["Moment Conditions", "Identification"],
        "required_by": ["Efficient GMM", "Over-identification Test"],
        "tags": ["moment conditions", "efficiency"],
    },
    {
        "name": "DML Estimator",
        "type": MathObjectType.ESTIMATOR,
        "latex": r"\hat{\theta} = \left(\frac{1}{K}\sum_k \hat{E}_k[\tilde{D}\tilde{D}']\right)^{-1} \frac{1}{K}\sum_k \hat{E}_k[\tilde{D}\tilde{Y}]",
        "depends_on": ["Neyman Orthogonality", "Cross-fitting", "Riesz Representer"],
        "required_by": ["CATE", "Heterogeneous Effects"],
        "tags": ["DML", "causal ML", "semiparametric"],
    },
    # ── 분포 계층 ──
    {
        "name": "Normal Distribution",
        "type": MathObjectType.DISTRIBUTION,
        "latex": r"X \sim \mathcal{N}(\mu, \sigma^2)",
        "depends_on": [],
        "required_by": ["CLT", "t-test", "F-test", "OLS Inference"],
        "tags": ["distribution", "parametric"],
    },
    {
        "name": "Chi-squared Distribution",
        "type": MathObjectType.DISTRIBUTION,
        "latex": r"\chi^2_k = \sum_{i=1}^k Z_i^2, \; Z_i \sim \mathcal{N}(0,1)",
        "depends_on": ["Normal Distribution"],
        "required_by": ["Sargan Test", "Hansen J-test", "LM Test"],
        "tags": ["distribution", "testing"],
    },
    # ── 최적화 ──
    {
        "name": "Neyman Orthogonality",
        "type": MathObjectType.OPTIMIZATION,
        "latex": r"\partial_\eta E[\psi(W;\theta_0,\eta_0)][\eta - \eta_0] = 0",
        "depends_on": ["Score Function", "Nuisance Parameter"],
        "required_by": ["DML Estimator", "Semiparametric Efficiency"],
        "tags": ["DML", "orthogonality", "robustness"],
    },
    {
        "name": "Frisch-Waugh-Lovell Theorem",
        "type": MathObjectType.THEOREM,
        "latex": r"\hat{\beta}_1 = (M_2 X_1)' M_2 X_1)^{-1} (M_2 X_1)' M_2 Y",
        "depends_on": ["OLS", "Projection Matrix"],
        "required_by": ["Partialling Out", "DML", "Fixed Effects"],
        "tags": ["regression", "partialling out"],
    },
    # ── 균형 ──
    {
        "name": "Nash Equilibrium",
        "type": MathObjectType.EQUILIBRIUM,
        "latex": r"u_i(s_i^*, s_{-i}^*) \geq u_i(s_i, s_{-i}^*) \; \forall s_i",
        "depends_on": ["Best Response", "Rationality"],
        "required_by": ["IO Models", "Game Theory", "DSGE"],
        "tags": ["game theory", "equilibrium"],
    },
    {
        "name": "Competitive Equilibrium",
        "type": MathObjectType.EQUILIBRIUM,
        "latex": r"(p^*, x^*, y^*): \text{markets clear}, \text{agents optimize}",
        "depends_on": ["Walras Law", "Market Clearing"],
        "required_by": ["DSGE", "General Equilibrium", "Welfare Analysis"],
        "tags": ["general equilibrium", "macro"],
    },
    # ── 확률 과정 ──
    {
        "name": "Brownian Motion",
        "type": MathObjectType.PROCESS,
        "latex": r"W(t) \sim \mathcal{N}(0, t), \; W(t)-W(s) \perp \mathcal{F}_s",
        "depends_on": ["Martingale", "Continuous Paths"],
        "required_by": ["Stochastic Calculus", "Unit Root", "Cointegration"],
        "tags": ["time series", "stochastic"],
    },
    # ── 검정 통계량 ──
    {
        "name": "Sargan-Hansen J-test",
        "type": MathObjectType.STATISTIC,
        "latex": r"J = n \cdot g_n(\hat{\theta})'W g_n(\hat{\theta}) \xrightarrow{d} \chi^2_{q-k}",
        "depends_on": ["GMM", "Over-identification"],
        "required_by": ["IV Validity", "Instrument Exogeneity"],
        "tags": ["testing", "IV", "over-identification"],
    },
]


# ── 데이터 모델 ───────────────────────────────────────────────────────────────

@dataclass
class MathObject:
    """수학 객체 노드."""
    object_id:   str
    name:        str
    object_type: str
    latex:       str
    description: str = ""
    depends_on:  list[str] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)
    tags:        list[str] = field(default_factory=list)
    papers:      list[str] = field(default_factory=list)  # 이 객체를 사용한 논문
    created_at:  str = ""


# ── Math Ontology Store ───────────────────────────────────────────────────────

class MathOntologyStore:
    """수학 온톨로지 저장소."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._dir  = data_dir or (Path.home() / ".econometric_wiki")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "math_ontology.json"
        self._objects: dict[str, dict] = {}
        self._load()
        self._seed_builtin()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._objects = json.load(f)
            except Exception:
                self._objects = {}

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._objects, f, ensure_ascii=False, indent=2)

    def _seed_builtin(self):
        """내장 온톨로지 초기 시딩."""
        changed = False
        for entry in BUILTIN_MATH_ONTOLOGY:
            obj_id = hashlib.sha256(entry["name"].encode()).hexdigest()[:12]
            if obj_id not in self._objects:
                obj = MathObject(
                    object_id   = obj_id,
                    name        = entry["name"],
                    object_type = entry["type"].value,
                    latex       = entry.get("latex", ""),
                    depends_on  = entry.get("depends_on", []),
                    required_by = entry.get("required_by", []),
                    tags        = entry.get("tags", []),
                    created_at  = datetime.utcnow().isoformat(),
                )
                self._objects[obj_id] = asdict(obj)
                changed = True
        if changed:
            self._save()

    def get(self, name: str) -> Optional[MathObject]:
        for d in self._objects.values():
            if d["name"].lower() == name.lower():
                return MathObject(**d)
        return None

    def search(self, query: str) -> list[MathObject]:
        q = query.lower()
        results = []
        for d in self._objects.values():
            if (q in d["name"].lower() or
                any(q in t for t in d.get("tags", [])) or
                q in d.get("description", "").lower()):
                results.append(MathObject(**d))
        return results

    def add(self, obj: MathObject):
        self._objects[obj.object_id] = asdict(obj)
        self._save()

    def all_objects(self) -> list[MathObject]:
        return [MathObject(**d) for d in self._objects.values()]

    def link_paper(self, object_name: str, paper_title: str):
        """논문을 수학 객체에 연결."""
        for obj_id, d in self._objects.items():
            if d["name"].lower() == object_name.lower():
                if paper_title not in d.get("papers", []):
                    d.setdefault("papers", []).append(paper_title)
                    self._objects[obj_id] = d
                    self._save()
                break


# ── Math Ontology Engine ──────────────────────────────────────────────────────

class MathOntologyEngine:
    """
    수학 온톨로지 엔진.
    논문/노트에서 수학 객체를 자동 감지하고 의존성 그래프를 구축.
    """

    # 감지 패턴: (정규식, 객체 유형, 표준 이름)
    DETECTION_PATTERNS = [
        # 추정량
        (r'\bOLS\b|ordinary least squares', MathObjectType.ESTIMATOR, "OLS"),
        (r'\b2SLS\b|two.stage least squares', MathObjectType.ESTIMATOR, "2SLS"),
        (r'\bGMM\b|generalized method of moments', MathObjectType.ESTIMATOR, "GMM"),
        (r'\bMLE\b|maximum likelihood', MathObjectType.ESTIMATOR, "MLE"),
        (r'\bDML\b|double.debiased machine learning', MathObjectType.ESTIMATOR, "DML Estimator"),
        (r'\bLASSO\b|l1 regularization', MathObjectType.ESTIMATOR, "LASSO"),
        # 정리
        (r'\bCLT\b|central limit theorem', MathObjectType.THEOREM, "CLT"),
        (r'frisch.waugh|FWL theorem|partialling.out', MathObjectType.THEOREM, "Frisch-Waugh-Lovell Theorem"),
        (r'neyman orthogon', MathObjectType.OPTIMIZATION, "Neyman Orthogonality"),
        # 수렴
        (r'asymptotic normal|root.n consistent', MathObjectType.CONVERGENCE, "Asymptotic Normality"),
        (r'weak convergence|converges in distribution', MathObjectType.CONVERGENCE, "Weak Convergence"),
        (r'empirical process', MathObjectType.CONVERGENCE, "Empirical Process Theory"),
        # 분포
        (r'\bchi.squared?\b|χ²', MathObjectType.DISTRIBUTION, "Chi-squared Distribution"),
        (r'normal distribution|gaussian', MathObjectType.DISTRIBUTION, "Normal Distribution"),
        # 검정
        (r'sargan|hansen j.test|over.identification test', MathObjectType.STATISTIC, "Sargan-Hansen J-test"),
        # 균형
        (r'nash equilibrium', MathObjectType.EQUILIBRIUM, "Nash Equilibrium"),
        (r'competitive equilibrium|walrasian', MathObjectType.EQUILIBRIUM, "Competitive Equilibrium"),
        # 확률 과정
        (r'brownian motion|wiener process', MathObjectType.PROCESS, "Brownian Motion"),
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        self.store = MathOntologyStore(data_dir)

    def scan_content(self, content: str, paper_title: str = "") -> list[MathObject]:
        """
        내용에서 수학 객체 자동 감지.
        감지된 객체를 논문과 연결.
        """
        content_lower = content.lower()
        detected = []
        seen = set()

        for pattern, obj_type, std_name in self.DETECTION_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE):
                if std_name not in seen:
                    obj = self.store.get(std_name)
                    if obj:
                        if paper_title:
                            self.store.link_paper(std_name, paper_title)
                        detected.append(obj)
                        seen.add(std_name)

        return detected

    def get_dependency_chain(self, name: str, max_depth: int = 4) -> list[dict]:
        """
        특정 수학 객체의 의존성 체인 반환.
        예: DML → Neyman Orthogonality → Score Function → ...
        """
        obj = self.store.get(name)
        if not obj:
            return []

        chain = [{"name": obj.name, "type": obj.object_type, "latex": obj.latex, "depth": 0}]
        visited = {obj.name}

        def _expand(current_obj: MathObject, depth: int):
            if depth >= max_depth:
                return
            for dep_name in current_obj.depends_on:
                if dep_name not in visited:
                    dep = self.store.get(dep_name)
                    if dep:
                        chain.append({
                            "name": dep.name,
                            "type": dep.object_type,
                            "latex": dep.latex,
                            "depth": depth,
                        })
                        visited.add(dep_name)
                        _expand(dep, depth + 1)

        _expand(obj, 1)
        return chain

    def format_math_section(self, detected_objects: list[MathObject]) -> str:
        """감지된 수학 객체를 Markdown 섹션으로 포맷."""
        if not detected_objects:
            return ""

        lines = ["\n## 📐 Mathematical Object Ontology\n"]

        # 유형별 그룹핑
        by_type: dict[str, list[MathObject]] = {}
        for obj in detected_objects:
            by_type.setdefault(obj.object_type, []).append(obj)

        for obj_type, objs in sorted(by_type.items()):
            icon = MATH_TYPE_ICONS.get(MathObjectType(obj_type), "∘")
            lines.append(f"### {icon} {obj_type.replace('_', ' ').title()}\n")
            for obj in objs:
                lines.append(f"#### [[{obj.name}]]")
                if obj.latex:
                    lines.append(f"$$\n{obj.latex}\n$$")
                if obj.depends_on:
                    deps = " → ".join(f"[[{d}]]" for d in obj.depends_on)
                    lines.append(f"**Depends on**: {deps}")
                if obj.required_by:
                    reqs = ", ".join(f"[[{r}]]" for r in obj.required_by[:5])
                    lines.append(f"**Required by**: {reqs}")
                lines.append("")

        return "\n".join(lines)

    def build_theorem_dependency_graph(self, paper_content: str) -> str:
        """논문 내용에서 정리 의존성 그래프 생성 (Mermaid 형식)."""
        detected = self.scan_content(paper_content)
        if not detected:
            return ""

        lines = ["```mermaid", "graph TD"]
        seen_edges = set()

        for obj in detected:
            safe_name = obj.name.replace(" ", "_").replace("-", "_")
            for dep in obj.depends_on:
                dep_obj = self.store.get(dep)
                if dep_obj:
                    safe_dep = dep.replace(" ", "_").replace("-", "_")
                    edge = f"    {safe_dep}[{dep}] --> {safe_name}[{obj.name}]"
                    if edge not in seen_edges:
                        lines.append(edge)
                        seen_edges.add(edge)

        lines.append("```")
        return "\n".join(lines) if len(lines) > 3 else ""

    def get_stats(self) -> dict:
        """온톨로지 통계."""
        objs = self.store.all_objects()
        by_type = {}
        for o in objs:
            by_type[o.object_type] = by_type.get(o.object_type, 0) + 1
        return {"total": len(objs), "by_type": by_type}


# ── 싱글톤 접근 ───────────────────────────────────────────────────────────────
_engine: Optional[MathOntologyEngine] = None

def get_math_engine() -> MathOntologyEngine:
    global _engine
    if _engine is None:
        _engine = MathOntologyEngine()
    return _engine
