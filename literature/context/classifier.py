"""
classifier.py — Scientific Context Classifier (EPIC 09)
=======================================================
Deterministic, explainable categorization of retrieved papers into their
scientific-context roles. No LLM calls: classification relies on provider
publication types (OpenAlex ``type``, Semantic Scholar ``publicationTypes``,
PubMed ``pubtype``) and transparent keyword rules, so every assignment can
be audited from the recorded rationale.

Category rules (evaluated per candidate):

  SYSTEMATIC_REVIEW — publication type or text marks a systematic review
  META_ANALYSIS     — publication type or text marks a meta-analysis
  REVIEW            — review publication type / survey keywords
  REPLICATION       — replication / reproducibility language
  CONTRADICTORY     — contradiction / failure-to-replicate language
  INFLUENTIAL       — high citation counts or referenced-by-seed channel
  FOLLOW_UP         — cites the seed, or newer work on the same topic
  RELATED           — baseline category for every retained candidate
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from literature.context.models import CATEGORY_PRIORITY, ContextCategory
from literature.search.models import RetrievedPaper, RetrievalChannel, SeedPaper

# ── publication-type vocabularies (per provider) ─────────────────────────────

_REVIEW_TYPES = {
    "review",
    "journal-review",
    "book-review",  # OpenAlex / Crossref
    "review-article",
    "reference-entry",
}
_SYSTEMATIC_REVIEW_PHRASES = ("systematic review", "systematic literature review")
_META_ANALYSIS_PHRASES = ("meta-analysis", "meta analysis", "meta-analytic", "metaanalysis")
_REVIEW_PHRASES = (
    "literature review",
    "review of",
    "a review",
    "survey of",
    "narrative review",
    "scoping review",
    "overview of",
)
_REPLICATION_PATTERNS = (
    re.compile(r"\breplicat(?:e|ed|es|ing|ion|ions)\b", re.IGNORECASE),
    re.compile(r"\breproduc(?:e|ed|ibility|ible)\b", re.IGNORECASE),
    re.compile(r"\bregistered\s+report\b", re.IGNORECASE),
    re.compile(r"\bre-examination\b|\breexamination\b", re.IGNORECASE),
)
_CONTRADICTION_PHRASES = (
    "contradict",
    "contradicts",
    "contradictory",
    "fail to replicate",
    "failed to replicate",
    "fails to replicate",
    "failure to replicate",
    "does not support",
    "do not support",
    "no evidence of",
    "no evidence that",
    "no evidence for",
    "null effect",
    "no effect of",
    "opposite effect",
    "reconsider",
    "reconsidering",
    "refute",
    "refutes",
    "cast doubt",
    "casts doubt",
    "overturn",
    "overturns",
    "challenges the",
    "challenge the",
    "challenging the",
)

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "those",
    "into",
    "over",
    "under",
    "upon",
    "about",
    "between",
    "toward",
    "towards",
    "their",
    "there",
    "where",
    "when",
    "which",
    "what",
    "have",
    "has",
    "was",
    "were",
    "been",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "case",
    "study",
    "based",
    "using",
    "evidence",
    "effect",
    "effects",
    "analysis",
    "approach",
    "method",
    "methods",
}

INFLUENTIAL_CITATIONS_STRONG = 500
INFLUENTIAL_CITATIONS_MODERATE = 100


@dataclass(frozen=True)
class ClassificationResult:
    categories: Tuple[ContextCategory, ...]
    primary_category: ContextCategory
    relevance: float
    rationale: str
    matched_signals: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassifierConfig:
    min_title_overlap: float = 0.15  # topic-similarity floor for RELATED retention
    follow_up_overlap: float = 0.3  # topic similarity needed for year-based FOLLOW_UP
    influential_citations_strong: int = INFLUENTIAL_CITATIONS_STRONG
    influential_citations_moderate: int = INFLUENTIAL_CITATIONS_MODERATE


class ContextClassifier:
    """Assigns context categories, primary category, relevance and rationale."""

    def __init__(self, config: Optional[ClassifierConfig] = None) -> None:
        self.config = config or ClassifierConfig()

    def classify(
        self,
        paper: RetrievedPaper,
        seed: SeedPaper,
        channels: Iterable[str] = (),
    ) -> ClassificationResult:
        channel_set: Set[str] = {str(channel) for channel in channels} | {paper.channel.value}
        text = f"{paper.title} {paper.abstract}".lower()
        type_tokens = {str(pub_type).lower() for pub_type in paper.publication_types}

        categories: List[ContextCategory] = []
        signals: List[str] = []

        # ── review family (publication types first: most reliable) ─────────
        if _has_systematic_review(type_tokens, text):
            categories.append(ContextCategory.SYSTEMATIC_REVIEW)
            signals.append("systematic-review type/phrase")
        if _has_meta_analysis(type_tokens, text):
            categories.append(ContextCategory.META_ANALYSIS)
            signals.append("meta-analysis type/phrase")
        if _has_review(type_tokens, text):
            categories.append(ContextCategory.REVIEW)
            signals.append("review type/phrase")

        # ── replication ─────────────────────────────────────────────────────
        matched_replication = _match_patterns(_REPLICATION_PATTERNS, text)
        if matched_replication:
            categories.append(ContextCategory.REPLICATION)
            signals.extend(f"replication:{match}" for match in matched_replication[:3])

        # ── contradiction ───────────────────────────────────────────────────
        matched_contradiction = _match_phrases(_CONTRADICTION_PHRASES, text)
        if matched_contradiction:
            categories.append(ContextCategory.CONTRADICTORY)
            signals.extend(f"contradiction:{match}" for match in matched_contradiction[:3])

        # ── influential ─────────────────────────────────────────────────────
        citations = paper.citation_count or 0
        if citations >= self.config.influential_citations_strong:
            categories.append(ContextCategory.INFLUENTIAL)
            signals.append(f"citations:{citations}")
        elif citations >= self.config.influential_citations_moderate:
            categories.append(ContextCategory.INFLUENTIAL)
            signals.append(f"citations:{citations}")
        elif RetrievalChannel.REFERENCES.value in channel_set:
            categories.append(ContextCategory.INFLUENTIAL)
            signals.append("referenced-by-seed")

        # ── newer follow-up work ───────────────────────────────────────────
        cites_seed = bool(channel_set & {RetrievalChannel.CITATIONS.value})
        newer = seed.year is not None and paper.year is not None and paper.year > seed.year
        overlap = title_overlap(seed.title, paper.title)
        if cites_seed and newer:
            categories.append(ContextCategory.FOLLOW_UP)
            signals.append("cites-seed")
        elif cites_seed:
            categories.append(ContextCategory.FOLLOW_UP)
            signals.append("cites-seed")
        elif newer and overlap >= self.config.follow_up_overlap:
            categories.append(ContextCategory.FOLLOW_UP)
            signals.append(f"newer-topic-overlap:{overlap:.2f}")

        # ── related baseline ────────────────────────────────────────────────
        categories.append(ContextCategory.RELATED)

        deduped = _dedupe_categories(categories)
        primary = _primary_category(deduped)
        relevance = self._relevance(paper, seed, channel_set, overlap)
        rationale = _build_rationale(deduped, signals, paper)

        return ClassificationResult(
            categories=tuple(deduped),
            primary_category=primary,
            relevance=relevance,
            rationale=rationale,
            matched_signals=tuple(signals),
        )

    # ── internals ──────────────────────────────────────────────────────────

    def _relevance(
        self, paper: RetrievedPaper, seed: SeedPaper, channel_set: Set[str], overlap: float
    ) -> float:
        score = 0.30
        extra_channels = max(0, len(channel_set) - 1)
        score += min(0.20, 0.10 * extra_channels)
        score += min(0.25, overlap * 0.5)

        citations = paper.citation_count or 0
        if citations >= INFLUENTIAL_CITATIONS_STRONG:
            score += 0.15
        elif citations >= INFLUENTIAL_CITATIONS_MODERATE:
            score += 0.10
        elif citations >= 25:
            score += 0.05

        if paper.year and seed.year and abs(paper.year - seed.year) <= 5:
            score += 0.10

        return round(min(1.0, score), 4)


# ── module helpers ────────────────────────────────────────────────────────────


def _has_systematic_review(type_tokens: Set[str], text: str) -> bool:
    if any(token in {"systematicreview", "systematic review"} for token in type_tokens):
        return True
    return any(phrase in text for phrase in _SYSTEMATIC_REVIEW_PHRASES)


def _has_meta_analysis(type_tokens: Set[str], text: str) -> bool:
    if any(token in {"metaanalysis", "meta-analysis"} for token in type_tokens):
        return True
    return any(phrase in text for phrase in _META_ANALYSIS_PHRASES)


def _has_review(type_tokens: Set[str], text: str) -> bool:
    if type_tokens & _REVIEW_TYPES:
        return True
    if any(token == "review" for token in type_tokens):
        return True
    return any(phrase in text for phrase in _REVIEW_PHRASES)


def _match_patterns(patterns: Sequence[re.Pattern], text: str) -> List[str]:
    matches = []
    for pattern in patterns:
        found = pattern.search(text)
        if found:
            matches.append(found.group(0).lower())
    return matches


def _match_phrases(phrases: Sequence[str], text: str) -> List[str]:
    return [phrase for phrase in phrases if phrase in text]


def _dedupe_categories(categories: List[ContextCategory]) -> List[ContextCategory]:
    ordered: List[ContextCategory] = []
    for category in CATEGORY_PRIORITY:
        if category in categories and category not in ordered:
            ordered.append(category)
    return ordered


def _primary_category(categories: List[ContextCategory]) -> ContextCategory:
    return categories[0] if categories else ContextCategory.RELATED


def _build_rationale(
    categories: List[ContextCategory], signals: List[str], paper: RetrievedPaper
) -> str:
    parts = [f"categories={','.join(category.value for category in categories)}"]
    if signals:
        parts.append(f"signals={'; '.join(signals[:6])}")
    if paper.citation_count is not None:
        parts.append(f"citations={paper.citation_count}")
    if paper.year is not None:
        parts.append(f"year={paper.year}")
    parts.append(f"source={paper.source.value}")
    return " | ".join(parts)


def tokenize_title(title: str) -> Set[str]:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {word for word in words if len(word) > 2 and word not in _STOPWORDS}


def title_overlap(title_a: str, title_b: str) -> float:
    tokens_a = tokenize_title(title_a)
    tokens_b = tokenize_title(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0
