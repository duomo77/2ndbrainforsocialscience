export type InputType = "notes" | "paper" | "transcript" | "dataset" | "equation";

export interface AnalysisEvent {
  kind: "status" | "engine" | "token" | "save" | "error";
  message: string;
  payload: Record<string, unknown>;
}

export interface AnalyzePayload {
  input_type: InputType;
  raw_text: string;
  metadata: {
    title?: string;
    authors?: string;
    year?: string;
    journal?: string;
    context?: string;
    file_info?: string;
  };
  api_key: string;
  base_url: string;
  model: string;
  vault_path: string;
  auto_save: boolean;
  topic_override: string;
}

export interface AnalyzeResponse {
  markdown: string;
  title: string;
  topic: string;
  cached: boolean;
  saved_path: string;
  deep_context_markdown: string;
  deep_context_path: string;
  research_intelligence_markdown: string;
  research_intelligence_path: string;
  methodology_atlas_paths: string[];
  figure_intelligence_markdown: string;
  figure_intelligence_path: string;
  figure_visualization_specs: VisualizationSpec[];
  events: AnalysisEvent[];
}

export interface VisualizationSpec {
  chart_type: string;
  data_source: {
    origin: string;
    description: string;
    evidence_status: string;
  };
  x: EncodingSpec;
  y: EncodingSpec;
  color?: EncodingSpec;
  annotations?: { text: string; target?: string; evidence_status?: string }[];
  reference_lines?: { axis: "x" | "y"; value: number; label?: string }[];
  interactions?: string[];
  layout?: { width?: number; height?: number };
  data?: FigureDatum[];
  source_figure_id: string;
  reconstruction_status: string;
}

export interface EncodingSpec {
  field: string;
  label: string;
  type: "quantitative" | "temporal" | "nominal" | "ordinal" | string;
  scale: string;
  evidence_status: string;
}

export interface FigureDatum {
  x: number | string;
  y: number;
  label?: string;
  series?: string;
  provenance?: string;
}
