# Actual Architecture Map

## Runtime Entry Points

```text
main.py / npm run api / npm run dev
  -> api.app.FastAPI
  -> api.runtime.WebAnalysisRuntime
  -> core.analysis_pipeline.AnalysisPipeline
  -> core.ros_engine.analyze_*
  -> cognitive engines
  -> graph / memory / cache / Obsidian persistence
```

## React Frontend

```text
frontend/src/App.tsx
  -> frontend/src/api.ts
  -> POST /api/analyze or /api/analyze-file
  -> Markdown result pane + runtime event list
```

## Document Processing

```text
core.pipeline.pipeline.DocumentPipeline
  -> validator
  -> identifier
  -> parser registry
  -> cleaner
  -> file storage
  -> document manager history
```

## Semantic Graph

```text
AnalysisPipeline
  -> WebAnalysisRuntime.update_semantic_graph / AnalysisWorker._update_semantic_graph
  -> graph_migration.migrate_legacy_to_typed
  -> knowledge_graph.KnowledgeGraphService
  -> KnowledgeGraphStore JSON file
```

## RAG

```text
AnalysisPipeline
  -> engine_loader.get_rag_engine
  -> rag_engine.ROSRAGEngine
  -> CheapestCognitionRouter / HierarchicalRetriever / RAGContextBuilder
  -> untrusted retrieved context in ros_engine prompts
```

## Not Found Runtime Architecture

- Vector database implementation: NOT FOUND.
- Real embedding provider lifecycle: NOT FOUND.
- Runtime research agents with tool authority: NOT FOUND.
