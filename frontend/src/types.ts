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
  events: AnalysisEvent[];
}
