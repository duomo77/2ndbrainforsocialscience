import {
  Activity,
  CheckCircle2,
  Clipboard,
  FileText,
  FolderGit2,
  Loader2,
  Play,
  Settings2,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { analyzeFile, analyzeText, health } from "./api";
import type { AnalysisEvent, AnalyzePayload, AnalyzeResponse, InputType } from "./types";

const inputTypes: { value: InputType; label: string }[] = [
  { value: "notes", label: "Notes" },
  { value: "paper", label: "Paper" },
  { value: "transcript", label: "Transcript" },
  { value: "dataset", label: "Dataset" },
  { value: "equation", label: "Equation" },
];

const sampleText =
  "Difference-in-differences estimates depend on parallel trends. A useful next step is to connect [[Treatment Effect]] assumptions to robustness checks and heterogeneous effects.";

function App() {
  const [inputType, setInputType] = useState<InputType>("notes");
  const [title, setTitle] = useState("ROS Web Note");
  const [content, setContent] = useState(sampleText);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("demo-local");
  const [vaultPath, setVaultPath] = useState("");
  const [autoSave, setAutoSave] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outputView, setOutputView] = useState<"card" | "context">("card");

  useEffect(() => {
    health()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  const payload: AnalyzePayload = useMemo(
    () => ({
      input_type: inputType,
      raw_text: content,
      metadata: { title },
      api_key: apiKey,
      base_url: baseUrl,
      model: model || "demo-local",
      vault_path: vaultPath,
      auto_save: autoSave,
      topic_override: "",
    }),
    [apiKey, autoSave, baseUrl, content, inputType, model, title, vaultPath],
  );

  async function runAnalysis() {
    setBusy(true);
    setError("");
    setEvents([]);
    try {
      const response = file ? await analyzeFile(file, payload) : await analyzeText(payload);
      setResult(response);
      setEvents(response.events);
      setOutputView(response.deep_context_markdown ? "context" : "card");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function copyMarkdown() {
    const activeMarkdown =
      outputView === "context" ? result?.deep_context_markdown : result?.markdown;
    if (!activeMarkdown) return;
    await navigator.clipboard.writeText(activeMarkdown);
  }

  const activeMarkdown =
    outputView === "context"
      ? result?.deep_context_markdown || "Deep Research Context will appear for paper inputs."
      : result?.markdown || "Markdown output will appear here.";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <FolderGit2 aria-hidden="true" size={24} />
          <div>
            <h1>ROS Web</h1>
            <p>Research Operating System</p>
          </div>
        </div>
        <div className={`health ${backendOk ? "ok" : backendOk === false ? "bad" : ""}`}>
          <Activity aria-hidden="true" size={16} />
          <span>{backendOk === null ? "Checking" : backendOk ? "FastAPI online" : "Backend offline"}</span>
        </div>
      </header>

      <section className="workspace">
        <aside className="control-panel">
          <div className="panel-title">
            <Settings2 aria-hidden="true" size={18} />
            <h2>Run</h2>
          </div>

          <label className="field">
            <span>Input</span>
            <select value={inputType} onChange={(event) => setInputType(event.target.value as InputType)}>
              {inputTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Title</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>

          <label className="field">
            <span>Model</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </label>

          <label className="field">
            <span>Base URL</span>
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="OpenAI compatible endpoint" />
          </label>

          <label className="field">
            <span>API Key</span>
            <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
          </label>

          <label className="field">
            <span>Vault Path</span>
            <input value={vaultPath} onChange={(event) => setVaultPath(event.target.value)} />
          </label>

          <label className="toggle-row">
            <input type="checkbox" checked={autoSave} onChange={(event) => setAutoSave(event.target.checked)} />
            <span>Auto-save to vault</span>
          </label>

          <label className="upload-box">
            <Upload aria-hidden="true" size={20} />
            <span>{file ? file.name : "Choose file"}</span>
            <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>

          <button className="primary-action" onClick={runAnalysis} disabled={busy || (!content.trim() && !file)}>
            {busy ? <Loader2 className="spin" aria-hidden="true" size={18} /> : <Play aria-hidden="true" size={18} />}
            <span>{busy ? "Running" : "Analyze"}</span>
          </button>
        </aside>

        <section className="editor-pane">
          <div className="pane-header">
            <div className="panel-title">
              <FileText aria-hidden="true" size={18} />
              <h2>Source</h2>
            </div>
            {file && (
              <button className="ghost-button" onClick={() => setFile(null)}>
                Clear file
              </button>
            )}
          </div>
          <textarea value={content} onChange={(event) => setContent(event.target.value)} />
        </section>

        <section className="result-pane">
          <div className="pane-header">
            <div className="panel-title">
              <CheckCircle2 aria-hidden="true" size={18} />
              <h2>Result</h2>
            </div>
            <div className="result-actions">
              <div className="output-tabs" role="tablist" aria-label="Output layer">
                <button
                  className={outputView === "card" ? "active" : ""}
                  onClick={() => setOutputView("card")}
                  role="tab"
                  aria-selected={outputView === "card"}
                >
                  Card
                </button>
                <button
                  className={outputView === "context" ? "active" : ""}
                  onClick={() => setOutputView("context")}
                  disabled={!result?.deep_context_markdown}
                  role="tab"
                  aria-selected={outputView === "context"}
                >
                  Context
                </button>
              </div>
              <button
                className="icon-button"
                onClick={copyMarkdown}
                disabled={!result?.markdown}
                title="Copy active Markdown"
              >
                <Clipboard aria-hidden="true" size={18} />
              </button>
            </div>
          </div>
          {error ? <div className="error-box">{error}</div> : null}
          {result?.saved_path || result?.deep_context_path ? (
            <div className="save-paths">
              {result.saved_path ? <p>Saved: {result.saved_path}</p> : null}
              {result.deep_context_path ? <p>Context: {result.deep_context_path}</p> : null}
            </div>
          ) : null}
          <pre className="markdown-output">{activeMarkdown}</pre>
        </section>
      </section>

      <section className="event-band">
        <div className="panel-title">
          <Activity aria-hidden="true" size={18} />
          <h2>Runtime Events</h2>
        </div>
        <div className="event-list">
          {(events.length ? events : [{ kind: "status", message: "Idle", payload: {} } as AnalysisEvent]).map((event, index) => (
            <div className="event-row" key={`${event.kind}-${index}`}>
              <span>{event.kind}</span>
              <p>{event.message}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
