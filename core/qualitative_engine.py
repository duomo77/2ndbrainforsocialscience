"""
qualitative_engine.py  —  ROS v7.0 Multi-Epistemic Engine
===========================================================
철학: 실증주의만큼 해석주의·구성주의·비판이론도 first-class citizen.
      질적 관찰은 양적 데이터와 동등한 의미론적 엔티티.

지원 에피스테믹 전통:
  - Positivist / Quantitative
  - Interpretivist / Qualitative
  - Constructivist
  - Critical Theory
  - Mixed-Method
  - Historical / Comparative
  - Computational / Data-driven
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# EPISTEMIC TAXONOMY
# ══════════════════════════════════════════════════════════════════════════════

class EpistemicMode(str, Enum):
    QUANTITATIVE  = "quantitative"
    QUALITATIVE   = "qualitative"
    MIXED         = "mixed"
    HISTORICAL    = "historical"
    COMPUTATIONAL = "computational"
    CRITICAL      = "critical_theory"
    AUTO          = "auto"


class MaterialType(str, Enum):
    """질적 연구 자료 유형."""
    INTERVIEW          = "interview"
    FOCUS_GROUP        = "focus_group"
    ETHNOGRAPHIC_NOTES = "ethnographic_notes"
    FIELD_OBSERVATIONS = "field_observations"
    DISCOURSE_ANALYSIS = "discourse_analysis"
    DOCUMENT_ANALYSIS  = "document_analysis"
    CASE_STUDY         = "case_study"
    NARRATIVE          = "narrative"
    POLICY_TEXT        = "policy_text"
    HISTORICAL_ARCHIVE = "historical_archive"
    SURVEY_OPEN_ENDED  = "survey_open_ended"
    SOCIAL_MEDIA       = "social_media"


class TheoreticalFramework(str, Enum):
    """이론적 패러다임."""
    INTERPRETIVISM      = "Interpretivism"
    CONSTRUCTIVISM      = "Constructivism"
    CRITICAL_THEORY     = "Critical Theory"
    PHENOMENOLOGY       = "Phenomenology"
    GROUNDED_THEORY     = "Grounded Theory"
    DISCOURSE_ANALYSIS  = "Discourse Analysis"
    INSTITUTIONAL       = "Institutional Theory"
    FEMINIST            = "Feminist Theory"
    POSTCOLONIAL        = "Postcolonial Theory"
    PRAGMATISM          = "Pragmatism"
    STRUCTURALISM       = "Structuralism"
    POSTSTRUCTURALISM   = "Poststructuralism"
    REALISM             = "Critical Realism"
    POSITIVISM          = "Positivism"


# ══════════════════════════════════════════════════════════════════════════════
# DATA CONTRACTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EpistemicProfile:
    """논문/자료의 에피스테믹 프로파일."""
    mode: EpistemicMode
    confidence: float           # 0.0 ~ 1.0
    detected_signals: list[str] = field(default_factory=list)
    framework_hints: list[str]  = field(default_factory=list)
    methodology_hints: list[str] = field(default_factory=list)
    is_mixed: bool = False
    qual_score: int = 0
    quant_score: int = 0


@dataclass
class QualitativeTheme:
    """질적 분석에서 추출된 테마."""
    name: str
    core_claim: str
    evidence_quotes: list[str] = field(default_factory=list)
    theoretical_connections: list[str] = field(default_factory=list)
    tension_with: list[str] = field(default_factory=list)
    salience: float = 0.5       # 0.0 ~ 1.0


@dataclass
class DiscourseFrame:
    """담론 분석에서 추출된 프레임."""
    frame_name: str
    dominant_narrative: str
    silenced_voices: list[str] = field(default_factory=list)
    power_relations: list[str] = field(default_factory=list)
    semantic_shifts: list[str] = field(default_factory=list)


@dataclass
class EpistemicTension:
    """에피스테믹 긴장 구조 (그래프 엔티티)."""
    tension_id: str
    type: str                   # methodological / ideological / theoretical / ontological
    position_a: str
    position_b: str
    discipline: str
    resolution_status: str = "unresolved"  # unresolved / partial / resolved
    notes: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# EPISTEMIC DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

# 질적 신호 패턴
_QUAL_SIGNALS: list[tuple[str, str]] = [
    (r"\b(interview|interviewee|informant|participant)\b",       "interview_data"),
    (r"\b(ethnograph|fieldwork|field note|participant observation)\b", "ethnography"),
    (r"\b(discourse|rhetoric|framing|narrative|text analysis)\b","discourse"),
    (r"\b(thematic|coding|saturation|grounded theory|constant comparison)\b", "thematic_analysis"),
    (r"\b(case study|within-case|cross-case|process tracing)\b", "case_study"),
    (r"\b(phenomenolog|lived experience|meaning-making|hermeneutic)\b", "phenomenology"),
    (r"\b(qualitative|interpretivist|constructivist|critical theory)\b", "qual_paradigm"),
    (r"\b(focus group|in-depth interview|semi-structured)\b",    "qual_method"),
    (r"\b(positionality|reflexivity|trustworthiness|transferability)\b", "qual_rigor"),
    (r"\b(ideology|power|hegemony|domination|resistance|subaltern)\b", "critical_theory"),
]

# 양적 신호 패턴
_QUANT_SIGNALS: list[tuple[str, str]] = [
    (r"\b(regression|ols|2sls|iv|did|rdd|rct|experiment)\b",    "causal_design"),
    (r"\b(coefficient|standard error|p-value|confidence interval|t-stat)\b", "inference"),
    (r"\b(bayesian|mcmc|prior|posterior|likelihood)\b",          "bayesian"),
    (r"\b(machine learning|random forest|xgboost|lasso|neural network)\b", "ml"),
    (r"\b(panel data|fixed effect|random effect|instrumental variable)\b", "panel"),
    (r"\b(identification|exogenous|endogenous|selection bias|omitted variable)\b", "identification"),
    (r"\b(sample size|n=|observations|dataset|survey data)\b",   "quantitative_data"),
    (r"\b(structural equation|path model|sem|factor analysis)\b","structural"),
]

# 역사·비교 신호
_HIST_SIGNALS: list[tuple[str, str]] = [
    (r"\b(historical|archive|primary source|secondary source)\b", "historical"),
    (r"\b(comparative|cross-national|cross-country|most similar|most different)\b", "comparative"),
    (r"\b(periodization|chronolog|temporal|longitudinal narrative)\b", "temporal"),
]

# 프레임워크 힌트
_FRAMEWORK_HINTS: dict[str, str] = {
    r"\b(grounded theory|strauss|corbin|glaser)\b":     TheoreticalFramework.GROUNDED_THEORY.value,
    r"\b(discourse analysis|foucault|laclau|mouffe)\b": TheoreticalFramework.DISCOURSE_ANALYSIS.value,
    r"\b(phenomenolog|husserl|heidegger|merleau-ponty)\b": TheoreticalFramework.PHENOMENOLOGY.value,
    r"\b(critical theory|frankfurt|habermas|adorno)\b": TheoreticalFramework.CRITICAL_THEORY.value,
    r"\b(institutional|north|scott|dimaggio|powell)\b": TheoreticalFramework.INSTITUTIONAL.value,
    r"\b(feminist|gender|patriarchy|intersectionality)\b": TheoreticalFramework.FEMINIST.value,
    r"\b(postcolonial|decolonial|subaltern|spivak|bhabha)\b": TheoreticalFramework.POSTCOLONIAL.value,
    r"\b(constructivist|berger|luckmann|social construction)\b": TheoreticalFramework.CONSTRUCTIVISM.value,
    r"\b(critical realism|bhaskar|archer|sayer)\b":     TheoreticalFramework.REALISM.value,
}


class EpistemicDetector:
    """
    입력 텍스트에서 에피스테믹 모드를 자동 감지.

    책임:
      - 질적/양적/혼합 신호 스코어링
      - 이론적 프레임워크 힌트 추출
      - 방법론 힌트 추출
    """

    def detect(self, text: str, discipline: str = "") -> EpistemicProfile:
        text_lower = text.lower()
        disc_lower = discipline.lower().replace(" ", "").replace("_", "")

        qual_signals: list[str] = []
        quant_signals: list[str] = []
        hist_signals: list[str] = []

        for pattern, label in _QUAL_SIGNALS:
            if re.search(pattern, text_lower, re.I):
                qual_signals.append(label)

        for pattern, label in _QUANT_SIGNALS:
            if re.search(pattern, text_lower, re.I):
                quant_signals.append(label)

        for pattern, label in _HIST_SIGNALS:
            if re.search(pattern, text_lower, re.I):
                hist_signals.append(label)

        framework_hints: list[str] = []
        for pattern, fw in _FRAMEWORK_HINTS.items():
            if re.search(pattern, text_lower, re.I):
                framework_hints.append(fw)

        q_score = len(qual_signals)
        n_score = len(quant_signals)
        h_score = len(hist_signals)

        # 학문 분야 기반 기본 편향
        qual_disciplines  = {"sociology","anthropology","communicationstudies",
                             "history","philosophy","linguistics","literature","arthistory"}
        quant_disciplines = {"economics","econometrics","statistics","physics","chemistry",
                             "biology","medicine","epidemiology","machinelearning"}

        if disc_lower in qual_disciplines:
            q_score += 2
        elif disc_lower in quant_disciplines:
            n_score += 2

        # 에피스테믹 모드 결정
        if h_score > 0 and q_score <= 1 and n_score <= 1:
            mode = EpistemicMode.HISTORICAL
            confidence = 0.80
        elif q_score > 0 and n_score > 0:
            mode = EpistemicMode.MIXED
            confidence = min(0.85, 0.60 + 0.05 * (q_score + n_score))
        elif q_score > n_score:
            mode = EpistemicMode.QUALITATIVE
            confidence = min(0.95, 0.65 + 0.05 * q_score)
        elif n_score > q_score:
            mode = EpistemicMode.QUANTITATIVE
            confidence = min(0.95, 0.65 + 0.05 * n_score)
        else:
            mode = EpistemicMode.QUANTITATIVE
            confidence = 0.50

        all_signals = qual_signals + quant_signals + hist_signals

        return EpistemicProfile(
            mode=mode,
            confidence=confidence,
            detected_signals=all_signals,
            framework_hints=framework_hints,
            methodology_hints=qual_signals + quant_signals,
            is_mixed=(mode == EpistemicMode.MIXED),
            qual_score=q_score,
            quant_score=n_score,
        )


# ══════════════════════════════════════════════════════════════════════════════
# QUALITATIVE STRUCTURE EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════

class QualitativeExtractor:
    """
    LLM 결과 마크다운에서 질적 구조를 추출.
    (테마, 담론 프레임, 에피스테믹 긴장)
    """

    def extract_themes(self, markdown: str) -> list[QualitativeTheme]:
        themes: list[QualitativeTheme] = []
        # ### Theme N: [Name] 패턴 추출
        theme_blocks = re.split(r"###\s+Theme\s+\d+:\s*", markdown, flags=re.I)
        for block in theme_blocks[1:]:
            lines = block.strip().split("\n")
            name = lines[0].strip() if lines else "Unknown Theme"
            core_claim = ""
            quotes: list[str] = []
            connections: list[str] = []

            for line in lines[1:]:
                if line.startswith(">"):
                    core_claim = line.lstrip("> ").strip()
                elif "**Evidence**" in line or "**Quote**" in line:
                    quotes.append(re.sub(r"\*\*.*?\*\*:\s*", "", line).strip())
                elif "**Connects to**" in line:
                    found = re.findall(r"\[\[([^\]]+)\]\]", line)
                    connections.extend(found)

            if name:
                themes.append(QualitativeTheme(
                    name=name, core_claim=core_claim,
                    evidence_quotes=quotes[:5],
                    theoretical_connections=connections,
                ))
        return themes

    def extract_discourse_frames(self, markdown: str) -> list[DiscourseFrame]:
        frames: list[DiscourseFrame] = []
        # Discourse / Ideological Analysis 섹션 추출
        section = re.search(
            r"##\s+💬\s+Discourse.*?(?=##|\Z)", markdown, re.S | re.I
        )
        if not section:
            return frames

        text = section.group(0)
        dominant = re.search(r"\*\*Dominant frames?\*\*:\s*(.+)", text)
        silenced  = re.search(r"\*\*Silenced voices?\*\*:\s*(.+)", text)
        power     = re.search(r"\*\*Power relations?\*\*:\s*(.+)", text)

        if dominant:
            frames.append(DiscourseFrame(
                frame_name="Primary Frame",
                dominant_narrative=dominant.group(1).strip(),
                silenced_voices=[silenced.group(1).strip()] if silenced else [],
                power_relations=[power.group(1).strip()] if power else [],
            ))
        return frames

    def extract_tensions(self, markdown: str, discipline: str = "") -> list[EpistemicTension]:
        tensions: list[EpistemicTension] = []
        # ⚠️ Critical Assessment 또는 Tension 섹션
        tension_patterns = [
            (r"structural rigor vs empirical", "methodological",
             "Structural Rigor", "Empirical Tractability"),
            (r"identification strength vs external validity", "methodological",
             "Internal Validity", "External Validity"),
            (r"interpretability vs predictive", "methodological",
             "Interpretability", "Predictive Power"),
            (r"theory vs empirical", "theoretical",
             "Theory", "Empirical Evidence"),
            (r"positivist vs interpretivist", "ontological",
             "Positivism", "Interpretivism"),
            (r"agency vs structure", "theoretical",
             "Agency", "Structure"),
            (r"micro vs macro", "theoretical",
             "Micro-level", "Macro-level"),
            (r"qualitative vs quantitative", "methodological",
             "Qualitative", "Quantitative"),
        ]

        for pattern, tension_type, pos_a, pos_b in tension_patterns:
            if re.search(pattern, markdown, re.I):
                tensions.append(EpistemicTension(
                    tension_id=f"{pos_a.lower().replace(' ', '_')}_vs_{pos_b.lower().replace(' ', '_')}",
                    type=tension_type,
                    position_a=pos_a,
                    position_b=pos_b,
                    discipline=discipline,
                ))
        return tensions


# ══════════════════════════════════════════════════════════════════════════════
# MIXED-METHOD INTEGRATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class MixedMethodIntegrator:
    """
    혼합방법론 연구의 QUAN + QUAL 통합 분석.

    통합 전략:
      - Triangulation: 수렴 확인
      - Sequential Explanatory: QUAN → QUAL 설명
      - Sequential Exploratory: QUAL → QUAN 검증
      - Embedded: 한 방법이 다른 방법 내 포함
    """

    INTEGRATION_STRATEGIES = {
        "triangulation":           "두 방법의 결과가 수렴하는지 확인",
        "sequential_explanatory":  "양적 결과를 질적 방법으로 설명",
        "sequential_exploratory":  "질적 탐색 후 양적 검증",
        "embedded":                "주요 방법 내에 보조 방법 포함",
        "transformative":          "비판이론/사회정의 프레임 내 혼합",
    }

    def detect_integration_strategy(self, text: str) -> str:
        text_lower = text.lower()
        if "triangulat" in text_lower:
            return "triangulation"
        if "sequential" in text_lower and "explanatory" in text_lower:
            return "sequential_explanatory"
        if "sequential" in text_lower and "exploratory" in text_lower:
            return "sequential_exploratory"
        if "embedded" in text_lower:
            return "embedded"
        if "transformative" in text_lower or "emancipatory" in text_lower:
            return "transformative"
        return "triangulation"  # 기본값

    def generate_integration_note(
        self,
        quan_findings: str,
        qual_findings: str,
        strategy: str,
    ) -> str:
        """혼합방법론 통합 섹션 마크다운 생성."""
        strategy_desc = self.INTEGRATION_STRATEGIES.get(strategy, "통합 전략 미지정")
        return f"""## 🔀 Mixed-Method Integration

**Integration Strategy**: {strategy} — {strategy_desc}

### Points of Convergence
[QUAN and QUAL findings that mutually reinforce]

### Points of Divergence
[Where QUAN and QUAL findings conflict or diverge]

### Meta-Inferences
[Higher-order conclusions possible only through integration]

### Epistemic Value Added
- QUAN contribution: statistical generalizability
- QUAL contribution: contextual depth, mechanism explanation
- Integration: {strategy_desc}
"""


# ══════════════════════════════════════════════════════════════════════════════
# SEMANTIC ENTROPY MONITOR (질적 그래프 전용)
# ══════════════════════════════════════════════════════════════════════════════

class QualitativeEntropyMonitor:
    """
    질적 지식 그래프의 의미론적 엔트로피 모니터링.
    - 테마 중복 감지
    - 담론 프레임 충돌 감지
    - 개념 이동(semantic drift) 감지
    """

    def __init__(self):
        self._theme_registry: dict[str, list[str]] = {}  # theme_name → [note_ids]
        self._frame_registry: dict[str, list[str]] = {}  # frame → [note_ids]

    def register_themes(self, note_id: str, themes: list[QualitativeTheme]) -> list[str]:
        """테마 등록 및 중복 경고 반환."""
        warnings: list[str] = []
        for theme in themes:
            key = theme.name.lower().strip()
            if key in self._theme_registry:
                existing = self._theme_registry[key]
                warnings.append(
                    f"⚠️ Theme '{theme.name}' already exists in: {existing[:3]}"
                )
            self._theme_registry.setdefault(key, []).append(note_id)
        return warnings

    def detect_concept_drift(
        self, concept: str, old_definition: str, new_definition: str
    ) -> Optional[EpistemicTension]:
        """개념 정의 변화 감지 → 에피스테믹 긴장 생성."""
        # 간단한 유사도: 공통 단어 비율
        old_words = set(old_definition.lower().split())
        new_words = set(new_definition.lower().split())
        if not old_words or not new_words:
            return None
        overlap = len(old_words & new_words) / max(len(old_words), len(new_words))
        if overlap < 0.5:
            return EpistemicTension(
                tension_id=f"drift_{concept.lower().replace(' ', '_')}",
                type="semantic_drift",
                position_a=f"Original: {old_definition[:80]}",
                position_b=f"New: {new_definition[:80]}",
                discipline="General",
                notes=f"Concept '{concept}' has drifted (overlap={overlap:.2f})",
            )
        return None

    def get_entropy_report(self) -> dict:
        total_themes = len(self._theme_registry)
        duplicate_themes = sum(
            1 for v in self._theme_registry.values() if len(v) > 1
        )
        return {
            "total_themes": total_themes,
            "duplicate_themes": duplicate_themes,
            "duplication_rate": duplicate_themes / max(total_themes, 1),
            "total_frames": len(self._frame_registry),
        }


# ══════════════════════════════════════════════════════════════════════════════
# FACADE — 외부 인터페이스
# ══════════════════════════════════════════════════════════════════════════════

class MultiEpistemicEngine:
    """
    멀티-에피스테믹 엔진 퍼사드.
    worker.py 및 main_window.py에서 이 클래스를 통해 접근.
    """

    def __init__(self):
        self.detector   = EpistemicDetector()
        self.extractor  = QualitativeExtractor()
        self.integrator = MixedMethodIntegrator()
        self.entropy    = QualitativeEntropyMonitor()

    def detect_mode(self, text: str, discipline: str = "") -> EpistemicProfile:
        return self.detector.detect(text, discipline)

    def extract_structure(self, markdown: str, discipline: str = "") -> dict:
        """LLM 결과 마크다운에서 질적 구조 추출."""
        return {
            "themes":   self.extractor.extract_themes(markdown),
            "frames":   self.extractor.extract_discourse_frames(markdown),
            "tensions": self.extractor.extract_tensions(markdown, discipline),
        }

    def get_material_types(self) -> list[str]:
        return [m.value for m in MaterialType]

    def get_frameworks(self) -> list[str]:
        return [f.value for f in TheoreticalFramework]

    def get_epistemic_modes(self) -> list[str]:
        return [e.value for e in EpistemicMode if e != EpistemicMode.AUTO]

    def get_integration_strategies(self) -> list[str]:
        return list(self.integrator.INTEGRATION_STRATEGIES.keys())

    def entropy_report(self) -> dict:
        return self.entropy.get_entropy_report()


# ── 모듈 레벨 싱글톤 ──────────────────────────────────────────────────────────
_engine: Optional[MultiEpistemicEngine] = None

def get_engine() -> MultiEpistemicEngine:
    global _engine
    if _engine is None:
        _engine = MultiEpistemicEngine()
    return _engine
