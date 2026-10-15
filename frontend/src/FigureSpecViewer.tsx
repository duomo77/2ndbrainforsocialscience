import * as d3 from "d3";
import { useEffect, useRef } from "react";

import type { FigureDatum, VisualizationSpec } from "./types";

interface FigureSpecViewerProps {
  specs: VisualizationSpec[];
}

const emptyColor = "#81909a";
const markColor = "#146c78";
const accentColor = "#b05c26";

type XScale =
  | { kind: "linear"; scale: d3.ScaleLinear<number, number> }
  | { kind: "point"; scale: d3.ScalePoint<string> };

export function FigureSpecViewer({ specs }: FigureSpecViewerProps) {
  if (!specs.length) {
    return null;
  }

  return (
    <div className="figure-spec-stack" aria-label="D3 figure reconstructions">
      {specs.slice(0, 4).map((spec) => (
        <FigureChart key={spec.source_figure_id} spec={spec} />
      ))}
    </div>
  );
}

function FigureChart({ spec }: { spec: VisualizationSpec }) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svgNode = svgRef.current;
    if (!svgNode) return;

    const width = spec.layout?.width ?? 720;
    const height = spec.layout?.height ?? 420;
    const margin = { top: 26, right: 34, bottom: 58, left: 68 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const data = normalizeData(spec.data ?? []);

    const svg = d3.select(svgNode);
    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img");

    const frame = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const xScale = buildXScale(spec, data, innerWidth);
    const y = d3
      .scaleLinear()
      .domain(data.length ? d3.extent(data, (datum) => datum.y) as [number, number] : [-1, 1])
      .nice()
      .range([innerHeight, 0]);

    frame.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(5).tickSize(-innerWidth).tickFormat(() => ""));
    frame
      .append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(xScale.kind === "linear" ? d3.axisBottom(xScale.scale).ticks(5) : d3.axisBottom(xScale.scale));
    frame.append("g").call(d3.axisLeft(y).ticks(5));

    frame
      .append("text")
      .attr("class", "axis-label")
      .attr("x", innerWidth / 2)
      .attr("y", innerHeight + 42)
      .attr("text-anchor", "middle")
      .text(spec.x.label || spec.x.field);

    frame
      .append("text")
      .attr("class", "axis-label")
      .attr("transform", "rotate(-90)")
      .attr("x", -innerHeight / 2)
      .attr("y", -48)
      .attr("text-anchor", "middle")
      .text(spec.y.label || spec.y.field);

    drawReferenceLines(frame, spec, xScale, y, innerWidth, innerHeight);

    if (data.length) {
      drawMarks(frame, spec, data, xScale, y, innerHeight);
    } else {
      drawScaffold(frame, innerWidth, innerHeight);
    }
  }, [spec]);

  return (
    <article className="figure-card">
      <div className="figure-card-header">
        <div>
          <h3>{spec.chart_type.replace(/_/g, " ")}</h3>
          <p>{spec.data_source.origin} · {spec.reconstruction_status}</p>
        </div>
        <span>{spec.data_source.evidence_status}</span>
      </div>
      <svg ref={svgRef} aria-label={`${spec.chart_type} reconstruction`} />
      <p className="figure-provenance">{spec.data_source.description}</p>
    </article>
  );
}

function normalizeData(data: FigureDatum[]): Required<Pick<FigureDatum, "x" | "y">>[] {
  return data
    .filter((datum) => datum.x !== undefined && Number.isFinite(Number(datum.y)))
    .map((datum) => ({ x: datum.x, y: Number(datum.y) }));
}

function buildXScale(spec: VisualizationSpec, data: Required<Pick<FigureDatum, "x" | "y">>[], width: number): XScale {
  const numeric = data.every((datum) => typeof datum.x === "number" || /^-?\d+(\.\d+)?$/.test(String(datum.x)));
  if (numeric) {
    const domain = data.length ? d3.extent(data, (datum) => Number(datum.x)) as [number, number] : [-1, 1];
    return { kind: "linear", scale: d3.scaleLinear().domain(domain).nice().range([0, width]) };
  }
  const values = data.length ? data.map((datum) => String(datum.x)) : [spec.x.label || spec.x.field];
  return { kind: "point", scale: d3.scalePoint<string>().domain(values).range([0, width]).padding(0.5) };
}

function drawMarks(
  frame: d3.Selection<SVGGElement, unknown, null, undefined>,
  spec: VisualizationSpec,
  data: Required<Pick<FigureDatum, "x" | "y">>[],
  xScale: XScale,
  y: d3.ScaleLinear<number, number>,
  innerHeight: number,
) {
  const xValue = (datum: Required<Pick<FigureDatum, "x" | "y">>) =>
    xScale.kind === "linear" ? xScale.scale(Number(datum.x)) : xScale.scale(String(datum.x));

  if (spec.chart_type.includes("BAR")) {
    const bandwidth = Math.max(16, Math.min(48, 360 / Math.max(data.length, 1)));
    frame
      .selectAll("rect.mark")
      .data(data)
      .join("rect")
      .attr("class", "mark")
      .attr("x", (datum) => Number(xValue(datum)) - bandwidth / 2)
      .attr("y", (datum) => y(Math.max(0, datum.y)))
      .attr("width", bandwidth)
      .attr("height", (datum) => Math.abs(y(datum.y) - y(0)))
      .attr("fill", markColor);
    return;
  }

  if (spec.chart_type.includes("LINE") || spec.chart_type.includes("TIME") || spec.chart_type.includes("EVENT")) {
    const line = d3
      .line<Required<Pick<FigureDatum, "x" | "y">>>()
      .x((datum) => Number(xValue(datum)))
      .y((datum) => y(datum.y));
    frame.append("path").datum(data).attr("class", "series-line").attr("d", line).attr("fill", "none");
  }

  frame
    .selectAll("circle.mark")
    .data(data)
    .join("circle")
    .attr("class", "mark")
    .attr("cx", (datum) => Number(xValue(datum)))
    .attr("cy", (datum) => y(datum.y))
    .attr("r", spec.chart_type.includes("SCATTER") ? 4 : 3)
    .attr("fill", spec.chart_type.includes("COEFFICIENT") ? accentColor : markColor)
    .append("title")
    .text((datum) => `${spec.x.label || "x"}: ${datum.x}\n${spec.y.label || "y"}: ${datum.y}`);

  if (spec.chart_type.includes("COEFFICIENT")) {
    frame
      .selectAll("line.stem")
      .data(data)
      .join("line")
      .attr("class", "stem")
      .attr("x1", (datum) => Number(xValue(datum)))
      .attr("x2", (datum) => Number(xValue(datum)))
      .attr("y1", innerHeight)
      .attr("y2", (datum) => y(datum.y));
  }
}

function drawReferenceLines(
  frame: d3.Selection<SVGGElement, unknown, null, undefined>,
  spec: VisualizationSpec,
  xScale: XScale,
  y: d3.ScaleLinear<number, number>,
  width: number,
  height: number,
) {
  for (const line of spec.reference_lines ?? []) {
    if (line.axis === "y") {
      const yPos = y(line.value);
      frame.append("line").attr("class", "reference-line").attr("x1", 0).attr("x2", width).attr("y1", yPos).attr("y2", yPos);
    }
    if (line.axis === "x" && xScale.kind === "linear") {
      const xPos = xScale.scale(line.value);
      frame.append("line").attr("class", "reference-line").attr("x1", xPos).attr("x2", xPos).attr("y1", 0).attr("y2", height);
    }
  }
}

function drawScaffold(frame: d3.Selection<SVGGElement, unknown, null, undefined>, width: number, height: number) {
  frame
    .append("rect")
    .attr("class", "empty-plot")
    .attr("x", 0)
    .attr("y", 0)
    .attr("width", width)
    .attr("height", height)
    .attr("fill", "none");
  frame
    .append("text")
    .attr("x", width / 2)
    .attr("y", height / 2)
    .attr("text-anchor", "middle")
    .attr("fill", emptyColor)
    .text("DATA UNAVAILABLE");
}
