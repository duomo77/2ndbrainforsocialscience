from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core import engine_loader as _el
from core import memory, parsers, ros_engine
from core.analysis_pipeline import AnalysisCallbacks, AnalysisPipeline, AnalysisRuntime
from core.contracts import LLMConfig, Result, VaultConfig


@dataclass
class WebAnalysisEvent:
    kind: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebAnalysisRequest:
    input_type: str
    raw_text: str = ""
    file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    api_key: str = ""
    base_url: str = ""
    model: str = "demo-local"
    vault_path: str = ""
    auto_save: bool = False
    topic_override: str = ""


class WebAnalysisRuntime:
    """PyQt-free runtime adapter for AnalysisPipeline."""

    def __init__(self, request: WebAnalysisRequest, events: list[WebAnalysisEvent]):
        self.request = request
        self.events = events
        self.raw_text = request.raw_text
        self.model = request.model or "demo-local"

    def build_pipeline_runtime(self) -> AnalysisRuntime:
        return AnalysisRuntime(
            parse_input=self.parse_input,
            run_analysis=self.run_analysis,
            run_cognitive_engines=self.run_cognitive_engines,
            persist_legacy_graph=self.persist_legacy_graph,
            update_semantic_graph=self.update_semantic_graph,
            persist_analysis_cache=self.persist_analysis_cache,
            set_raw_text=self.set_raw_text,
            set_model=self.set_model,
            set_metadata=self.set_metadata,
            get_security_layer=_el.get_security_layer,
            get_cache_engine=_el.get_cache_engine,
            get_incremental_engine=_el.get_incremental_engine,
            get_fault_recovery_engine=_el.get_fault_recovery_engine,
            get_resource_governor=_el.get_resource_governor,
            get_rag_engine=_el.get_rag_engine,
            get_rag_observability=_el.get_rag_observability,
            get_graph_integrity_engine=_el.get_graph_integrity_engine,
            get_memory_trust_engine=_el.get_memory_trust_engine,
        )

    def callbacks(self) -> AnalysisCallbacks:
        return AnalysisCallbacks(
            on_token=lambda text: self._event("token", text),
            on_status=lambda text: self._event("status", text),
            on_engine_update=lambda name, data: self._event(
                "engine", name, data if isinstance(data, dict) else {"value": data}
            ),
            on_save_done=lambda path, topic: self._event(
                "save", "saved", {"path": path, "topic": topic}
            ),
            on_error=lambda message: self._event("error", message),
            is_cancelled=lambda: False,
        )

    def _event(self, kind: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append(WebAnalysisEvent(kind=kind, message=message, payload=payload or {}))

    def parse_input(self) -> tuple[str, dict]:
        if self.request.file_path:
            detected = parsers.detect_input_type(self.request.file_path)
            if detected == "paper" or self.request.file_path.endswith(".pdf"):
                return parsers.parse_pdf(self.request.file_path)
            if detected == "dataset":
                return parsers.parse_dataset(self.request.file_path)
            if detected == "transcript":
                return parsers.parse_transcript(self.request.file_path, raw_text=self.raw_text)
            if detected == "audio":
                return parsers.parse_audio(self.request.file_path)
            if detected == "code":
                return parsers.parse_code(self.request.file_path)
            return parsers.parse_text(self.request.file_path), {}
        return self.raw_text, {}

    def run_analysis(
        self,
        content: str,
        file_meta: dict,
        existing_nodes: list[str],
        profile: dict,
        rag_context: str = "",
    ) -> str:
        if not self.request.api_key or self.model == "demo-local":
            return self._local_demo_analysis(content, existing_nodes)

        metadata = self.request.metadata
        callback = lambda text: self._event("token", text)
        common = {
            "api_key": self.request.api_key,
            "base_url": self.request.base_url,
            "model": self.model,
            "existing_nodes": existing_nodes,
            "researcher_profile": profile,
            "content": content,
            "rag_context": rag_context,
            "callback": callback,
            "is_cancelled": lambda: False,
        }
        input_type = self.request.input_type
        if input_type == "paper":
            return ros_engine.analyze_paper(
                title=metadata.get("title", file_meta.get("title", "Unknown")),
                authors=metadata.get("authors", file_meta.get("author", "")),
                year=metadata.get("year", ""),
                journal=metadata.get("journal", ""),
                zotero=metadata.get("zotero", ""),
                **common,
            )
        if input_type == "dataset":
            return ros_engine.analyze_dataset(
                dataset_name=metadata.get("title", "Unknown Dataset"),
                file_info=metadata.get("file_info", ""),
                context=metadata.get("context", ""),
                **common,
            )
        if input_type == "equation":
            return ros_engine.analyze_equation(
                api_key=self.request.api_key,
                base_url=self.request.base_url,
                model=self.model,
                context=metadata.get("context", ""),
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=callback,
                is_cancelled=lambda: False,
            )
        return ros_engine.analyze_transcript(
            source_name=metadata.get("title", "Notes"),
            input_type=input_type if input_type != "notes" else "notes",
            date=metadata.get("year", datetime.now().strftime("%Y-%m-%d")),
            context=metadata.get("context", "General notes"),
            **common,
        )

    def _local_demo_analysis(self, content: str, existing_nodes: list[str]) -> str:
        title = self.request.metadata.get("title") or "ROS Web Analysis"
        clean = " ".join(content.split())
        excerpt = clean[:900] + ("..." if len(clean) > 900 else "")
        concepts = self._concept_candidates(clean, existing_nodes)
        links = ", ".join(f"[[{concept}]]" for concept in concepts) or "[[Research Notes]]"
        return (
            "---\n"
            f"title: {title}\n"
            "type: notes\n"
            "discipline: General\n"
            "epistemic_mode: local-demo\n"
            "tags: [ros, web, analysis]\n"
            "---\n\n"
            "## Core Insight\n"
            f"> {excerpt or 'No content was provided.'}\n\n"
            "## Knowledge Graph Connections\n"
            f"{links}\n\n"
            "## Open Questions\n"
            "- Which claims need stronger evidence?\n"
            "- Which concept should become a durable note?\n\n"
            "## Next Steps\n"
            "- [ ] Re-run with a configured LLM provider for full ROS analysis.\n"
        )

    def _concept_candidates(self, content: str, existing_nodes: list[str]) -> list[str]:
        wikilinks = re.findall(r"\[\[([^\]|]+)", content)
        words = re.findall(r"\b[A-Z][A-Za-z][A-Za-z -]{2,36}\b", content)
        candidates = [*wikilinks, *words, *existing_nodes[:5]]
        seen: set[str] = set()
        result: list[str] = []
        for candidate in candidates:
            value = " ".join(candidate.split()).strip(" .,:;")
            if value and value not in seen:
                seen.add(value)
                result.append(value)
            if len(result) >= 8:
                break
        return result

    def run_cognitive_engines(self, markdown: str, title: str) -> str:
        wikilinks = re.findall(r"\[\[([^\]|]+)\]\]", markdown)
        additions = []

        try:
            evolution = _el.get_evolution_engine()
            if evolution:
                record = evolution.register_note(title=title, content=markdown, wikilinks=wikilinks)
                markdown = evolution.inject_evolution_frontmatter(markdown, title, wikilinks)
                self._event(
                    "engine",
                    "evolution",
                    {
                        "stage": record.current_stage,
                        "score": record.maturity_score,
                        "version": record.version,
                    },
                )
        except Exception as exc:
            self._event("status", f"Evolution skipped: {exc}")

        try:
            contradiction = _el.get_contradiction_engine()
            if contradiction:
                findings = contradiction.scan_rule_based(markdown, title)
                report = contradiction.format_contradiction_report(title)
                if report:
                    additions.append(report)
                self._event("engine", "contradiction", {"count": len(findings)})
        except Exception as exc:
            self._event("status", f"Contradiction scan skipped: {exc}")

        try:
            math_engine = _el.get_math_engine()
            if math_engine:
                objects = math_engine.scan_content(markdown, title)
                section = math_engine.format_math_section(objects)
                if section:
                    additions.append(section)
                self._event("engine", "math_ontology", {"count": len(objects)})
        except Exception as exc:
            self._event("status", f"Math scan skipped: {exc}")

        if additions:
            return (
                markdown.rstrip()
                + "\n\n---\n\n## ROS Cognitive Engine Output\n\n"
                + "\n".join(additions)
            )
        return markdown

    def persist_legacy_graph(self, title: str, markdown: str) -> None:
        try:
            edges = ros_engine.extract_graph_edges(
                self.request.api_key, self.request.base_url, self.model, markdown
            )
            memory.update_graph(title, "", edges)
            memory.register_concepts(
                edges.get("explicit_links", []) + edges.get("implicit_links", [])
            )
        except Exception as exc:
            self._event("status", f"Legacy graph skipped: {exc}")

    def update_semantic_graph(self, title: str, markdown: str) -> None:
        try:
            from core.graph_migration import migrate_legacy_to_typed
            from core.knowledge_graph import get_knowledge_graph_service

            try:
                migrate_legacy_to_typed()
            except Exception:
                pass
            report = get_knowledge_graph_service().ingest_markdown(
                title=title,
                markdown=markdown,
                source_type=self.request.input_type,
                source_ref=self.request.file_path or "",
            )
            self._event(
                "engine",
                "semantic_graph",
                {
                    "nodes": report.total_nodes,
                    "edges": report.total_edges,
                    "nodes_upserted": report.nodes_upserted,
                    "edges_upserted": report.edges_upserted,
                },
            )
        except Exception as exc:
            self._event("status", f"Semantic graph skipped: {exc}")

    def persist_analysis_cache(
        self,
        cache: Any,
        incremental: Any,
        content_hash: str,
        cache_key: str,
        content: str,
        enhanced: str,
        is_fallback: bool,
    ) -> None:
        if not (cache and incremental) or is_fallback:
            return
        try:
            cache.put_analysis(content_hash, self.model, enhanced)
            incremental.mark_computed(cache_key, content)
        except Exception as exc:
            self._event("status", f"Cache skipped: {exc}")

    def set_raw_text(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def set_model(self, model: str) -> None:
        self.model = model

    def set_metadata(self, metadata: dict[str, Any]) -> None:
        self.request.metadata = dict(metadata)


def run_web_analysis(request: WebAnalysisRequest) -> tuple[Result, list[WebAnalysisEvent]]:
    events: list[WebAnalysisEvent] = []
    web_runtime = WebAnalysisRuntime(request, events)
    pipeline = AnalysisPipeline(web_runtime.build_pipeline_runtime())
    result = pipeline.run(
        input_type=request.input_type,
        raw_text=request.raw_text,
        metadata=request.metadata,
        file_path=request.file_path,
        llm_config=LLMConfig(
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model or "demo-local",
        ),
        vault_config=VaultConfig(
            vault_path=request.vault_path,
            auto_save=request.auto_save,
        ),
        topic_override=request.topic_override,
        callbacks=web_runtime.callbacks(),
    )
    return result, events
