import type { AnalyzePayload, AnalyzeResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function analyzeText(payload: AnalyzePayload): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseAnalysisResponse(response);
}

export async function analyzeFile(
  file: File,
  payload: AnalyzePayload,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("input_type", payload.input_type);
  form.append("title", payload.metadata.title || file.name);
  form.append("api_key", payload.api_key);
  form.append("base_url", payload.base_url);
  form.append("model", payload.model);
  form.append("vault_path", payload.vault_path);
  form.append("auto_save", String(payload.auto_save));
  form.append("topic_override", payload.topic_override);

  const response = await fetch(`${API_BASE}/api/analyze-file`, {
    method: "POST",
    body: form,
  });
  return parseAnalysisResponse(response);
}

export async function health(): Promise<{ ok: boolean; runtime: string }> {
  const response = await fetch(`${API_BASE}/api/health`);
  if (!response.ok) {
    throw new Error("Backend health check failed");
  }
  return response.json();
}

async function parseAnalysisResponse(response: Response): Promise<AnalyzeResponse> {
  const body = await response.json();
  if (!response.ok) {
    const detail = body.detail ?? {};
    throw new Error(detail.error || body.error || "Analysis failed");
  }
  return body;
}
