"""
classifier.py  —  ROS v7.0 Universal Science Classifier
=========================================================
사회과학·자연과학 전 분야를 커버하는 범용 논문 분류 엔진.

도메인 계층:
  Tier-1: 대분류 (자연과학 / 사회과학 / 공학·기술 / 의학·보건 / 인문학 / 복합·학제)
  Tier-2: 세부 학문 (물리학, 생물학, 경제학, 심리학 …)

우선순위:
  1. 사용자 정의 규칙
  2. 저널명 직접 매핑 (400+ 저널)
  3. 키워드 패턴 매칭 (제목 + 초록)
  4. LLM 폴백 (설정 시)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ── Tier-1 대분류 ──────────────────────────────────────────────────────────────
TIER1: dict[str, str] = {
    "NaturalScience":    "🔬 자연과학",
    "SocialScience":     "🏛 사회과학",
    "Engineering":       "⚙️ 공학·기술",
    "MedicalScience":    "🏥 의학·보건",
    "Humanities":        "📚 인문학",
    "Interdisciplinary": "🔀 복합·학제",
}

# ── Tier-2 세부 학문 → (Tier-1, 아이콘, 폴더명) ────────────────────────────────
DISCIPLINE_MAP: dict[str, tuple[str, str, str]] = {
    # 자연과학
    "Physics":               ("NaturalScience",    "⚛️",  "Physics"),
    "Chemistry":             ("NaturalScience",    "🧪",  "Chemistry"),
    "Biology":               ("NaturalScience",    "🧬",  "Biology"),
    "Mathematics":           ("NaturalScience",    "📐",  "Mathematics"),
    "Statistics":            ("NaturalScience",    "📊",  "Statistics"),
    "Astronomy":             ("NaturalScience",    "🔭",  "Astronomy"),
    "EarthScience":          ("NaturalScience",    "🌍",  "EarthScience"),
    "EnvironmentalScience":  ("NaturalScience",    "🌿",  "EnvironmentalScience"),
    "Neuroscience":          ("NaturalScience",    "🧠",  "Neuroscience"),
    "Genetics":              ("NaturalScience",    "🧬",  "Genetics"),
    "Ecology":               ("NaturalScience",    "🌱",  "Ecology"),
    "MaterialsScience":      ("NaturalScience",    "🔩",  "MaterialsScience"),
    # 사회과학
    "Economics":             ("SocialScience",     "📈",  "Economics"),
    "Econometrics":          ("SocialScience",     "📐",  "Econometrics"),
    "Psychology":            ("SocialScience",     "🧠",  "Psychology"),
    "Sociology":             ("SocialScience",     "👥",  "Sociology"),
    "PoliticalScience":      ("SocialScience",     "🏛",  "PoliticalScience"),
    "Anthropology":          ("SocialScience",     "🗿",  "Anthropology"),
    "Geography":             ("SocialScience",     "🗺️",  "Geography"),
    "CommunicationStudies":  ("SocialScience",     "📡",  "CommunicationStudies"),
    "LawStudies":            ("SocialScience",     "⚖️",  "LawStudies"),
    "EducationScience":      ("SocialScience",     "🎓",  "EducationScience"),
    # 공학·기술
    "ComputerScience":       ("Engineering",       "💻",  "ComputerScience"),
    "MachineLearning":       ("Engineering",       "🤖",  "MachineLearning"),
    "ElectricalEngineering": ("Engineering",       "⚡",  "ElectricalEngineering"),
    "MechanicalEngineering": ("Engineering",       "🔧",  "MechanicalEngineering"),
    "ChemicalEngineering":   ("Engineering",       "🧪",  "ChemicalEngineering"),
    "CivilEngineering":      ("Engineering",       "🏗️",  "CivilEngineering"),
    "Robotics":              ("Engineering",       "🦾",  "Robotics"),
    "Bioinformatics":        ("Engineering",       "🧬",  "Bioinformatics"),
    # 의학·보건
    "Medicine":              ("MedicalScience",    "🏥",  "Medicine"),
    "PublicHealth":          ("MedicalScience",    "💊",  "PublicHealth"),
    "Epidemiology":          ("MedicalScience",    "🦠",  "Epidemiology"),
    "Pharmacology":          ("MedicalScience",    "💉",  "Pharmacology"),
    "ClinicalTrials":        ("MedicalScience",    "🔬",  "ClinicalTrials"),
    "Psychiatry":            ("MedicalScience",    "🧠",  "Psychiatry"),
    # 인문학
    "History":               ("Humanities",        "📜",  "History"),
    "Philosophy":            ("Humanities",        "💭",  "Philosophy"),
    "Linguistics":           ("Humanities",        "🗣️",  "Linguistics"),
    "Literature":            ("Humanities",        "📖",  "Literature"),
    "ArtHistory":            ("Humanities",        "🎨",  "ArtHistory"),
    # 복합·학제
    "CognitiveScience":      ("Interdisciplinary", "🔀",  "CognitiveScience"),
    "BehavioralEconomics":   ("Interdisciplinary", "🔀",  "BehavioralEconomics"),
    "DataScience":           ("Interdisciplinary", "📊",  "DataScience"),
    "ComplexSystems":        ("Interdisciplinary", "🌐",  "ComplexSystems"),
    "Uncategorized":         ("Interdisciplinary", "📂",  "Uncategorized"),
}

# ── 저널명 → Discipline 매핑 ──────────────────────────────────────────────────
JOURNAL_MAP: dict[str, str] = {
    # 물리학
    "physical review letters": "Physics", "physical review": "Physics",
    "nature physics": "Physics", "journal of physics": "Physics",
    "annals of physics": "Physics", "physics letters": "Physics",
    "nuclear physics": "Physics", "reviews of modern physics": "Physics",
    "new journal of physics": "Physics", "european physical journal": "Physics",
    # 화학
    "journal of the american chemical society": "Chemistry", "jacs": "Chemistry",
    "angewandte chemie": "Chemistry", "nature chemistry": "Chemistry",
    "journal of physical chemistry": "Chemistry", "chemical science": "Chemistry",
    "chemistry of materials": "Chemistry", "acs nano": "Chemistry",
    "chemical reviews": "Chemistry", "organic letters": "Chemistry",
    # 생물학
    "nature": "Biology", "science": "Biology", "cell": "Biology",
    "plos biology": "Biology", "elife": "Biology", "molecular cell": "Biology",
    "current biology": "Biology", "developmental cell": "Biology",
    "journal of cell biology": "Biology", "embo journal": "Biology",
    # 유전학
    "nature genetics": "Genetics", "genome research": "Genetics",
    "plos genetics": "Genetics", "american journal of human genetics": "Genetics",
    "genome biology": "Genetics", "human molecular genetics": "Genetics",
    # 신경과학
    "neuron": "Neuroscience", "nature neuroscience": "Neuroscience",
    "journal of neuroscience": "Neuroscience", "cerebral cortex": "Neuroscience",
    "neuroimage": "Neuroscience", "brain": "Neuroscience",
    "trends in neurosciences": "Neuroscience",
    # 수학
    "annals of mathematics": "Mathematics", "inventiones mathematicae": "Mathematics",
    "duke mathematical journal": "Mathematics", "advances in mathematics": "Mathematics",
    "journal of algebra": "Mathematics", "topology": "Mathematics",
    # 통계학
    "annals of statistics": "Statistics",
    "journal of the american statistical association": "Statistics", "jasa": "Statistics",
    "biometrika": "Statistics", "journal of the royal statistical society": "Statistics",
    "statistical science": "Statistics", "bayesian analysis": "Statistics",
    # 컴퓨터과학
    "journal of the acm": "ComputerScience", "communications of the acm": "ComputerScience",
    "ieee transactions on computers": "ComputerScience",
    "theoretical computer science": "ComputerScience",
    "artificial intelligence": "ComputerScience",
    # 머신러닝
    "journal of machine learning research": "MachineLearning", "jmlr": "MachineLearning",
    "machine learning": "MachineLearning", "neural computation": "MachineLearning",
    "neurips": "MachineLearning", "icml": "MachineLearning", "iclr": "MachineLearning",
    "aaai": "MachineLearning", "ijcai": "MachineLearning",
    # 경제학
    "american economic review": "Economics", "aer": "Economics",
    "quarterly journal of economics": "Economics", "qje": "Economics",
    "journal of political economy": "Economics", "jpe": "Economics",
    "review of economic studies": "Economics", "restud": "Economics",
    "review of economics and statistics": "Economics", "restat": "Economics",
    "economic journal": "Economics", "american economic journal": "Economics",
    "rand journal of economics": "Economics",
    # 계량경제학
    "econometrica": "Econometrics", "journal of econometrics": "Econometrics",
    "journal of applied econometrics": "Econometrics",
    "econometric theory": "Econometrics", "quantitative economics": "Econometrics",
    # 심리학
    "psychological review": "Psychology", "psychological bulletin": "Psychology",
    "journal of personality and social psychology": "Psychology",
    "psychological science": "Psychology", "nature human behaviour": "Psychology",
    "cognition": "Psychology", "clinical psychological science": "Psychology",
    # 사회학
    "american sociological review": "Sociology",
    "american journal of sociology": "Sociology",
    "social forces": "Sociology", "annual review of sociology": "Sociology",
    # 정치학
    "american political science review": "PoliticalScience",
    "american journal of political science": "PoliticalScience",
    "journal of politics": "PoliticalScience", "political analysis": "PoliticalScience",
    "world politics": "PoliticalScience", "international organization": "PoliticalScience",
    # 의학
    "new england journal of medicine": "Medicine", "nejm": "Medicine",
    "lancet": "Medicine", "jama": "Medicine", "bmj": "Medicine",
    "nature medicine": "Medicine", "plos medicine": "Medicine",
    # 역학·공중보건
    "american journal of epidemiology": "Epidemiology",
    "international journal of epidemiology": "Epidemiology",
    "american journal of public health": "PublicHealth",
    # 환경과학
    "nature climate change": "EnvironmentalScience",
    "environmental science and technology": "EnvironmentalScience",
    "ecology letters": "Ecology", "global ecology and biogeography": "Ecology",
    # 천문학
    "astrophysical journal": "Astronomy", "astronomy and astrophysics": "Astronomy",
    "monthly notices of the royal astronomical society": "Astronomy",
    "nature astronomy": "Astronomy",
    # 인지과학
    "cognitive science": "CognitiveScience",
    "trends in cognitive sciences": "CognitiveScience",
    # 바이오인포매틱스
    "bioinformatics": "Bioinformatics", "plos computational biology": "Bioinformatics",
    "nucleic acids research": "Bioinformatics",
    # 재료과학
    "nature materials": "MaterialsScience", "acta materialia": "MaterialsScience",
    "advanced materials": "MaterialsScience",
    # 프리프린트
    "nber": "Economics", "ssrn": "Uncategorized", "arxiv": "Uncategorized",
    "biorxiv": "Biology", "medrxiv": "Medicine", "chemrxiv": "Chemistry",
    "psyarxiv": "Psychology", "socarxiv": "Sociology",
}

# ── 키워드 패턴 → Discipline ───────────────────────────────────────────────────
KEYWORD_PATTERNS: list[tuple[str, str]] = [
    (r"\b(quantum|qubit|hamiltonian|photon|boson|fermion|relativity|spacetime|wavefunction)\b", "Physics"),
    (r"\b(synthesis|catalyst|molecule|polymer|reaction|spectroscopy|crystallography|solvent|ligand)\b", "Chemistry"),
    (r"\b(protein|gene|cell|dna|rna|chromosome|mutation|evolution|organism|species|membrane)\b", "Biology"),
    (r"\b(genome|snp|gwas|allele|locus|haplotype|sequencing|transcriptome|epigenome|variant)\b", "Genetics"),
    (r"\b(neuron|synapse|cortex|hippocampus|fmri|eeg|neural circuit|action potential|dopamine|axon)\b", "Neuroscience"),
    (r"\b(theorem|proof|manifold|topology|algebra|group theory|number theory|differential equation|eigenvalue)\b", "Mathematics"),
    (r"\b(bayesian|frequentist|p-value|confidence interval|bootstrap|mcmc|prior|posterior|likelihood)\b", "Statistics"),
    (r"\b(climate change|greenhouse|carbon emission|ecosystem|biodiversity|habitat|deforestation)\b", "EnvironmentalScience"),
    (r"\b(galaxy|star|planet|cosmology|dark matter|black hole|telescope|redshift|nebula)\b", "Astronomy"),
    (r"\b(deep learning|neural network|transformer|bert|gpt|llm|reinforcement learning|gradient descent|attention)\b", "MachineLearning"),
    (r"\b(algorithm|complexity|compiler|distributed system|database|network protocol|cryptography)\b", "ComputerScience"),
    (r"\b(robot|autonomous|sensor|actuator|control system|pid|slam|kinematics|servo)\b", "Robotics"),
    (r"\b(sequence alignment|blast|phylogenetic|motif|pathway|metabolomics|proteomics|variant calling)\b", "Bioinformatics"),
    (r"\b(causal inference|treatment effect|instrumental variable|difference.in.differences|regression discontinuity|dml|double machine learning)\b", "Econometrics"),
    (r"\b(gdp|inflation|monetary policy|fiscal policy|labor market|wage|unemployment|trade|tariff)\b", "Economics"),
    (r"\b(cognitive|perception|memory|attention|emotion|behavior|learning|motivation|personality|cognition)\b", "Psychology"),
    (r"\b(social stratification|inequality|class|race|gender|ethnicity|institution|social capital|norm)\b", "Sociology"),
    (r"\b(election|voting|democracy|party|congress|legislature|policy|governance|state|regime)\b", "PoliticalScience"),
    (r"\b(randomized controlled trial|rct|clinical trial|placebo|drug|treatment|patient|disease|diagnosis|symptom)\b", "Medicine"),
    (r"\b(incidence|prevalence|mortality|morbidity|cohort|case.control|odds ratio|hazard ratio|survival)\b", "Epidemiology"),
    (r"\b(vaccine|pandemic|infection|pathogen|virus|bacteria|immune|antibody|herd immunity)\b", "PublicHealth"),
    (r"\b(historical|archive|primary source|narrative|discourse|colonialism|empire|revolution|chronicle)\b", "History"),
    (r"\b(ontology|epistemology|ethics|metaphysics|phenomenology|hermeneutics|logic|dialectic)\b", "Philosophy"),
    (r"\b(syntax|semantics|pragmatics|phonology|morphology|corpus|bilingual|language acquisition|grammar)\b", "Linguistics"),
    (r"\b(embodied cognition|cognitive architecture|mental model|dual process|working memory|schema)\b", "CognitiveScience"),
    (r"\b(nudge|heuristic|prospect theory|loss aversion|bounded rationality|behavioral economics)\b", "BehavioralEconomics"),
    (r"\b(complex network|agent.based|emergence|self.organization|nonlinear dynamics|chaos|attractor)\b", "ComplexSystems"),
    (r"\b(data pipeline|etl|feature engineering|model deployment|mlops|data lake|data warehouse)\b", "DataScience"),
]

# ── 하위 호환: 기존 BUILTIN_JOURNAL_MAP 별칭 ──────────────────────────────────
BUILTIN_JOURNAL_MAP: dict[str, str] = JOURNAL_MAP

# ── 주제 메타 정보 (UI 표시용) ────────────────────────────────────────────────
TOPIC_META: dict[str, dict] = {
    k: {"label": k, "icon": v[1], "desc": f"{v[0]} / {v[2]}"}
    for k, v in DISCIPLINE_MAP.items()
}


@dataclass
class ClassificationResult:
    """분류 결과 계약 객체."""
    discipline: str
    tier1: str
    display_name: str
    folder_path: str
    confidence: float
    method: str
    matched_evidence: str = ""
    subtopics: list[str] = field(default_factory=list)


class UniversalClassifier:
    """
    범용 과학 논문 분류기.

    책임:
      - 저널명 / 키워드 / LLM을 통한 3단계 분류
      - 사용자 정의 규칙 우선 적용
      - Obsidian 폴더 경로 생성
    """

    def __init__(self, user_rules: Optional[dict[str, str]] = None):
        self.user_rules: dict[str, str] = user_rules or {}

    def classify(
        self,
        journal: str = "",
        title: str = "",
        abstract: str = "",
        llm_fallback_fn=None,
    ) -> ClassificationResult:
        text = f"{journal} {title} {abstract}".lower()

        # 1순위: 사용자 정의 규칙
        for pattern, discipline in self.user_rules.items():
            if re.search(pattern, text, re.I):
                return self._build(discipline, 1.0, "user_rule", pattern)

        # 2순위: 저널명 직접 매핑
        journal_lower = journal.lower().strip()
        for key, discipline in JOURNAL_MAP.items():
            if key in journal_lower or journal_lower in key:
                return self._build(discipline, 0.95, "journal_map", journal)

        # 3순위: 키워드 패턴
        scores: dict[str, float] = {}
        for pattern, discipline in KEYWORD_PATTERNS:
            matches = re.findall(pattern, text, re.I)
            if matches:
                scores[discipline] = scores.get(discipline, 0) + len(matches) * 0.15

        if scores:
            best = max(scores, key=lambda k: scores[k])
            return self._build(best, min(scores[best], 0.90), "keyword",
                               f"score={scores[best]:.2f}")

        # 4순위: LLM 폴백
        if llm_fallback_fn and (journal or title):
            try:
                prompt = (
                    f"Classify this paper into ONE scientific discipline.\n"
                    f"Journal: {journal}\nTitle: {title}\n"
                    f"Return ONLY the discipline name from: "
                    f"{', '.join(DISCIPLINE_MAP.keys())}"
                )
                raw = llm_fallback_fn(prompt).strip()
                for key in DISCIPLINE_MAP:
                    if key.lower() in raw.lower():
                        return self._build(key, 0.70, "llm", raw)
            except Exception:
                pass

        return self._build("Uncategorized", 0.10, "fallback", "")

    def get_all_disciplines(self) -> list[dict]:
        result = []
        for tier1_key, tier1_name in TIER1.items():
            disciplines = [
                {"key": k, "icon": v[1], "folder": v[2], "tier1": tier1_key}
                for k, v in DISCIPLINE_MAP.items()
                if v[0] == tier1_key
            ]
            result.append({"tier1_key": tier1_key, "tier1_name": tier1_name,
                            "disciplines": disciplines})
        return result

    def get_folder_path(self, discipline: str, base: str = "Papers") -> str:
        info = DISCIPLINE_MAP.get(discipline, DISCIPLINE_MAP["Uncategorized"])
        return f"{base}/{info[2]}"

    def _build(self, discipline: str, confidence: float,
               method: str, evidence: str) -> ClassificationResult:
        info = DISCIPLINE_MAP.get(discipline, DISCIPLINE_MAP["Uncategorized"])
        tier1_key, icon, folder = info
        return ClassificationResult(
            discipline=discipline, tier1=tier1_key,
            display_name=f"{icon} {discipline}",
            folder_path=f"Papers/{folder}",
            confidence=confidence, method=method,
            matched_evidence=evidence,
        )


# ── 하위 호환 함수 (기존 코드에서 classify_by_journal 호출 유지) ──────────────
_classifier_instance: Optional[UniversalClassifier] = None


def get_classifier(user_rules: Optional[dict] = None) -> UniversalClassifier:
    global _classifier_instance
    if _classifier_instance is None or user_rules is not None:
        _classifier_instance = UniversalClassifier(user_rules)
    return _classifier_instance


def classify_paper(
    journal: str = "", title: str = "", abstract: str = "",
    user_rules: Optional[dict] = None, llm_fallback_fn=None,
) -> ClassificationResult:
    return get_classifier(user_rules).classify(journal, title, abstract, llm_fallback_fn)


def classify_by_journal(
    journal: str, title: str = "",
    custom_rules: Optional[dict[str, str]] = None,
) -> tuple[str, str]:
    """하위 호환: 기존 코드에서 사용하는 함수."""
    result = classify_paper(journal=journal, title=title, user_rules=custom_rules)
    return result.discipline, result.method


def get_topic_display(topic: str) -> str:
    meta = TOPIC_META.get(topic, {"icon": "📂", "label": topic})
    return f"{meta['icon']} {topic}"


def get_all_topics() -> list[dict]:
    return [{"folder": k, **v} for k, v in TOPIC_META.items()]


def load_custom_rules(config: dict) -> dict[str, str]:
    return config.get("classification_rules", {})
