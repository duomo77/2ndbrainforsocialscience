"""
evidence.py — Evidence Strength Scoring (EPIC 09)
=================================================
Aggregates the classified context papers into a single evidence-strength
assessment for the research area surrounding the seed paper.

Rubric (transparent and count-driven):

  STRONG      — at least one meta-analysis or systematic review and no
                contradictory findings in the retrieved context
  MODERATE    — review-level syntheses or a broad corroborating base with
                no contradictions
  CONTESTED   — multiple contradictory findings (or one without any
                synthesis-level support)
  EMERGING    — mostly newer follow-up work with no synthesis yet
  LIMITED     — thin context: few papers, no synthesis
  INSUFFICIENT— fewer than three context papers retrieved

The 0–1 score blends synthesis coverage, corroboration breadth, replication
support and recency, minus contradiction pressure.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from literature.context.models import (
    ContextCategory,
    ContextPaper,
    EvidenceAssessment,
    EvidenceLevel,
)


class EvidenceStrengthScorer:
    """Deterministic evidence-strength aggregation over context papers."""

    def assess(self, papers: Sequence[ContextPaper]) -> EvidenceAssessment:
        signals = _category_counts(papers)
        rationale: List[str] = []

        n_meta = signals[ContextCategory.META_ANALYSIS.value]
        n_systematic = signals[ContextCategory.SYSTEMATIC_REVIEW.value]
        n_reviews = signals[ContextCategory.REVIEW.value]
        n_replications = signals[ContextCategory.REPLICATION.value]
        n_contradictions = signals[ContextCategory.CONTRADICTORY.value]
        n_influential = signals[ContextCategory.INFLUENTIAL.value]
        n_follow_ups = signals[ContextCategory.FOLLOW_UP.value]
        n_related = signals[ContextCategory.RELATED.value]
        total = len(papers)

        if total < 3:
            return EvidenceAssessment(
                level=EvidenceLevel.INSUFFICIENT,
                score=round(0.1 * total, 4),
                rationale=[
                    f"only {total} context paper(s) retrieved — evidence base too thin to grade"
                ],
                signals=signals,
            )

        synthesis = n_meta + n_systematic
        score = 0.0
        score += 0.35 * min(synthesis, 2) / 2
        score += 0.15 * min(n_reviews, 3) / 3
        score += 0.15 * min(n_replications, 2) / 2
        score += 0.15 * min(max(n_related - synthesis - n_reviews, 0), 8) / 8
        score += 0.10 * min(n_influential, 3) / 3
        score += 0.10 * min(n_follow_ups, 4) / 4
        score -= 0.25 * min(n_contradictions, 2) / 2
        score = max(0.0, min(1.0, score))

        level = self._level(
            synthesis=synthesis,
            n_reviews=n_reviews,
            n_contradictions=n_contradictions,
            n_related=n_related,
            n_follow_ups=n_follow_ups,
            total=total,
        )

        rationale.append(
            f"{total} context papers across {sum(1 for v in signals.values() if v)} categories"
        )
        if synthesis:
            rationale.append(
                f"{synthesis} synthesis-level study(ies): meta-analysis/systematic review"
            )
        if n_reviews:
            rationale.append(f"{n_reviews} review paper(s)")
        if n_replications:
            rationale.append(f"{n_replications} replication-related paper(s)")
        if n_contradictions:
            rationale.append(f"{n_contradictions} contradictory finding(s) detected")
        if n_follow_ups:
            rationale.append(f"{n_follow_ups} newer follow-up paper(s)")

        return EvidenceAssessment(
            level=level,
            score=round(score, 4),
            rationale=rationale,
            signals=signals,
        )

    # ── internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _level(
        *,
        synthesis: int,
        n_reviews: int,
        n_contradictions: int,
        n_related: int,
        n_follow_ups: int,
        total: int,
    ) -> EvidenceLevel:
        if n_contradictions >= 2 or (n_contradictions >= 1 and synthesis == 0 and n_reviews == 0):
            return EvidenceLevel.CONTESTED
        if synthesis >= 1 and n_contradictions == 0:
            return EvidenceLevel.STRONG
        if synthesis == 0 and n_reviews == 0 and n_follow_ups > 0 and n_follow_ups >= total // 2:
            return EvidenceLevel.EMERGING
        if n_reviews >= 1 or (n_related >= 5 and n_contradictions == 0):
            return EvidenceLevel.MODERATE
        return EvidenceLevel.LIMITED


def _category_counts(papers: Sequence[ContextPaper]) -> Dict[str, int]:
    counts = {category.value: 0 for category in ContextCategory}
    for paper in papers:
        for category in set(paper.categories):
            counts[category.value] += 1
    return counts
