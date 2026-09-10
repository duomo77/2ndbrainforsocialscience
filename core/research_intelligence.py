"""
research_intelligence.py -- deterministic research intelligence layer.

The compiler turns a paper/card/context into typed research objects before
rendering Markdown. It intentionally produces candidates with provenance and
review status rather than pretending local heuristics can resolve a field.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable

from core.research_context import EVIDENCE_EXPLICIT, EVIDENCE_INFERENCE, EVIDENCE_NOT_VERIFIED
from core.utils.markdown_utils import inject_frontmatter


SOURCE_FACT = "SOURCE_FACT"
AI_INFERENCE = "AI_INFERENCE"
OPEN_QUESTION = "OPEN_QUESTION"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass(frozen=True)
class ResearchMethodObject:
    name: str
    method_family: str
    research_design: str = ""
    identification_strategy: str = ""
    estimator: str = ""
    implementation: str = ""
    evidence_status: str = EVIDENCE_EXPLICIT


@dataclass(frozen=True)
class EvidenceObject:
    evidence_id: str
    text: str
    evidence_type: str = "TEXTUAL_EVIDENCE"
    source_paper: str = ""
    source_locator: str = "document_text"
    evidence_status: str = SOURCE_FACT


@dataclass(frozen=True)
class AssumptionObject:
    assumption_id: str
    name: str
    importance: str = "IMPORTANT"
    required_by: tuple[str, ...] = ()
    evidence_status: str = EVIDENCE_EXPLICIT


@dataclass(frozen=True)
class ClaimObject:
    claim_id: str
    text: str
    claim_type: str = "MAIN_CLAIM"
    source_paper: str = ""
    evidence_ids: tuple[str, ...] = ()
    assumption_ids: tuple[str, ...] = ()
    method_names: tuple[str, ...] = ()
    evidence_status: str = SOURCE_FACT
    confidence: str = "MEDIUM"


@dataclass(frozen=True)
class ResearchGapObject:
    gap_id: str
    text: str
    gap_type: str
    supporting_claim_ids: tuple[str, ...] = ()
    supporting_papers: tuple[str, ...] = ()
    confidence: str = "LOW"
    evidence_status: str = AI_INFERENCE


@dataclass(frozen=True)
class HypothesisObject:
    hypothesis_id: str
    text: str
    derived_from_gap_id: str
    status: str = "IDEA"
    quality_gate: dict[str, bool] = field(default_factory=dict)
    evidence_status: str = AI_INFERENCE


@dataclass(frozen=True)
class ContradictionCandidate:
    contradiction_id: str
    claim_a_id: str
    claim_b_id: str
    source_a: str
    source_b: str
    contradiction_type: str
    possible_explanation: str
    resolution_status: str = "HUMAN_REVIEW_REQUIRED"
    confidence: str = "LOW"


@dataclass(frozen=True)
class StructuredPaperObjects:
    paper_id: str
    title: str
    research_questions: tuple[str, ...] = ()
    claims: tuple[ClaimObject, ...] = ()
    evidence: tuple[EvidenceObject, ...] = ()
    assumptions: tuple[AssumptionObject, ...] = ()
    methods: tuple[ResearchMethodObject, ...] = ()
    gaps: tuple[ResearchGapObject, ...] = ()
    hypotheses: tuple[HypothesisObject, ...] = ()
    replication_requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchIntelligenceBundle:
    title: str
    intelligence_title: str
    markdown: str
    structured: StructuredPaperObjects
    methodology_atlas: dict[str, str] = field(default_factory=dict)
    contradictions: tuple[ContradictionCandidate, ...] = ()


_METHOD_SPECS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "Difference-in-Differences",
        "reduced-form causal",
        r"\b(?:difference[- ]in[- ]differences|DiD)\b",
        "Quasi-experimental panel or repeated cross-section design",
        "Treatment/control outcome changes are compared under a parallel-trends assumption",
        "Difference-in-differences regression or event-study regression",
    ),
    (
        "Regression Discontinuity",
        "reduced-form causal",
        r"\b(?:regression discontinuity|RDD)\b",
        "Quasi-experimental threshold design",
        "Discontinuity at an assignment cutoff identifies a local effect under continuity",
        "Local polynomial regression",
    ),
    (
        "Instrumental Variables",
        "reduced-form causal",
        r"\b(?:instrumental variables?|IV|2SLS)\b",
        "Quasi-experimental design using excluded variation",
        "Variation induced by an instrument identifies a local parameter under relevance and exclusion",
        "Two-stage least squares",
    ),
    (
        "Ordinary Least Squares",
        "quantitative",
        r"\b(?:OLS|ordinary least squares|linear regression)\b",
        "Associational or model-based regression design",
        "Identification requires design-specific exogeneity or selection assumptions",
        "Linear least squares",
    ),
    (
        "Case Study",
        "qualitative",
        r"\bcase stud",
        "Qualitative case-based design",
        "Interpretive leverage comes from case selection, process evidence, and rival explanation handling",
        "Structured qualitative analysis",
    ),
    (
        "Archival Research",
        "historical",
        r"\b(?:archive|archival|primary sources?)\b",
        "Historical source-based design",
        "Argument credibility depends on source criticism, coverage, and interpretation",
        "Document/source analysis",
    ),
)

_ASSUMPTION_SPECS: tuple[tuple[str, str], ...] = (
    ("Parallel Trends", r"\bparallel trends?\b"),
    ("Exogeneity", r"\bexogen"),
    ("Exclusion Restriction", r"\bexclusion restriction\b"),
    ("Continuity", r"\bcontinuity\b"),
    ("No Manipulation", r"\b(?:no manipulation|manipulat(?:e|ion))\b"),
    ("Source Reliability", r"\b(?:source criticism|source reliability|primary sources?)\b"),
)

_GAP_TYPES: tuple[tuple[str, str], ...] = (
    ("DATA GAP", r"\b(?:data limitation|limited data|new dataset|data gap|sample)\b"),
    ("IDENTIFICATION GAP", r"\b(?:identification problem|identify|identifying variation|endogeneity)\b"),
    ("MEASUREMENT GAP", r"\b(?:measurement|proxy|misclassif|measurement error)\b"),
    ("EXTERNAL VALIDITY GAP", r"\b(?:external validity|generaliz|single country|local effect)\b"),
    ("REPLICATION GAP", r"\b(?:replication|replicate|reproduce)\b"),
    ("MECHANISM GAP", r"\b(?:mechanism|channel|why)\b"),
)

_LIMITATION_RE = re.compile(
    r"([^.\n]*(?:limitation|future research|does not|cannot|unable to|not observe|unresolved|remains unclear)[^.\n]*[.])",
    re.IGNORECASE,
)
_CLAIM_RE = re.compile(
    r"([^.\n]*(?:we find|we show|we demonstrate|we argue|results show|evidence suggests|increases?|decreases?|has no effect|no significant effect)[^.\n]*[.])",
    re.IGNORECASE,
)
_EVIDENCE_RE = re.compile(
    r"([^.\n]*(?:data|sample|dataset|table|figure|estimate|result|evidence|survey|archive|primary source)[^.\n]*[.])",
    re.IGNORECASE,
)


def intelligence_note_title(title: str) -> str:
    clean = " ".join(str(title or "Untitled").split()).strip()
    return f"{clean} - Research Intelligence"


def build_research_intelligence(
    *,
    title: str,
    content: str,
    card_markdown: str = "",
    deep_context_markdown: str = "",
) -> ResearchIntelligenceBundle:
    haystack = "\n\n".join(part for part in (content, card_markdown, deep_context_markdown) if part)
    structured = decompose_paper(title=title, content=haystack)
    atlas = {
        method.name: render_methodology_atlas_note(method, title, structured)
        for method in structured.methods
    }
    markdown = render_research_intelligence(structured)
    return ResearchIntelligenceBundle(
        title=title,
        intelligence_title=intelligence_note_title(title),
        markdown=markdown,
        structured=structured,
        methodology_atlas=atlas,
    )


def decompose_paper(*, title: str, content: str) -> StructuredPaperObjects:
    paper_id = _stable_id("paper", title, content[:500])
    methods = tuple(_detect_methods(content))
    assumptions = tuple(_detect_assumptions(content, methods))
    evidence = tuple(_extract_evidence(content, title))
    claims = tuple(_extract_claims(content, title, evidence, assumptions, methods))
    gaps = tuple(_extract_gaps(content, title, claims))
    hypotheses = tuple(_hypotheses_from_gaps(gaps))
    questions = tuple(_extract_questions(content))
    replication = tuple(_replication_requirements(methods, content))
    return StructuredPaperObjects(
        paper_id=paper_id,
        title=title,
        research_questions=questions,
        claims=claims,
        evidence=evidence,
        assumptions=assumptions,
        methods=methods,
        gaps=gaps,
        hypotheses=hypotheses,
        replication_requirements=replication,
    )


def detect_cross_paper_contradictions(
    papers: Iterable[StructuredPaperObjects],
) -> tuple[ContradictionCandidate, ...]:
    claims = [claim for paper in papers for claim in paper.claims]
    contradictions: list[ContradictionCandidate] = []
    for left_index, left in enumerate(claims):
        for right in claims[left_index + 1 :]:
            if left.source_paper == right.source_paper:
                continue
            if not _same_subject(left.text, right.text):
                continue
            ctype = _claim_conflict_type(left.text, right.text)
            if not ctype:
                continue
            contradictions.append(
                ContradictionCandidate(
                    contradiction_id=_stable_id("contradiction", left.claim_id, right.claim_id, ctype),
                    claim_a_id=left.claim_id,
                    claim_b_id=right.claim_id,
                    source_a=left.source_paper,
                    source_b=right.source_paper,
                    contradiction_type=ctype,
                    possible_explanation=(
                        "Verify estimand, population, period, data, measurement, and identification "
                        "before treating this as a resolved contradiction."
                    ),
                    confidence="MEDIUM",
                )
            )
    return tuple(contradictions)


def mine_research_gaps(
    papers: Iterable[StructuredPaperObjects],
) -> tuple[ResearchGapObject, ...]:
    grouped: dict[str, list[ResearchGapObject]] = {}
    for paper in papers:
        for gap in paper.gaps:
            grouped.setdefault(gap.gap_type, []).append(gap)
    mined = []
    for gap_type, gaps in grouped.items():
        if len(gaps) < 2:
            continue
        supporting_papers = tuple(_unique(paper for gap in gaps for paper in gap.supporting_papers))
        supporting_claims = tuple(_unique(cid for gap in gaps for cid in gap.supporting_claim_ids))
        mined.append(
            ResearchGapObject(
                gap_id=_stable_id("gap_cluster", gap_type, *supporting_papers),
                text=f"Repeated {gap_type.lower()} appears across {len(supporting_papers)} papers.",
                gap_type=gap_type,
                supporting_claim_ids=supporting_claims,
                supporting_papers=supporting_papers,
                confidence="MEDIUM" if len(supporting_papers) >= 2 else "LOW",
                evidence_status=AI_INFERENCE,
            )
        )
    return tuple(mined)


def render_research_intelligence(structured: StructuredPaperObjects) -> str:
    body = "\n\n".join(
        [
            f"# Research Intelligence - {structured.title}",
            f"Source paper: [[{structured.title}]]",
            "## Research Objects",
            _render_research_objects(structured),
            "## Claim Evidence Assumption Graph",
            _render_claim_graph(structured),
            "## Methodology Atlas Links",
            _render_method_links(structured),
            "## Research Gap Candidates",
            _render_gaps(structured.gaps),
            "## Hypothesis Candidates",
            _render_hypotheses(structured.hypotheses),
            "## Replication Pack Skeleton",
            _render_replication(structured),
            "## Active Learning Tasks",
            _render_active_learning(structured),
            "## Integrity Gate",
            _render_integrity_gate(),
        ]
    )
    frontmatter = {
        "title": intelligence_note_title(structured.title),
        "type": "research_intelligence",
        "source_paper": structured.title,
        "paper_id": structured.paper_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "pipeline_version": "research-intelligence-v1",
        "human_verified": False,
        "object_count": (
            len(structured.claims)
            + len(structured.evidence)
            + len(structured.assumptions)
            + len(structured.methods)
            + len(structured.gaps)
            + len(structured.hypotheses)
        ),
    }
    return inject_frontmatter(body, frontmatter)


def render_methodology_atlas_note(
    method: ResearchMethodObject,
    source_title: str,
    structured: StructuredPaperObjects,
) -> str:
    method_assumptions = [
        assumption.name
        for assumption in structured.assumptions
        if method.name in assumption.required_by or not assumption.required_by
    ]
    body = "\n\n".join(
        [
            f"# Method - {method.name}",
            "## Canonical Structure",
            f"- Canonical name: [[{method.name}]]",
            f"- Method family: {method.method_family}",
            f"- Research design: {method.research_design or EVIDENCE_NOT_VERIFIED}",
            f"- Identification logic: {method.identification_strategy or EVIDENCE_NOT_VERIFIED}",
            f"- Estimator: {method.estimator or EVIDENCE_NOT_VERIFIED}",
            "- Implementation: `NOT_VERIFIED` unless software/package evidence is present.",
            "## Required Assumptions",
            "\n".join(f"- [[{name}]]" for name in method_assumptions) or f"`{EVIDENCE_NOT_VERIFIED}`",
            "## Diagnostics and Failure Modes",
            _method_failure_checklist(method.name),
            "## Source Applications",
            "\n".join(
                [
                    f"### [[{source_title}]]",
                    f"- Insight type: Method application",
                    f"- Source: [[{source_title}]]",
                    "- Page: `NOT_VERIFIED`",
                    f"- Confidence: `{AI_INFERENCE}`",
                    "- Human review: required before promoting to canonical method knowledge.",
                ]
            ),
        ]
    )
    return inject_frontmatter(
        body,
        {
            "title": f"Method - {method.name}",
            "type": "methodology_atlas",
            "canonical_name": method.name,
            "method_family": method.method_family,
            "human_verified": False,
            "source_papers": [source_title],
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )


def add_research_intelligence_link(card_markdown: str, title: str) -> str:
    link = f"[[{intelligence_note_title(title)}]]"
    if link in card_markdown:
        return card_markdown
    block = f"## Research Intelligence\n{link}\n"
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", card_markdown, re.DOTALL)
    if match:
        return card_markdown[: match.end()] + "\n" + block + "\n" + card_markdown[match.end():].lstrip()
    return block + "\n" + card_markdown.lstrip()


def merge_methodology_atlas_markdown(existing: str, generated: str, source_title: str) -> str:
    """Append a source application without erasing existing atlas content."""
    if not existing.strip():
        return generated
    if f"[[{source_title}]]" in existing:
        return existing
    application = re.search(r"## Source Applications\n(.+)$", generated, re.DOTALL)
    addition = application.group(1).strip() if application else f"### [[{source_title}]]\n- Confidence: `{AI_INFERENCE}`"
    if re.search(r"^## Source Applications\s*$", existing, re.MULTILINE):
        return existing.rstrip() + "\n\n" + addition + "\n"
    return existing.rstrip() + "\n\n## Source Applications\n\n" + addition + "\n"


def _detect_methods(content: str) -> list[ResearchMethodObject]:
    methods = []
    for name, family, pattern, design, identification, estimator in _METHOD_SPECS:
        if re.search(pattern, content, re.IGNORECASE):
            methods.append(
                ResearchMethodObject(
                    name=name,
                    method_family=family,
                    research_design=design,
                    identification_strategy=identification,
                    estimator=estimator,
                )
            )
    return methods


def _detect_assumptions(
    content: str,
    methods: tuple[ResearchMethodObject, ...] | list[ResearchMethodObject],
) -> list[AssumptionObject]:
    required_by = tuple(method.name for method in methods)
    assumptions = []
    for name, pattern in _ASSUMPTION_SPECS:
        if re.search(pattern, content, re.IGNORECASE):
            assumptions.append(
                AssumptionObject(
                    assumption_id=_stable_id("assumption", name, content[:120]),
                    name=name,
                    required_by=required_by,
                )
            )
    return assumptions


def _extract_evidence(content: str, title: str) -> list[EvidenceObject]:
    evidence = []
    for match in _EVIDENCE_RE.finditer(content):
        text = _clean_sentence(match.group(1))
        evidence.append(
            EvidenceObject(
                evidence_id=_stable_id("evidence", title, text),
                text=text,
                source_paper=title,
            )
        )
        if len(evidence) >= 8:
            break
    return evidence


def _extract_claims(
    content: str,
    title: str,
    evidence: tuple[EvidenceObject, ...],
    assumptions: tuple[AssumptionObject, ...],
    methods: tuple[ResearchMethodObject, ...],
) -> list[ClaimObject]:
    claims = []
    evidence_ids = tuple(item.evidence_id for item in evidence[:3])
    assumption_ids = tuple(item.assumption_id for item in assumptions)
    method_names = tuple(item.name for item in methods)
    for match in _CLAIM_RE.finditer(content):
        text = _clean_sentence(match.group(1))
        claims.append(
            ClaimObject(
                claim_id=_stable_id("claim", title, text),
                text=text,
                source_paper=title,
                evidence_ids=evidence_ids,
                assumption_ids=assumption_ids,
                method_names=method_names,
            )
        )
        if len(claims) >= 8:
            break
    if not claims:
        question = next(iter(_extract_questions(content)), "")
        if question:
            text = f"The paper addresses: {question}"
            claims.append(
                ClaimObject(
                    claim_id=_stable_id("claim", title, text),
                    text=text,
                    claim_type="QUESTION_CLAIM",
                    source_paper=title,
                    evidence_ids=evidence_ids,
                    assumption_ids=assumption_ids,
                    method_names=method_names,
                    evidence_status=AI_INFERENCE,
                    confidence="LOW",
                )
            )
    return claims


def _extract_gaps(content: str, title: str, claims: tuple[ClaimObject, ...]) -> list[ResearchGapObject]:
    gaps = []
    claim_ids = tuple(claim.claim_id for claim in claims[:3])
    for match in _LIMITATION_RE.finditer(content):
        text = _clean_sentence(match.group(1))
        gaps.append(
            ResearchGapObject(
                gap_id=_stable_id("gap", title, text),
                text=text,
                gap_type=_classify_gap(text),
                supporting_claim_ids=claim_ids,
                supporting_papers=(title,),
                confidence="LOW",
            )
        )
        if len(gaps) >= 5:
            break
    if not gaps and claims:
        inferred = "Verify whether the paper leaves an identification, measurement, external-validity, or mechanism gap."
        gaps.append(
            ResearchGapObject(
                gap_id=_stable_id("gap", title, inferred),
                text=inferred,
                gap_type="RESEARCH GAP",
                supporting_claim_ids=claim_ids,
                supporting_papers=(title,),
                confidence="SPECULATIVE",
            )
        )
    return gaps


def _hypotheses_from_gaps(gaps: tuple[ResearchGapObject, ...] | list[ResearchGapObject]) -> list[HypothesisObject]:
    hypotheses = []
    for gap in gaps:
        text = f"A follow-up study could test whether {gap.text.rstrip('.').lower()} changes the paper's central interpretation."
        gate = {
            "mechanism_explicit": False,
            "outcome_defined": False,
            "treatment_or_exposure_defined": False,
            "identifying_variation_defined": False,
            "novel_relative_to_local_literature": False,
        }
        hypotheses.append(
            HypothesisObject(
                hypothesis_id=_stable_id("hypothesis", gap.gap_id, text),
                text=text,
                derived_from_gap_id=gap.gap_id,
                quality_gate=gate,
            )
        )
    return hypotheses[:5]


def _extract_questions(content: str) -> list[str]:
    questions = []
    for pattern in (
        r"(?:research question|core question|question)\s*[:\-]\s*([^.\n?]+[?]?)",
        r"([^.\n?]*\?)",
    ):
        for match in re.finditer(pattern, content, re.IGNORECASE):
            question = _clean_sentence(match.group(1))
            question = re.sub(
                r"^(?:research question|core question|question)\s*[:\-]\s*",
                "",
                question,
                flags=re.IGNORECASE,
            )
            if question:
                if not question.endswith("?"):
                    question += "?"
                questions.append(question)
            if len(questions) >= 5:
                return _unique(questions)
    return _unique(questions)


def _replication_requirements(methods: tuple[ResearchMethodObject, ...], content: str) -> list[str]:
    requirements = ["Source paper and exact analysis sample", "Variable definitions", "Replication code status"]
    if methods:
        requirements.extend([f"Estimator implementation for {method.name}" for method in methods])
    if re.search(r"\bstandard errors?|cluster", content, re.IGNORECASE):
        requirements.append("Standard-error and clustering specification")
    return _unique(requirements)


def _classify_gap(text: str) -> str:
    for label, pattern in _GAP_TYPES:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return "RESEARCH GAP"


def _same_subject(left: str, right: str) -> bool:
    left_words = _content_words(left)
    right_words = _content_words(right)
    return len(left_words & right_words) >= 2


def _claim_conflict_type(left: str, right: str) -> str:
    left_direction = _effect_direction(left)
    right_direction = _effect_direction(right)
    if left_direction and right_direction and left_direction != right_direction:
        return "EMPIRICAL_RESULT_CONTRADICTION"
    return ""


def _effect_direction(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(no effect|no significant effect|zero effect)\b", lower):
        return "zero"
    if re.search(r"\b(increase|increases|positive|raises|improves)\b", lower):
        return "positive"
    if re.search(r"\b(decrease|decreases|negative|reduces|lowers)\b", lower):
        return "negative"
    return ""


def _render_research_objects(structured: StructuredPaperObjects) -> str:
    return "\n".join(
        [
            f"- Research questions: {len(structured.research_questions)}",
            f"- Claims: {len(structured.claims)}",
            f"- Evidence objects: {len(structured.evidence)}",
            f"- Assumptions: {len(structured.assumptions)}",
            f"- Methods: {len(structured.methods)}",
            f"- Research gaps: {len(structured.gaps)}",
            f"- Hypotheses: {len(structured.hypotheses)}",
            "- Human review status: `HUMAN_REVIEW_REQUIRED`",
        ]
    )


def _render_claim_graph(structured: StructuredPaperObjects) -> str:
    if not structured.claims:
        return f"`{EVIDENCE_NOT_VERIFIED}` - No claim objects were safely extracted."
    blocks = []
    evidence_by_id = {item.evidence_id: item for item in structured.evidence}
    assumption_by_id = {item.assumption_id: item for item in structured.assumptions}
    for claim in structured.claims:
        evidence_lines = [
            f"  - Supported by: `{eid}` - {evidence_by_id[eid].text}"
            for eid in claim.evidence_ids
            if eid in evidence_by_id
        ] or ["  - Supported by: `NOT_VERIFIED`"]
        assumption_lines = [
            f"  - Depends on: [[{assumption_by_id[aid].name}]]"
            for aid in claim.assumption_ids
            if aid in assumption_by_id
        ] or ["  - Depends on: `NOT_VERIFIED`"]
        method_lines = [f"  - Produced through: [[{name}]]" for name in claim.method_names] or [
            "  - Produced through: `NOT_VERIFIED`"
        ]
        blocks.append(
            "\n".join(
                [
                    f"### Claim `{claim.claim_id}`",
                    f"- Text: {claim.text}",
                    f"- Claim type: `{claim.claim_type}`",
                    f"- Evidence status: `{claim.evidence_status}`",
                    *evidence_lines,
                    *assumption_lines,
                    *method_lines,
                ]
            )
        )
    return "\n\n".join(blocks)


def _render_method_links(structured: StructuredPaperObjects) -> str:
    if not structured.methods:
        return f"`{EVIDENCE_NOT_VERIFIED}` - No method object was detected."
    return "\n".join(f"- [[Method - {method.name}]]" for method in structured.methods)


def _render_gaps(gaps: tuple[ResearchGapObject, ...]) -> str:
    if not gaps:
        return f"`{EVIDENCE_NOT_VERIFIED}` - No gap candidate."
    return "\n\n".join(
        [
            "\n".join(
                [
                    f"### {gap.gap_type}",
                    f"- Gap ID: `{gap.gap_id}`",
                    f"- Claim: {gap.text}",
                    f"- Confidence: `{gap.confidence}`",
                    f"- Evidence status: `{gap.evidence_status}`",
                    f"- Supporting papers: {', '.join(f'[[{paper}]]' for paper in gap.supporting_papers)}",
                ]
            )
            for gap in gaps
        ]
    )


def _render_hypotheses(hypotheses: tuple[HypothesisObject, ...]) -> str:
    if not hypotheses:
        return f"`{EVIDENCE_NOT_VERIFIED}` - No hypothesis candidate."
    blocks = []
    for hypothesis in hypotheses:
        gate = "\n".join(
            f"  - {name}: `{str(value).upper()}`"
            for name, value in hypothesis.quality_gate.items()
        )
        blocks.append(
            "\n".join(
                [
                    f"### Hypothesis `{hypothesis.hypothesis_id}`",
                    f"- Status: `{hypothesis.status}`",
                    f"- Derived from gap: `{hypothesis.derived_from_gap_id}`",
                    f"- Text: {hypothesis.text}",
                    "- Quality gate:",
                    gate,
                ]
            )
        )
    return "\n\n".join(blocks)


def _render_replication(structured: StructuredPaperObjects) -> str:
    requirements = "\n".join(f"- [ ] {item}" for item in structured.replication_requirements)
    return "\n".join(
        [
            "- Feasibility: `UNKNOWN`",
            "- Code status: `SKELETON_NOT_YET_VERIFIED`",
            "- Required items:",
            requirements,
        ]
    )


def _render_active_learning(structured: StructuredPaperObjects) -> str:
    method = structured.methods[0].name if structured.methods else "the paper's method"
    return "\n".join(
        [
            "- Explain the research question without quoting the abstract.",
            f"- Separate [[{method}]] from identification and estimation.",
            "- Name the assumption doing the most work.",
            "- Identify one evidence object supporting the main claim.",
            "- Turn one research gap candidate into a testable design.",
        ]
    )


def _render_integrity_gate() -> str:
    return "\n".join(
        [
            "- Is the source known? `YES`",
            "- Is provenance preserved? `YES`",
            "- Is this source fact or synthesis? Marked per object.",
            "- Is confidence high enough for permanent promotion? `HUMAN_REVIEW_REQUIRED`",
            "- Does contradictory evidence exist? `NOT_VERIFIED` until cross-paper scan runs.",
            "- Will this overwrite human interpretation? `NO`; generated artifacts require review.",
        ]
    )


def _method_failure_checklist(method_name: str) -> str:
    checklists = {
        "Difference-in-Differences": [
            "Parallel trends",
            "Anticipation",
            "Treatment timing",
            "Heterogeneous treatment effects",
            "Clustering",
            "Composition changes",
        ],
        "Regression Discontinuity": [
            "Manipulation near cutoff",
            "Bandwidth sensitivity",
            "Covariate balance",
            "Functional form",
            "Fuzzy compliance",
        ],
        "Instrumental Variables": [
            "Weak instruments",
            "Exclusion restriction",
            "Monotonicity",
            "First-stage strength",
            "Local estimand interpretation",
        ],
    }
    items = checklists.get(method_name, ["Measurement error", "Sample selection", "Model misspecification"])
    return "\n".join(f"- [ ] {item}" for item in items)


def _content_words(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "effect",
        "effects",
        "paper",
        "study",
        "find",
        "finds",
        "show",
        "shows",
        "result",
        "results",
    }
    return {word for word in re.findall(r"[a-z]{4,}", text.lower()) if word not in stop}


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "\x1f".join(str(part).strip().casefold() for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _clean_sentence(value: str) -> str:
    return " ".join(str(value or "").split()).strip(" -")


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
