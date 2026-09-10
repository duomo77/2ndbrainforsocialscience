from __future__ import annotations

from core.research_intelligence import (
    HUMAN_REVIEW_REQUIRED,
    build_research_intelligence,
    decompose_paper,
    detect_cross_paper_contradictions,
    merge_methodology_atlas_markdown,
    mine_research_gaps,
)


def test_decompose_paper_extracts_structured_research_objects():
    structured = decompose_paper(
        title="Training Paper",
        content=(
            "Research question: Does training affect wages? "
            "We use difference-in-differences estimates with parallel trends. "
            "Our dataset contains workers from 2010 to 2020. "
            "We find that training increases wages. "
            "A limitation is that the sample covers a single country."
        ),
    )

    assert structured.research_questions == ("Does training affect wages?",)
    assert structured.methods[0].name == "Difference-in-Differences"
    assert structured.methods[0].identification_strategy
    assert structured.assumptions[0].name == "Parallel Trends"
    assert structured.evidence
    assert structured.claims
    assert structured.claims[0].evidence_ids
    assert structured.gaps[0].gap_type == "DATA GAP"
    assert structured.hypotheses[0].derived_from_gap_id == structured.gaps[0].gap_id
    assert "Estimator implementation for Difference-in-Differences" in structured.replication_requirements


def test_cross_paper_contradiction_candidates_require_human_review():
    left = decompose_paper(
        title="Policy Positive",
        content="We find that the policy increases employment. The data cover treated counties.",
    )
    right = decompose_paper(
        title="Policy Null",
        content="We find that the policy has no effect on employment. The dataset covers other counties.",
    )

    contradictions = detect_cross_paper_contradictions([left, right])

    assert len(contradictions) == 1
    assert contradictions[0].contradiction_type == "EMPIRICAL_RESULT_CONTRADICTION"
    assert contradictions[0].resolution_status == HUMAN_REVIEW_REQUIRED
    assert contradictions[0].source_a == "Policy Positive"
    assert contradictions[0].source_b == "Policy Null"


def test_gap_miner_clusters_repeated_gap_types_across_papers():
    papers = [
        decompose_paper(
            title="Paper A",
            content="We find positive effects. A limitation is that the sample covers one city.",
        ),
        decompose_paper(
            title="Paper B",
            content="We show similar effects. A limitation is that limited data constrain subgroup tests.",
        ),
    ]

    gaps = mine_research_gaps(papers)

    assert len(gaps) == 1
    assert gaps[0].gap_type == "DATA GAP"
    assert gaps[0].supporting_papers == ("Paper A", "Paper B")
    assert gaps[0].confidence == "MEDIUM"


def test_research_intelligence_bundle_renders_atlas_and_integrity_gate():
    bundle = build_research_intelligence(
        title="IV Paper",
        content=(
            "Research question: Does treatment affect outcomes? "
            "We use instrumental variables and the exclusion restriction. "
            "The dataset includes regional exposure. We find treatment increases outcomes."
        ),
    )

    assert "type: research_intelligence" in bundle.markdown
    assert "## Claim Evidence Assumption Graph" in bundle.markdown
    assert "## Integrity Gate" in bundle.markdown
    atlas = bundle.methodology_atlas["Instrumental Variables"]
    assert "type: methodology_atlas" in atlas
    assert "Research design:" in atlas
    assert "Identification logic:" in atlas
    assert "Estimator:" in atlas
    assert "[[IV Paper]]" in atlas


def test_methodology_atlas_merge_appends_only_new_source_application():
    existing = "---\ntitle: Method - OLS\n---\n\n# Method - OLS\n\n## Source Applications\n\n### [[Old Paper]]"
    generated = "# Method - OLS\n\n## Source Applications\n### [[New Paper]]\n- Confidence: `AI_INFERENCE`"

    merged = merge_methodology_atlas_markdown(existing, generated, "New Paper")
    merged_again = merge_methodology_atlas_markdown(merged, generated, "New Paper")

    assert "[[Old Paper]]" in merged
    assert "[[New Paper]]" in merged
    assert merged.count("## Source Applications") == 1
    assert merged_again == merged
