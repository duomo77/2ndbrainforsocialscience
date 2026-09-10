# Action Chain Verification

| Action | Trigger | Handler | Service | DB | Graph | Vector | AI | Persistence | UI Result | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Start web runtime | python main.py / npm run api / npm run dev | main.main | api.app.FastAPI | N/A | N/A at startup | N/A | N/A | Static React build served when available | HTTP API available on localhost | RUNTIME VERIFIED |
| Run analysis | React Analyze button / POST /api/analyze | api.app.analyze | WebAnalysisRuntime -> AnalysisPipeline | Memory stores where enabled | Legacy graph + typed semantic graph | Not currently canonical | ros_engine.analyze_* | Optional Obsidian save, cache, memory trust | React result pane receives Markdown JSON payload | RUNTIME VERIFIED |
| Save note to Obsidian | Analysis auto-save / result save | obsidian_sync.save_note_to_vault | Obsidian sync | N/A | Index wikilinks visible in note | N/A | N/A | Markdown file + `_INDEX.md` | Save signal with path/topic | RUNTIME VERIFIED |
| Validate provider connection | Settings connection test | ValidationWorker.run | ros_engine.validate_api | N/A | N/A | N/A | Provider probe | None | Validation result signal | RUNTIME VERIFIED |
| Process document | DocumentPipeline.process / process_document | DocumentPipeline.process | Validator -> Identifier -> Parser -> Cleaner -> Storage | DocumentManager in-memory history + file stores | Optional scientific context extension | N/A | N/A | documents/raw, processed, metadata | Document object | RUNTIME VERIFIED |
