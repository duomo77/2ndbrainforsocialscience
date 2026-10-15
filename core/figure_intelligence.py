"""
figure_intelligence.py -- academic figure intelligence and D3 spec compiler.

The canonical object is a source-grounded visualization specification, not
arbitrary JavaScript. D3 renderers consume the spec, while provenance and
reconstruction status stay visible to the researcher.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable

from core.intel.figure_detector import detect_figures
from core.utils.markdown_utils import inject_frontmatter


DATA_VISUALIZATION = "DATA_VISUALIZATION"
STATISTICAL_FIGURE = "STATISTICAL_FIGURE"
MODEL_DIAGRAM = "MODEL_DIAGRAM"
CONCEPTUAL_DIAGRAM = "CONCEPTUAL_DIAGRAM"
DECORATIVE = "DECORATIVE"
UNKNOWN = "UNKNOWN"

SOURCE_ONLY = "SOURCE_ONLY"
STRUCTURE_EXTRACTED = "STRUCTURE_EXTRACTED"
DATA_PARTIALLY_RECOVERED = "DATA_PARTIALLY_RECOVERED"
DATA_RECOVERED = "DATA_RECOVERED"
RECONSTRUCTED = "RECONSTRUCTED"
VALIDATED = "VALIDATED"
HUMAN_VERIFIED = "HUMAN_VERIFIED"
FAILED = "FAILED"

AUTHOR_DATA = "AUTHOR_DATA"
SUPPLEMENTARY_DATA = "SUPPLEMENTARY_DATA"
REPLICATION_PACKAGE = "REPLICATION_PACKAGE"
TABLE_DERIVED = "TABLE_DERIVED"
TEXT_DERIVED = "TEXT_DERIVED"
DIGITIZED_FROM_FIGURE = "DIGITIZED_FROM_FIGURE"
AI_ESTIMATED = "AI_ESTIMATED"
MANUALLY_ENTERED = "MANUALLY_ENTERED"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
UNKNOWN_DATA = "UNKNOWN"

AI_INFERENCE = "AI_INFERENCE"
SOURCE_FACT = "SOURCE_FACT"
HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass(frozen=True)
class BoundingBox:
    top: int = -1
    left: int = -1
    bottom: int = -1
    right: int = -1


@dataclass(frozen=True)
class FigurePanel:
    panel_id: str
    label: str = ""
    caption_fragment: str = ""
    figure_type: str = UNKNOWN


@dataclass(frozen=True)
class EncodingSpec:
    field: str
    label: str = ""
    type: str = "quantitative"
    scale: str = "linear"
    evidence_status: str = AI_INFERENCE


@dataclass(frozen=True)
class DataSourceSpec:
    origin: str = DATA_UNAVAILABLE
    description: str = "No machine-readable figure data recovered."
    recovery_priority: tuple[str, ...] = (
        AUTHOR_DATA,
        SUPPLEMENTARY_DATA,
        REPLICATION_PACKAGE,
        TABLE_DERIVED,
        TEXT_DERIVED,
        DIGITIZED_FROM_FIGURE,
        AI_ESTIMATED,
    )
    evidence_status: str = HUMAN_REVIEW_REQUIRED


@dataclass(frozen=True)
class ReferenceLineSpec:
    axis: str
    value: float
    label: str = ""


@dataclass(frozen=True)
class AnnotationSpec:
    text: str
    target: str = ""
    evidence_status: str = AI_INFERENCE


@dataclass(frozen=True)
class VisualizationSpec:
    chart_type: str
    data_source: DataSourceSpec
    x: EncodingSpec
    y: EncodingSpec
    source_figure_id: str
    color: EncodingSpec | None = None
    uncertainty: tuple[str, ...] = ()
    annotations: tuple[AnnotationSpec, ...] = ()
    reference_lines: tuple[ReferenceLineSpec, ...] = ()
    interactions: tuple[str, ...] = ("tooltip", "keyboard-focus")
    layout: dict[str, int] = field(default_factory=lambda: {"width": 720, "height": 420})
    data: tuple[dict[str, Any], ...] = ()
    reconstruction_status: str = SOURCE_ONLY


@dataclass(frozen=True)
class FigureProvenance:
    source_stage: str = "EXTRACTED_STRUCTURE"
    extraction_method: str = "text_figure_reference_detector"
    ocr_engine: str = "NOT_RUN"
    data_origin: str = DATA_UNAVAILABLE
    source_hash: str = ""
    confidence: str = "LOW"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class ResearchFigure:
    id: str
    paper_id: str
    figure_number: str = ""
    caption: str = ""
    figure_category: str = UNKNOWN
    figure_type: str = UNKNOWN
    source_page: int = -1
    source_bounding_box: BoundingBox | None = None
    panels: tuple[FigurePanel, ...] = ()
    visualization_spec: VisualizationSpec | None = None
    reconstruction_status: str = SOURCE_ONLY
    provenance: FigureProvenance = field(default_factory=FigureProvenance)
    verification_status: str = HUMAN_REVIEW_REQUIRED


@dataclass(frozen=True)
class FigureIntelligenceBundle:
    title: str
    figure_note_title: str
    markdown: str
    figures: tuple[ResearchFigure, ...] = ()
    visualization_specs: tuple[dict[str, Any], ...] = ()


_FIGURE_RE = re.compile(
    r"\b(?:Figure|Fig\.?)\s*([0-9]+[A-Za-z]?|[IVXLC]+)\s*[:.\-]?\s*([^\n]{0,500})",
    re.IGNORECASE,
)

_TYPE_PATTERNS: tuple[tuple[str, str, str, str], ...] = (
    ("EVENT_STUDY", STATISTICAL_FIGURE, "event time", r"\b(?:event[- ]study|leads?|lags?|pre[- ]trend|event time)\b"),
    ("RDD_PLOT", STATISTICAL_FIGURE, "running variable", r"\b(?:regression discontinuity|RDD|cutoff|threshold)\b"),
    ("DID_PLOT", STATISTICAL_FIGURE, "time", r"\b(?:difference[- ]in[- ]differences|parallel trends?|treated and control)\b"),
    ("COEFFICIENT_PLOT", STATISTICAL_FIGURE, "coefficient", r"\b(?:coefficient|estimate|confidence interval|standard error)\b"),
    ("FOREST_PLOT", STATISTICAL_FIGURE, "study", r"\bforest plot\b"),
    ("REGRESSION_SCATTER", STATISTICAL_FIGURE, "x", r"\b(?:binned scatter|binscatter|regression scatter|fitted line)\b"),
    ("SCATTERPLOT", DATA_VISUALIZATION, "x", r"\bscatter(?:plot)?\b"),
    ("MULTI_SERIES_LINE", DATA_VISUALIZATION, "x", r"\b(?:multiple series|treated|control|groups?|series)\b.*\b(?:line|trend|over time)\b"),
    ("TIME_SERIES", DATA_VISUALIZATION, "time", r"\b(?:time series|over time|trend|year|month)\b"),
    ("LINE_CHART", DATA_VISUALIZATION, "x", r"\bline chart\b|\bline graph\b"),
    ("GROUPED_BAR", DATA_VISUALIZATION, "group", r"\bgrouped bar\b"),
    ("STACKED_BAR", DATA_VISUALIZATION, "group", r"\bstacked bar\b"),
    ("BAR_CHART", DATA_VISUALIZATION, "category", r"\bbar (?:chart|plot|graph)\b"),
    ("HISTOGRAM", STATISTICAL_FIGURE, "bin", r"\bhistogram\b"),
    ("DENSITY_PLOT", STATISTICAL_FIGURE, "value", r"\bdensity\b"),
    ("ECDF", STATISTICAL_FIGURE, "value", r"\bECDF\b|empirical cumulative"),
    ("BOX_PLOT", STATISTICAL_FIGURE, "group", r"\bbox(?:plot)?\b"),
    ("VIOLIN_PLOT", STATISTICAL_FIGURE, "group", r"\bviolin\b"),
    ("HEATMAP", DATA_VISUALIZATION, "x", r"\bheat ?map\b"),
    ("CORRELATION_MATRIX", STATISTICAL_FIGURE, "variable", r"\bcorrelation matrix\b"),
    ("IMPULSE_RESPONSE", STATISTICAL_FIGURE, "horizon", r"\bimpulse response\b"),
    ("PARTIAL_EFFECT", STATISTICAL_FIGURE, "x", r"\bpartial effect\b"),
    ("MARGINAL_EFFECT", STATISTICAL_FIGURE, "x", r"\bmarginal effect\b"),
    ("ROC_CURVE", STATISTICAL_FIGURE, "false positive rate", r"\bROC\b|receiver operating"),
    ("CALIBRATION_PLOT", STATISTICAL_FIGURE, "predicted probability", r"\bcalibration\b"),
    ("NETWORK_GRAPH", DATA_VISUALIZATION, "node", r"\bnetwork\b"),
    ("SANKEY", DATA_VISUALIZATION, "flow", r"\bsankey\b"),
    ("CHOROPLETH", DATA_VISUALIZATION, "region", r"\bchoropleth\b"),
    ("POINT_MAP", DATA_VISUALIZATION, "longitude", r"\bmap\b"),
    ("CAUSAL_DAG", MODEL_DIAGRAM, "node", r"\b(?:DAG|directed acyclic graph|causal graph)\b"),
    ("MODEL_DIAGRAM", MODEL_DIAGRAM, "component", r"\b(?:model diagram|architecture|framework|flowchart)\b"),
)


def figure_note_title(title: str) -> str:
    clean = " ".join(str(title or "Untitled").split()).strip()
    return f"{clean} - Figure Intelligence"


def add_figure_intelligence_link(card_markdown: str, title: str) -> str:
    link = f"[[{figure_note_title(title)}]]"
    if link in card_markdown:
        return card_markdown
    block = f"## Figure Intelligence\n{link}\n"
    match = re.match(r"^---\s*\n.*?\n---\s*\n?", card_markdown, re.DOTALL)
    if match:
        return card_markdown[: match.end()] + "\n" + block + "\n" + card_markdown[match.end():].lstrip()
    return block + "\n" + card_markdown.lstrip()


def build_figure_intelligence(*, title: str, content: str, paper_id: str = "") -> FigureIntelligenceBundle:
    figures = extract_research_figures(title=title, content=content, paper_id=paper_id)
    specs = tuple(
        visualization_spec_to_dict(figure.visualization_spec)
        for figure in figures
        if figure.visualization_spec is not None
    )
    markdown = render_figure_intelligence(title=title, figures=figures)
    return FigureIntelligenceBundle(
        title=title,
        figure_note_title=figure_note_title(title),
        markdown=markdown,
        figures=figures,
        visualization_specs=specs,
    )


def extract_research_figures(*, title: str, content: str, paper_id: str = "") -> tuple[ResearchFigure, ...]:
    paper_identity = paper_id or _stable_id("paper", title)
    candidates = _extract_caption_candidates(content)
    if not candidates:
        candidates = _fallback_detected_figures(content)

    figures = []
    for index, candidate in enumerate(candidates, start=1):
        caption = candidate["caption"]
        figure_number = candidate.get("figure_number") or str(index)
        figure_type, category, default_x = classify_figure_type(caption)
        panels = tuple(_detect_panels(caption, figure_number, figure_type))
        recovered_data, data_origin = _recover_textual_data(caption)
        status = DATA_RECOVERED if recovered_data else STRUCTURE_EXTRACTED
        if category in {DECORATIVE, UNKNOWN} and not caption:
            status = SOURCE_ONLY
        figure_id = _stable_id("figure", paper_identity, figure_number, caption)
        bbox = _bbox_from_candidate(candidate)
        provenance = FigureProvenance(
            source_hash=_stable_id("source", caption),
            data_origin=data_origin,
            confidence="MEDIUM" if caption else "LOW",
        )
        spec = _build_visualization_spec(
            figure_id=figure_id,
            figure_type=figure_type,
            caption=caption,
            default_x=default_x,
            data=recovered_data,
            data_origin=data_origin,
            reconstruction_status=status,
        )
        figures.append(
            ResearchFigure(
                id=figure_id,
                paper_id=paper_identity,
                figure_number=figure_number,
                caption=caption,
                figure_category=category,
                figure_type=figure_type,
                source_page=int(candidate.get("page_number", -1) or -1),
                source_bounding_box=bbox,
                panels=panels,
                visualization_spec=spec,
                reconstruction_status=status,
                provenance=provenance,
            )
        )
    return tuple(figures)


def classify_figure_type(text: str) -> tuple[str, str, str]:
    for figure_type, category, default_x, pattern in _TYPE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return figure_type, category, default_x
    if re.search(r"\b(?:photo|illustration|image)\b", text, re.IGNORECASE):
        return "ILLUSTRATION", DECORATIVE, "x"
    if re.search(r"\b(?:diagram|conceptual|framework)\b", text, re.IGNORECASE):
        return "CONCEPTUAL_DIAGRAM", CONCEPTUAL_DIAGRAM, "component"
    return UNKNOWN, UNKNOWN, "x"


def visualization_spec_to_dict(spec: VisualizationSpec | None) -> dict[str, Any]:
    if spec is None:
        return {}
    return _drop_none(asdict(spec))


def validate_visualization_spec(spec: VisualizationSpec) -> tuple[bool, list[str]]:
    errors = []
    if not spec.source_figure_id:
        errors.append("source_figure_id is required")
    if not spec.chart_type:
        errors.append("chart_type is required")
    if spec.data_source.origin in {DIGITIZED_FROM_FIGURE, AI_ESTIMATED} and spec.reconstruction_status == DATA_RECOVERED:
        errors.append("digitized or AI-estimated data cannot be marked DATA_RECOVERED")
    if spec.reconstruction_status in {RECONSTRUCTED, VALIDATED, HUMAN_VERIFIED} and not spec.data:
        errors.append("reconstructed specs require recovered data")
    return not errors, errors


def render_figure_intelligence(*, title: str, figures: Iterable[ResearchFigure]) -> str:
    figures = tuple(figures)
    body = "\n\n".join(
        [
            f"# Figure Intelligence - {title}",
            f"Source paper: [[{title}]]",
            "## Figure Registry",
            _render_registry(figures),
            "## Reconstruction Queue",
            _render_queue(figures),
            "## Visualization Specifications",
            _render_specs(figures),
            "## Provenance and Verification",
            _render_provenance(figures),
            "## Integrity Rules",
            _render_integrity_rules(),
        ]
    )
    frontmatter = {
        "title": figure_note_title(title),
        "type": "figure_intelligence",
        "source_paper": title,
        "figure_count": len(figures),
        "generated_at": datetime.now(UTC).isoformat(),
        "pipeline_version": "figure-intelligence-v1",
        "human_verified": False,
    }
    return inject_frontmatter(body, frontmatter)


def _extract_caption_candidates(content: str) -> list[dict[str, Any]]:
    candidates = []
    for match in _FIGURE_RE.finditer(content):
        figure_number = match.group(1)
        caption_seed = match.group(2).strip(" :-")
        block = content[match.end() : match.end() + 500]
        tail = re.split(r"\n\s*\n|(?:Table|Figure|Fig\.?)\s+[0-9IVXLC]+", block, maxsplit=1)[0]
        caption = _clean_caption(" ".join(part for part in (caption_seed, tail) if part))
        if not caption:
            caption = f"Figure {figure_number}"
        candidates.append({"figure_number": figure_number, "caption": caption})
        if len(candidates) >= 20:
            break
    return _dedupe_candidates(candidates)


def _fallback_detected_figures(content: str) -> list[dict[str, Any]]:
    candidates = []
    for index, figure in enumerate(detect_figures(content), start=1):
        caption = _clean_caption(figure.caption or figure.alt_text or "")
        if figure.kind in {"equation", "image"} and not caption:
            continue
        candidates.append(
            {
                "figure_number": str(index),
                "caption": caption,
                "page_number": figure.page_number,
                "bbox": figure.bounding_box,
            }
        )
    return _dedupe_candidates(candidates)


def _build_visualization_spec(
    *,
    figure_id: str,
    figure_type: str,
    caption: str,
    default_x: str,
    data: tuple[dict[str, Any], ...],
    data_origin: str,
    reconstruction_status: str,
) -> VisualizationSpec:
    y_label = _infer_y_label(caption)
    x_label = _infer_x_label(caption, default_x)
    reference_lines = []
    if figure_type in {"EVENT_STUDY", "RDD_PLOT"}:
        reference_lines.append(ReferenceLineSpec(axis="x", value=0.0, label="Reference point"))
    if figure_type in {"COEFFICIENT_PLOT", "EVENT_STUDY", "DID_PLOT", "RDD_PLOT"}:
        reference_lines.append(ReferenceLineSpec(axis="y", value=0.0, label="No effect"))
    return VisualizationSpec(
        chart_type=figure_type,
        data_source=DataSourceSpec(
            origin=data_origin,
            description=(
                "Values recovered from explicit caption/text pairs."
                if data
                else "No numeric values recovered; renderer shows a reconstruction scaffold only."
            ),
            evidence_status=SOURCE_FACT if data_origin == TEXT_DERIVED else HUMAN_REVIEW_REQUIRED,
        ),
        x=EncodingSpec(field="x", label=x_label, type=_infer_x_type(x_label), evidence_status=AI_INFERENCE),
        y=EncodingSpec(field="y", label=y_label, type="quantitative", evidence_status=AI_INFERENCE),
        color=EncodingSpec(field="series", label="Series", type="nominal") if _mentions_multiple_series(caption) else None,
        source_figure_id=figure_id,
        uncertainty=("confidence_interval",) if re.search(r"\b(?:confidence intervals?|CI|standard errors?)\b", caption, re.IGNORECASE) else (),
        annotations=tuple(_extract_annotations(caption)),
        reference_lines=tuple(reference_lines),
        data=data,
        reconstruction_status=reconstruction_status,
    )


def _recover_textual_data(caption: str) -> tuple[tuple[dict[str, Any], ...], str]:
    pairs = []
    for match in re.finditer(r"\b(\d{4}|[-+]?\d+(?:\.\d+)?|[A-Za-z][A-Za-z0-9_\-]{0,24})\s*=\s*([-+]?\d+(?:\.\d+)?)\b", caption):
        raw_x = match.group(1).strip()
        y = float(match.group(2))
        x: float | str
        x = float(raw_x) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw_x) else raw_x
        pairs.append({"x": x, "y": y, "label": raw_x, "provenance": TEXT_DERIVED})
        if len(pairs) >= 40:
            break
    if not pairs:
        return (), DATA_UNAVAILABLE
    return tuple(pairs), TEXT_DERIVED


def _detect_panels(caption: str, figure_number: str, figure_type: str) -> list[FigurePanel]:
    labels = re.findall(r"\bPanel\s+([A-Z])\b|\(([A-Z])\)", caption)
    panel_labels = [left or right for left, right in labels]
    if not panel_labels:
        return [FigurePanel(panel_id=_stable_id("panel", figure_number, "main"), label="main", figure_type=figure_type)]
    return [
        FigurePanel(
            panel_id=_stable_id("panel", figure_number, label),
            label=label,
            caption_fragment=_fragment_after_panel(caption, label),
            figure_type=figure_type,
        )
        for label in dict.fromkeys(panel_labels)
    ]


def _render_registry(figures: tuple[ResearchFigure, ...]) -> str:
    if not figures:
        return "`NO_FIGURES_DETECTED` - no scientifically meaningful figure reference was found."
    blocks = []
    for figure in figures:
        blocks.append(
            "\n".join(
                [
                    f"### Figure {figure.figure_number or figure.id}",
                    f"- Figure ID: `{figure.id}`",
                    f"- Category: `{figure.figure_category}`",
                    f"- Figure type: `{figure.figure_type}`",
                    f"- Reconstruction status: `{figure.reconstruction_status}`",
                    f"- Verification status: `{figure.verification_status}`",
                    f"- Panel count: {len(figure.panels)}",
                    f"- Caption: {figure.caption or '`NOT_EXTRACTED`'}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _render_queue(figures: tuple[ResearchFigure, ...]) -> str:
    if not figures:
        return "- [ ] Re-run after PDF figure extraction or OCR is available."
    lines = []
    for figure in figures:
        lines.extend(
            [
                f"- [ ] Figure {figure.figure_number}: search author replication data.",
                f"- [ ] Figure {figure.figure_number}: check supplementary material before digitization.",
                f"- [ ] Figure {figure.figure_number}: verify axis labels and units from the source crop.",
            ]
        )
        if figure.provenance.data_origin == DATA_UNAVAILABLE:
            lines.append(f"- [ ] Figure {figure.figure_number}: mark as `PARTIAL_RECONSTRUCTION` until data are recovered.")
    return "\n".join(lines)


def _render_specs(figures: tuple[ResearchFigure, ...]) -> str:
    if not figures:
        return "```json\n[]\n```"
    specs = [visualization_spec_to_dict(figure.visualization_spec) for figure in figures if figure.visualization_spec]
    return "```json\n" + json.dumps(specs, ensure_ascii=False, indent=2) + "\n```"


def _render_provenance(figures: tuple[ResearchFigure, ...]) -> str:
    if not figures:
        return "`NOT_AVAILABLE`"
    return "\n".join(
        [
            (
                f"- Figure {figure.figure_number}: source stage `{figure.provenance.source_stage}`, "
                f"data origin `{figure.provenance.data_origin}`, confidence `{figure.provenance.confidence}`."
            )
            for figure in figures
        ]
    )


def _render_integrity_rules() -> str:
    return "\n".join(
        [
            "- Original source figure must remain separate from reconstructed output.",
            "- D3 JavaScript is renderer code only; the JSON Visualization Specification is canonical.",
            "- Digitized or AI-estimated values must never be marked as author data.",
            "- Missing values must remain unavailable rather than being invented.",
            "- Human verification is required before a reconstruction becomes canonical research evidence.",
        ]
    )


def _infer_x_label(caption: str, fallback: str) -> str:
    match = re.search(r"\bx[- ]axis\s*(?:shows|is|:)?\s*([^.;,]+)", caption, re.IGNORECASE)
    if match:
        return re.split(r"\b(?:and\s+)?(?:the\s+)?y[- ]axis\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return fallback


def _infer_y_label(caption: str) -> str:
    match = re.search(r"\by[- ]axis\s*(?:shows|is|:)?\s*([^.;,]+)", caption, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if re.search(r"\b(?:effect|coefficient|estimate)\b", caption, re.IGNORECASE):
        return "effect estimate"
    if re.search(r"\b(?:rate|share|percent|percentage)\b", caption, re.IGNORECASE):
        return "rate/share"
    return "value"


def _infer_x_type(label: str) -> str:
    return "temporal" if re.search(r"\b(?:time|year|month|date|event)\b", label, re.IGNORECASE) else "quantitative"


def _mentions_multiple_series(caption: str) -> bool:
    return bool(re.search(r"\b(?:treated|control|male|female|groups?|series|cohorts?)\b", caption, re.IGNORECASE))


def _extract_annotations(caption: str) -> list[AnnotationSpec]:
    annotations = []
    for keyword in ("policy", "treatment", "cutoff", "shock", "reform"):
        if re.search(rf"\b{keyword}\b", caption, re.IGNORECASE):
            annotations.append(AnnotationSpec(text=f"Caption references {keyword}.", target=keyword))
    return annotations[:4]


def _bbox_from_candidate(candidate: dict[str, Any]) -> BoundingBox | None:
    bbox = candidate.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    top, left, bottom, right = bbox
    return BoundingBox(top=int(top), left=int(left), bottom=int(bottom), right=int(right))


def _fragment_after_panel(caption: str, label: str) -> str:
    match = re.search(rf"(?:Panel\s+{re.escape(label)}|\({re.escape(label)}\))\s*[:.\-]?\s*([^()]+)", caption)
    return _clean_caption(match.group(1)) if match else ""


def _clean_caption(value: str) -> str:
    cleaned = " ".join(str(value or "").split()).strip(" .:-")
    return cleaned[:1000]


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for candidate in candidates:
        key = (candidate.get("figure_number", ""), candidate.get("caption", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_drop_none(item) for item in value)
    return value


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "\x1f".join(str(part).strip().casefold() for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"
