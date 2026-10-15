from __future__ import annotations

from core.figure_intelligence import (
    DATA_RECOVERED,
    DATA_UNAVAILABLE,
    DIGITIZED_FROM_FIGURE,
    SOURCE_FACT,
    TEXT_DERIVED,
    VisualizationSpec,
    build_figure_intelligence,
    extract_research_figures,
    validate_visualization_spec,
)


def test_extract_research_figure_classifies_event_study_without_inventing_data():
    figures = extract_research_figures(
        title="Policy Paper",
        content=(
            "Figure 1. Event-study estimates around the reform. "
            "The x-axis shows event time and the y-axis shows effect estimates with confidence intervals."
        ),
    )

    assert len(figures) == 1
    figure = figures[0]
    assert figure.figure_number == "1"
    assert figure.figure_type == "EVENT_STUDY"
    assert figure.figure_category == "STATISTICAL_FIGURE"
    assert figure.provenance.data_origin == DATA_UNAVAILABLE
    assert figure.visualization_spec is not None
    assert figure.visualization_spec.data == ()
    assert figure.visualization_spec.x.label == "event time"
    assert figure.visualization_spec.uncertainty == ("confidence_interval",)
    assert figure.visualization_spec.reference_lines
    assert figure.reconstruction_status == "STRUCTURE_EXTRACTED"


def test_extract_research_figure_recovers_explicit_caption_pairs_only():
    figures = extract_research_figures(
        title="Descriptive Paper",
        content="Figure 2. Bar chart of employment rates: 2010=0.44, 2011=0.48, 2012=0.51.",
    )

    spec = figures[0].visualization_spec

    assert spec is not None
    assert figures[0].figure_type == "BAR_CHART"
    assert figures[0].provenance.data_origin == TEXT_DERIVED
    assert figures[0].reconstruction_status == DATA_RECOVERED
    assert spec.data_source.origin == TEXT_DERIVED
    assert spec.data_source.evidence_status == SOURCE_FACT
    assert [point["y"] for point in spec.data] == [0.44, 0.48, 0.51]


def test_visualization_spec_validation_blocks_false_precision():
    bundle = build_figure_intelligence(
        title="Digitized Paper",
        content="Figure 3. Scatterplot of income and education.",
    )
    spec = bundle.figures[0].visualization_spec
    assert spec is not None
    unsafe = VisualizationSpec(
        chart_type=spec.chart_type,
        data_source=spec.data_source.__class__(origin=DIGITIZED_FROM_FIGURE),
        x=spec.x,
        y=spec.y,
        source_figure_id=spec.source_figure_id,
        data=({"x": 1, "y": 2},),
        reconstruction_status=DATA_RECOVERED,
    )

    ok, errors = validate_visualization_spec(unsafe)

    assert ok is False
    assert errors


def test_figure_intelligence_markdown_exposes_canonical_spec_and_rules():
    bundle = build_figure_intelligence(
        title="RDD Paper",
        content="Figure 4. Regression discontinuity plot at the cutoff.",
    )

    assert bundle.figures
    assert "type: figure_intelligence" in bundle.markdown
    assert "## Visualization Specifications" in bundle.markdown
    assert "D3 JavaScript is renderer code only" in bundle.markdown
    assert bundle.visualization_specs[0]["chart_type"] == "RDD_PLOT"
