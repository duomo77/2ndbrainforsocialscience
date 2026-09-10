"""
research_context.py -- Deep Research Context compiler.

This module builds the second paper-ingestion layer requested by the ROS audit:
a researcher-oriented context note that is separate from the compact paper card.
It is deliberately conservative. It uses the target paper/card/local vault signals
available during ingestion and labels unsupported lineage claims as not verified
instead of inventing background literature.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.utils.markdown_utils import inject_frontmatter


EVIDENCE_EXPLICIT = "EXPLICIT_IN_TARGET_PAPER"
EVIDENCE_LOCAL = "SUPPORTED_BY_LOCAL_VAULT"
EVIDENCE_SYNTHESIS = "AI_SYNTHESIS"
EVIDENCE_INFERENCE = "AI_INFERENCE"
EVIDENCE_NOT_VERIFIED = "NOT_VERIFIED"
LINEAGE_NOT_VERIFIED = "LITERATURE LINEAGE NOT SUFFICIENTLY VERIFIED"


@dataclass(frozen=True)
class BackgroundConcept:
    name: str
    priority: str = "USEFUL"
    evidence_status: str = EVIDENCE_INFERENCE
    rationale: str = ""


@dataclass(frozen=True)
class MethodSignal:
    name: str
    family: str
    evidence_status: str = EVIDENCE_EXPLICIT


@dataclass(frozen=True)
class ResearchContext:
    title: str
    context_title: str
    markdown: str
    concepts: tuple[BackgroundConcept, ...] = field(default_factory=tuple)
    methods: tuple[MethodSignal, ...] = field(default_factory=tuple)
    evidence_status: str = EVIDENCE_SYNTHESIS


_METHOD_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("Difference-in-Differences", "reduced-form causal", r"\b(?:difference[- ]in[- ]differences|DiD)\b"),
    ("Regression Discontinuity", "reduced-form causal", r"\b(?:regression discontinuity|RDD)\b"),
    ("Instrumental Variables", "reduced-form causal", r"\b(?:instrumental variables?|IV|2SLS)\b"),
    ("Ordinary Least Squares", "quantitative", r"\b(?:OLS|ordinary least squares|linear regression)\b"),
    ("Panel Fixed Effects", "quantitative", r"\b(?:fixed effects?|panel data)\b"),
    ("Randomized Controlled Trial", "experimental", r"\b(?:randomi[sz]ed controlled trial|RCT|experiment)\b"),
    ("Propensity Score Matching", "reduced-form causal", r"\bpropensity score|matching\b"),
    ("Double Machine Learning", "causal machine learning", r"\b(?:double machine learning|DML|orthogonal)\b"),
    ("Event Study", "reduced-form causal", r"\bevent study\b"),
    ("Ethnography", "qualitative", r"\bethnograph"),
    ("Interview", "qualitative", r"\binterviews?\b"),
    ("Discourse Analysis", "humanities/qualitative", r"\bdiscourse analysis\b"),
    ("Process Tracing", "qualitative", r"\bprocess tracing\b"),
    ("Archival Research", "historical", r"\b(?:archive|archival|primary sources?)\b"),
    ("Case Study", "qualitative", r"\bcase stud"),
)

_ASSUMPTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Parallel Trends", r"\bparallel trends?\b"),
    ("Exogeneity", r"\bexogen"),
    ("Exclusion Restriction", r"\bexclusion restriction\b"),
    ("Continuity", r"\bcontinuity\b"),
    ("No Manipulation", r"\b(?:no manipulation|manipulat(?:e|ion))\b"),
    ("Conditional Independence", r"\bconditional independence\b"),
    ("Stable Unit Treatment Value", r"\b(?:SUTVA|stable unit treatment)\b"),
    ("External Validity", r"\bexternal validity\b"),
    ("Source Reliability", r"\b(?:source criticism|reliability of sources|archive)\b"),
)

_CONCEPT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Identification", r"\bidentif"),
    ("Estimator", r"\bestimat"),
    ("Treatment Effect", r"\btreatment effect\b|\bATE\b|\bCATE\b"),
    ("Selection Bias", r"\bselection bias\b"),
    ("Counterfactual", r"\bcounterfactual"),
    ("Measurement", r"\bmeasurement\b"),
    ("Causal Inference", r"\bcausal\b"),
    ("Research Design", r"\bresearch design\b"),
    ("Inference", r"\binference\b"),
    ("Robustness", r"\brobustness\b"),
    ("Historical Context", r"\bhistorical\b"),
    ("Institutional Context", r"\binstitution"),
    ("Interpretive Framework", r"\binterpretive|hermeneutic|constructiv"),
    ("Source Criticism", r"\bsource criticism|primary source"),
)


def context_note_title(title: str) -> str:
    clean = " ".join(str(title or "Untitled").split()).strip()
    return f"{clean} - Deep Research Context"


def build_deep_research_context(
    *,
    title: str,
    content: str,
    card_markdown: str,
    metadata: dict[str, Any] | None = None,
    existing_nodes: list[str] | None = None,
    rag_context: str = "",
    depth: str = "standard",
) -> ResearchContext:
    """Build a conservative deep context note for an ingested paper."""
    metadata = dict(metadata or {})
    existing_nodes = existing_nodes or []
    clean_depth = _normalize_depth(depth)
    context_title = context_note_title(title)
    source_hash = hashlib.sha256((content or "").encode("utf-8")).hexdigest()[:16]
    methods = tuple(_detect_methods(content, card_markdown))
    concepts = tuple(_detect_concepts(content, card_markdown, existing_nodes, methods))
    assumptions = _detect_assumptions(content, card_markdown)
    question = _extract_research_question(content, card_markdown)
    contribution = _extract_contribution(content, card_markdown)
    references = _extract_reference_candidates(content)
    epistemic_mode = _infer_epistemic_mode(methods, content)
    now = datetime.now(UTC).isoformat()

    body = "\n\n".join(
        [
            f"# Deep Research Context - {title}",
            f"Source paper: [[{title}]]",
            "",
            "## Evidence Status",
            _evidence_status_block(),
            "## 1. Why This Paper Exists",
            _why_exists(question, contribution),
            "## 2. Historical and Intellectual Background",
            _historical_background(content, epistemic_mode),
            "## 3. The Research Problem Before This Paper",
            _research_problem(question, contribution),
            "## 4. Core Research Question",
            _status_line(question or "Core question not explicitly recovered from available text.", EVIDENCE_INFERENCE if question else EVIDENCE_NOT_VERIFIED),
            "## 5. Why the Question Matters",
            _status_line(_why_question_matters(methods, concepts), EVIDENCE_SYNTHESIS),
            "## 6. Required Background Concepts",
            _render_concepts(concepts),
            "## 7. Theoretical Background",
            _theoretical_background(epistemic_mode, concepts),
            "## 8. Empirical / Historical Background",
            _empirical_background(content, epistemic_mode),
            "## 9. Methodological Background",
            _render_methodological_background(methods),
            "## 10. Identification Background",
            _render_identification_background(methods, assumptions),
            "## 11. Key Predecessor Literature",
            _render_predecessor_literature(references),
            "## 12. Competing Approaches in the Literature",
            _status_line("Competing approaches require cited-source or vault verification before they can be reconstructed.", EVIDENCE_NOT_VERIFIED),
            "## 13. What Was Missing Before This Paper",
            _render_research_gap(methods, question),
            "## 14. What This Paper Changes",
            _render_contribution_decomposition(contribution, methods),
            "## 15. Key Assumptions",
            _render_assumptions(assumptions),
            "## 16. How to Read the Main Equations / Arguments",
            _render_equation_or_argument_guidance(content, methods),
            "## 17. Results in Context",
            _status_line("Result-to-literature positioning requires verified predecessor or later-literature evidence. Treat current result context as not verified.", EVIDENCE_NOT_VERIFIED),
            "## 18. What the Paper Does Not Resolve",
            _render_unresolved(methods),
            "## 19. Later Extensions and Related Questions",
            _status_line("Later extensions were not externally verified during this local ingestion pass.", EVIDENCE_NOT_VERIFIED),
            "## 20. What to Read Before This Paper",
            _render_read_before(concepts, methods),
            "## 21. What to Read After This Paper",
            _status_line("Read-after recommendations require a later-literature provider or already-ingested vault context.", EVIDENCE_NOT_VERIFIED),
            "## 22. Research Opportunities",
            _render_research_opportunities(methods, assumptions),
            "## 23. Connection to Existing Vault Knowledge",
            _render_vault_connections(existing_nodes, content, rag_context),
            "## 24. Open Questions for the Researcher",
            _render_open_questions(methods, assumptions),
            "# How to Study This Paper",
            _render_study_guide(concepts, methods),
            "## Missing Background",
            _render_missing_background(references),
        ]
    )

    frontmatter = {
        "title": context_title,
        "type": "research_context",
        "source_paper": title,
        "paper_id": source_hash,
        "generated_at": now,
        "pipeline_version": "deep-context-v1",
        "depth": clean_depth,
        "human_verified": False,
        "background_status": EVIDENCE_SYNTHESIS,
        "literature_verified": False,
        "methodology_verified": bool(methods),
        "evidence_policy": "explicit_status_per_section",
        "source_hash": source_hash,
    }
    markdown = inject_frontmatter(body, frontmatter)
    return ResearchContext(
        title=title,
        context_title=context_title,
        markdown=markdown,
        concepts=concepts,
        methods=methods,
    )


def add_deep_context_link(card_markdown: str, title: str) -> str:
    """Link the compact paper card to its sibling deep context note."""
    link = f"[[{context_note_title(title)}]]"
    if link in card_markdown:
        return card_markdown
    block = f"## Deep Context\n{link}\n"
    if card_markdown.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n?", card_markdown, re.DOTALL)
        if match:
            return card_markdown[: match.end()] + "\n" + block + "\n" + card_markdown[match.end():].lstrip()
    return block + "\n" + card_markdown.lstrip()


def _normalize_depth(depth: str) -> str:
    value = str(depth or "standard").strip().lower()
    return value if value in {"compact", "standard", "deep"} else "standard"


def _detect_methods(content: str, card_markdown: str) -> list[MethodSignal]:
    haystack = f"{content}\n\n{card_markdown}"
    found: list[MethodSignal] = []
    for name, family, pattern in _METHOD_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            found.append(MethodSignal(name=name, family=family))
    return found


def _detect_concepts(
    content: str,
    card_markdown: str,
    existing_nodes: list[str],
    methods: tuple[MethodSignal, ...] | list[MethodSignal],
) -> list[BackgroundConcept]:
    haystack = f"{content}\n\n{card_markdown}"
    concepts: list[BackgroundConcept] = []
    for method in methods:
        concepts.append(
            BackgroundConcept(
                name=method.name,
                priority="ESSENTIAL",
                evidence_status=method.evidence_status,
                rationale=f"Detected method signal in the target paper/card ({method.family}).",
            )
        )
    for name, pattern in _CONCEPT_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            concepts.append(
                BackgroundConcept(
                    name=name,
                    priority="ESSENTIAL" if name in {"Identification", "Causal Inference", "Research Design"} else "USEFUL",
                    evidence_status=EVIDENCE_EXPLICIT,
                    rationale="Term appears in the available target-paper text or generated card.",
                )
            )
    lower = haystack.lower()
    for node in existing_nodes[:20]:
        clean = " ".join(str(node).split()).strip()
        if clean and clean.lower() in lower:
            concepts.append(
                BackgroundConcept(
                    name=clean,
                    priority="USEFUL",
                    evidence_status=EVIDENCE_LOCAL,
                    rationale="Existing vault concept also appears in the target-paper context.",
                )
            )
    return _unique_concepts(concepts)[:12]


def _detect_assumptions(content: str, card_markdown: str) -> list[tuple[str, str]]:
    haystack = f"{content}\n\n{card_markdown}"
    found = []
    for name, pattern in _ASSUMPTION_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            found.append((name, EVIDENCE_EXPLICIT))
    return found


def _extract_research_question(content: str, card_markdown: str) -> str:
    for haystack in (card_markdown, content):
        match = re.search(
            r"(?:research question|core question|question)\s*[:\-]\s*(.+?)(?:\n|$)",
            haystack,
            re.IGNORECASE,
        )
        if match:
            return _clean_sentence(match.group(1))
    question_sentence = re.search(r"([^.\n?]*\?)(?:\s|$)", content)
    if question_sentence:
        return _clean_sentence(question_sentence.group(1))
    return ""


def _extract_contribution(content: str, card_markdown: str) -> str:
    haystack = f"{card_markdown}\n\n{content}"
    match = re.search(
        r"(?:contribution|adds?|changes?|introduces?|we (?:show|find|demonstrate|argue))[^.\n]*[.\n]",
        haystack,
        re.IGNORECASE,
    )
    return _clean_sentence(match.group(0)) if match else ""


def _extract_reference_candidates(content: str) -> list[str]:
    references_section = re.search(
        r"(?:^|\n)(?:references|bibliography)\s*\n(.+)$",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    source = references_section.group(1) if references_section else content
    candidates = []
    for line in source.splitlines():
        clean = " ".join(line.split()).strip(" -")
        if re.search(r"\b(19|20)\d{2}\b", clean) and len(clean) > 12:
            candidates.append(clean[:220])
        if len(candidates) >= 8:
            break
    return candidates


def _infer_epistemic_mode(methods: tuple[MethodSignal, ...], content: str) -> str:
    families = {method.family for method in methods}
    lower = content.lower()
    if any("historical" in family for family in families) or "archive" in lower:
        return "historical"
    if any("qualitative" in family for family in families):
        return "qualitative"
    if any("causal" in family or family in {"quantitative", "experimental"} for family in families):
        return "quantitative"
    if re.search(r"\b(theory|model|proposition|equilibrium)\b", lower):
        return "theoretical"
    return "mixed_or_uncertain"


def _evidence_status_block() -> str:
    return "\n".join(
        [
            f"- `{EVIDENCE_EXPLICIT}`: directly recovered from the target paper/card text.",
            f"- `{EVIDENCE_LOCAL}`: supported by concepts already present in the local vault/RAG context.",
            f"- `{EVIDENCE_SYNTHESIS}`: generated by combining available local evidence.",
            f"- `{EVIDENCE_INFERENCE}`: plausible interpretation that requires researcher verification.",
            f"- `{EVIDENCE_NOT_VERIFIED}`: intentionally left unclaimed until source verification is available.",
        ]
    )


def _why_exists(question: str, contribution: str) -> str:
    if question or contribution:
        parts = []
        if question:
            parts.append(f"- {_status_line('The paper is organized around: ' + question, EVIDENCE_INFERENCE)}")
        if contribution:
            parts.append(f"- {_status_line('Recovered contribution signal: ' + contribution, EVIDENCE_EXPLICIT)}")
        parts.append(f"- {_status_line('The deeper motivation still requires checking the introduction and cited predecessor literature.', EVIDENCE_NOT_VERIFIED)}")
        return "\n".join(parts)
    return _status_line("The motivating problem was not explicitly recovered from the available text. Review the introduction before treating this context as complete.", EVIDENCE_NOT_VERIFIED)


def _historical_background(content: str, epistemic_mode: str) -> str:
    if epistemic_mode == "historical":
        return _status_line("Historical or archival signals are present. Verify the period, geography, primary sources, and historiographic debate before expanding this section.", EVIDENCE_INFERENCE)
    if re.search(r"\b(policy|institution|reform|law|market|crisis)\b", content, re.IGNORECASE):
        return _status_line("Institutional or policy signals are present, so the reader likely needs contextual background on the relevant setting.", EVIDENCE_INFERENCE)
    return _status_line("No specific historical background was verified during local ingestion.", EVIDENCE_NOT_VERIFIED)


def _research_problem(question: str, contribution: str) -> str:
    if not (question or contribution):
        return _status_line("Existing knowledge, limitation, unresolved puzzle, and gap could not be reconstructed safely from local evidence.", EVIDENCE_NOT_VERIFIED)
    return "\n".join(
        [
            f"- Existing knowledge: `{EVIDENCE_NOT_VERIFIED}` predecessor literature not yet verified.",
            f"- Known limitation: `{EVIDENCE_INFERENCE}` inferred from the recovered question/contribution.",
            f"- Unresolved puzzle: {question or 'not explicitly recovered.'}",
            f"- This paper: {contribution or 'contribution requires manual verification.'}",
        ]
    )


def _why_question_matters(methods: tuple[MethodSignal, ...], concepts: tuple[BackgroundConcept, ...]) -> str:
    if methods:
        method_names = ", ".join(method.name for method in methods[:3])
        return f"The question matters partly because evaluating it requires the reader to understand {method_names} and its assumptions."
    if concepts:
        concept_names = ", ".join(concept.name for concept in concepts[:3])
        return f"The question matters because it touches prerequisite concepts such as {concept_names}."
    return "The importance of the question requires more source evidence before it can be reconstructed."


def _render_concepts(concepts: tuple[BackgroundConcept, ...]) -> str:
    if not concepts:
        return _status_line("No prerequisite concepts were confidently extracted. Add concepts after reading the introduction/method sections.", EVIDENCE_NOT_VERIFIED)
    blocks = []
    for concept in concepts:
        blocks.append(
            "\n".join(
                [
                    f"### {concept.name}",
                    f"- Priority: `{concept.priority}`",
                    f"- Evidence status: `{concept.evidence_status}`",
                    f"- Definition: `{EVIDENCE_NOT_VERIFIED}` requires a concept note or source-backed definition.",
                    f"- Intuition: {_concept_intuition(concept.name)}",
                    f"- Why it matters for this paper: {concept.rationale or 'Requires researcher verification.'}",
                    "- Minimal formalism: Add only if the paper uses formal notation for this concept.",
                    "- Related concepts: verify against existing vault links before expanding.",
                    "- Common confusion: keep separate from author claims until verified.",
                ]
            )
        )
    return "\n\n".join(blocks)


def _concept_intuition(name: str) -> str:
    if name == "Identification":
        return "separate what can be learned from the data/design from how the estimate is computed."
    if name == "Selection Bias":
        return "ask whether comparison groups differ for reasons related to the outcome."
    if name == "Counterfactual":
        return "track the unobserved alternative state that gives a causal claim meaning."
    if name == "Source Criticism":
        return "ask who produced the source, why, what it omits, and how it can mislead."
    return "explain this only in relation to the target paper, not as an encyclopedia entry."


def _theoretical_background(epistemic_mode: str, concepts: tuple[BackgroundConcept, ...]) -> str:
    concept_links = ", ".join(f"[[{concept.name}]]" for concept in concepts[:5])
    if epistemic_mode == "qualitative":
        return _status_line("Identify the interpretive tradition, theory of meaning, and evidence strategy before expanding this section.", EVIDENCE_INFERENCE)
    if epistemic_mode == "historical":
        return _status_line("Identify the historiographic debate and source-critical framework before expanding this section.", EVIDENCE_INFERENCE)
    if concept_links:
        return _status_line(f"The theoretical background should be developed through {concept_links}.", EVIDENCE_SYNTHESIS)
    return _status_line("The theoretical tradition was not verified from local evidence.", EVIDENCE_NOT_VERIFIED)


def _empirical_background(content: str, epistemic_mode: str) -> str:
    if epistemic_mode == "historical":
        return _status_line("Recover period, region, archive, primary sources, and existing historiography from the paper before use.", EVIDENCE_INFERENCE)
    if re.search(r"\b(data|sample|dataset|survey|panel|administrative)\b", content, re.IGNORECASE):
        return _status_line("Data/sample signals are present. The reader needs the unit of analysis, population, measurement, and institutional data source.", EVIDENCE_INFERENCE)
    return _status_line("Empirical setting was not sufficiently recovered.", EVIDENCE_NOT_VERIFIED)


def _render_methodological_background(methods: tuple[MethodSignal, ...]) -> str:
    if not methods:
        return _status_line("Method could not be extracted confidently. Do not infer estimator, design, or qualitative method without reviewing the methods section.", EVIDENCE_NOT_VERIFIED)
    blocks = []
    for method in methods:
        blocks.append(
            "\n".join(
                [
                    f"### [[{method.name}]]",
                    f"- Evidence status: `{method.evidence_status}`",
                    f"- What problem is the method solving? `{EVIDENCE_INFERENCE}` clarify from the paper's design section.",
                    "- What parameter is being estimated or interpreted? Not yet verified.",
                    "- What identifies the parameter or supports the interpretation? See Identification Background.",
                    "- Why this method? Verify whether alternatives are discussed by the authors.",
                    "- What can go wrong? Inspect assumptions, measurement, comparison group/case selection, and robustness.",
                    "- Diagnostics to inspect: design-specific diagnostics should be added after source verification.",
                ]
            )
        )
    return "\n\n".join(blocks)


def _render_identification_background(methods: tuple[MethodSignal, ...], assumptions: list[tuple[str, str]]) -> str:
    if not methods:
        return _status_line("Identification cannot be reconstructed until the method/research design is verified.", EVIDENCE_NOT_VERIFIED)
    assumption_names = ", ".join(name for name, _status in assumptions) or "the design-specific identifying assumptions"
    return "\n".join(
        [
            f"- Parameter: `{EVIDENCE_NOT_VERIFIED}` not yet extracted.",
            f"- Observed variation: `{EVIDENCE_NOT_VERIFIED}` not yet extracted.",
            f"- Identification assumption: `{EVIDENCE_INFERENCE}` likely depends on {assumption_names}.",
            "- Estimand: keep separate from estimator until explicitly recovered.",
            "- Estimator: see Methodological Background. Do not conflate this with identification.",
            "",
            f"> Parameter ______ is identified by variation in ______ under the assumption that {assumption_names}.",
        ]
    )


def _render_predecessor_literature(references: list[str]) -> str:
    if not references:
        return _status_line(LINEAGE_NOT_VERIFIED, EVIDENCE_NOT_VERIFIED)
    blocks = [
        _status_line("The following are reference candidates extracted locally. Their role in the lineage is not verified until checked against the target paper and bibliographic sources.", EVIDENCE_NOT_VERIFIED)
    ]
    for ref in references[:5]:
        blocks.append(
            "\n".join(
                [
                    f"### {ref}",
                    "- Role in the literature: `NOT_VERIFIED`",
                    "- Main question: `NOT_VERIFIED`",
                    "- Key contribution: `NOT_VERIFIED`",
                    "- Why this matters for the target paper: `NOT_VERIFIED`",
                    "- Relationship to target paper: verify before promoting to foundational/direct predecessor/method foundation.",
                ]
            )
        )
    return "\n\n".join(blocks)


def _render_research_gap(methods: tuple[MethodSignal, ...], question: str) -> str:
    gap_type = "IDENTIFICATION GAP" if methods else "RESEARCH GAP"
    if not question and not methods:
        return _status_line("Gap type could not be verified. Do not invent a gap.", EVIDENCE_NOT_VERIFIED)
    return f"- Gap type: `{gap_type}`\n- Status: `{EVIDENCE_INFERENCE}`\n- Reconstruction: verify what earlier work could not answer before treating this as final."


def _render_contribution_decomposition(contribution: str, methods: tuple[MethodSignal, ...]) -> str:
    rows = []
    if contribution:
        rows.append(f"- Question/empirical contribution: `{EVIDENCE_EXPLICIT}` {contribution}")
    if methods:
        rows.append("- Methodological/identification contribution: `AI_INFERENCE` method detected, but novelty requires comparison with predecessor literature.")
    if not rows:
        rows.append("- Contribution decomposition not verified from local evidence.")
    rows.append("- Do not exaggerate novelty until direct predecessor literature is checked.")
    return "\n".join(rows)


def _render_assumptions(assumptions: list[tuple[str, str]]) -> str:
    if not assumptions:
        return _status_line("No assumptions were explicitly detected. Add assumptions only after reading the design/theory section.", EVIDENCE_NOT_VERIFIED)
    return "\n\n".join(
        [
            "\n".join(
                [
                    f"### [[{name}]]",
                    f"- Importance: `IMPORTANT`",
                    f"- Evidence status: `{status}`",
                    "- Why needed: verify from the paper's design or argument.",
                    "- Where it enters: method/identification/theory section to be checked.",
                    "- Potential failure: not yet verified.",
                    "- Effect of violation: not yet verified.",
                ]
            )
            for name, status in assumptions
        ]
    )


def _render_equation_or_argument_guidance(content: str, methods: tuple[MethodSignal, ...]) -> str:
    has_equation = bool(re.search(r"\$[^$]+\$|\\begin\{(?:equation|align)", content))
    if has_equation:
        method_names = ", ".join(method.name for method in methods) or "the paper's method"
        return "\n".join(
            [
                "Before reading the main equations, reconstruct:",
                "1. Prerequisite concept.",
                "2. Notation and unit of analysis.",
                f"3. How the equation supports {method_names}.",
                "4. Which assumption gives the equation substantive meaning.",
                "",
                f"Evidence status: `{EVIDENCE_INFERENCE}` until equations are parsed and source-linked.",
            ]
        )
    return _status_line("No formal equation was detected locally. For qualitative/historical papers, map the argument structure instead: claim, evidence, counterargument, response.", EVIDENCE_INFERENCE)


def _render_unresolved(methods: tuple[MethodSignal, ...]) -> str:
    items = ["- Which claims are source-grounded rather than interpretive synthesis?"]
    if methods:
        items.append("- Which assumption carries the main substantive burden?")
        items.append("- Would an alternative method or evidence strategy change the interpretation?")
    items.append("- Which predecessor or critique must be ingested before this context becomes literature-verified?")
    return "\n".join(items)


def _render_read_before(concepts: tuple[BackgroundConcept, ...], methods: tuple[MethodSignal, ...]) -> str:
    essentials = [concept.name for concept in concepts if concept.priority == "ESSENTIAL"][:5]
    method_names = [method.name for method in methods[:3]]
    lines = ["### Level 0 - Basic Prerequisites"]
    lines.extend(f"- [[{name}]]" for name in essentials[:3])
    if not essentials:
        lines.append(f"- `{EVIDENCE_NOT_VERIFIED}` add after concept extraction.")
    lines.append("\n### Level 1 - Core Background")
    lines.extend(f"- [[{name}]]" for name in method_names)
    if not method_names:
        lines.append(f"- `{EVIDENCE_NOT_VERIFIED}` method background not extracted.")
    lines.append("\n### Level 2 - Direct Predecessors")
    lines.append(f"- `{EVIDENCE_NOT_VERIFIED}` {LINEAGE_NOT_VERIFIED}")
    lines.append("\n### Level 3 - Advanced Methodological Background")
    lines.append("- Add only after the method foundation is verified.")
    return "\n".join(lines)


def _render_research_opportunities(methods: tuple[MethodSignal, ...], assumptions: list[tuple[str, str]]) -> str:
    if not methods and not assumptions:
        return _status_line("Research opportunities require more verified structure from the paper.", EVIDENCE_NOT_VERIFIED)
    lines = []
    if assumptions:
        lines.append("- IDENTIFICATION OPPORTUNITY: test or stress the most fragile recovered assumption in a new setting.")
    if methods:
        lines.append("- METHOD EXTENSION: compare the detected method against plausible alternatives only after alternatives are source-verified.")
    lines.append("- REPLICATION: identify data, variables, software, and exact estimator before attempting replication.")
    return "\n".join(lines)


def _render_vault_connections(existing_nodes: list[str], content: str, rag_context: str) -> str:
    lower = f"{content}\n{rag_context}".lower()
    matches = []
    for node in existing_nodes[:30]:
        clean = " ".join(str(node).split()).strip()
        if clean and clean.lower() in lower:
            matches.append(clean)
    if not matches:
        return _status_line("No existing vault concept was confidently connected during this pass.", EVIDENCE_NOT_VERIFIED)
    return "\n".join(f"- [[{node}]] - `{EVIDENCE_LOCAL}`" for node in matches[:10])


def _render_open_questions(methods: tuple[MethodSignal, ...], assumptions: list[tuple[str, str]]) -> str:
    questions = [
        "What does the paper assume rather than demonstrate?",
        "Which claim would fail first if the central evidence were weaker?",
    ]
    if methods:
        questions.append("What exactly identifies the main parameter or supports the interpretation?")
        questions.append("Why was this method used instead of the closest alternative?")
    if assumptions:
        questions.append("Which assumption carries the most substantive weight?")
    questions.append("Which predecessor paper is indispensable but not yet ingested?")
    return "\n".join(f"- {question}" for question in questions)


def _render_study_guide(concepts: tuple[BackgroundConcept, ...], methods: tuple[MethodSignal, ...]) -> str:
    first_concept = concepts[0].name if concepts else "the core concept"
    first_method = methods[0].name if methods else "the paper's method or evidence strategy"
    return "\n".join(
        [
            f"1. Understand the empirical, theoretical, or interpretive problem behind [[{first_concept}]].",
            "2. Read the abstract/introduction only for the problem statement, not as proof of contribution.",
            f"3. Study [[{first_method}]] enough to separate method from identification or interpretation.",
            "4. Extract the paper's assumptions and mark each as explicit, inferred, or not verified.",
            "5. Read results/findings in relation to the reconstructed gap.",
            "6. Identify the one predecessor that must be verified next.",
            "7. Convert unresolved questions into follow-up notes or replication tasks.",
        ]
    )


def _render_missing_background(references: list[str]) -> str:
    items = []
    if not references:
        items.append("- Original predecessor literature has not been extracted or verified.")
    else:
        items.append("- Reference candidates require title/author/year/DOI verification before becoming lineage nodes.")
    items.extend(
        [
            "- Historical/institutional context may be incomplete.",
            "- Methodological assumptions require source-linked verification.",
            "- Later extensions and critiques require a local vault or scholarly-search expansion.",
        ]
    )
    return "\n".join(items)


def _status_line(text: str, status: str) -> str:
    return f"`{status}` - {text}"


def _clean_sentence(value: str) -> str:
    return " ".join(str(value or "").replace("[", "").replace("]", "").split()).strip(" -")


def _unique_concepts(concepts: list[BackgroundConcept]) -> list[BackgroundConcept]:
    seen: set[str] = set()
    result = []
    for concept in concepts:
        key = concept.name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(concept)
    return result
