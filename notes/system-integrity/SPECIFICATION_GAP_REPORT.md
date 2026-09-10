# Specification Gap Report

## Documented but Not Implemented
- Vector store
- Agents

## Partially Implemented
- Document pipeline
- Document intelligence
- RAG

## Implemented Differently
- RAG is documented with embedding-search vocabulary, but current verified retrieval is local keyword/graph-style retrieval.

## Implemented but Not Connected
- Provider and agent interfaces exist, but no runtime agent execution chain was found in the current scope.

## Implemented but Runtime Broken

## Implemented but Untested
- Full live provider calls require credentials and are not executed by this verifier.

## Implemented but Undocumented
- `core.analysis_pipeline.AnalysisPipeline` is implemented and documented in the Phase 6 review file; main README has not yet been updated.

## Documentation Outdated
- `ARCHITECTURE.md` references removed or roadmap components such as `state_manager.py` as live ownership.

## Unable to Verify
- Live LLM provider behavior without credentials.
- Full browser interaction beyond HTTP/build smoke tests.
- User's real Obsidian vault integrity, by design.
