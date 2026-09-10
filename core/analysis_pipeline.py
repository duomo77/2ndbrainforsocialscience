"""
analysis_pipeline.py -- Qt-free analysis orchestration boundary.

Phase 6 requires controlled extension points before adding larger research
capabilities.  This module extracts the end-to-end analysis lifecycle from the
desktop worker into a plain Python service while preserving the existing worker
behaviour through injected runtime callbacks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from core import memory, obsidian_sync, ros_engine
from core.constants import (
    MAX_EXISTING_NODES_IN_PROMPT,
    MAX_NODE_NAME_LENGTH,
    MAX_WIKILINKS_PER_NOTE,
)
from core.contracts import AnalysisResult, AnalysisStatus, Err, LLMConfig, Ok, Result, VaultConfig
from core.research_context import add_deep_context_link, build_deep_research_context
from core.research_intelligence import (
    add_research_intelligence_link,
    build_research_intelligence,
    merge_methodology_atlas_markdown,
)
from core.utils.markdown_utils import extract_frontmatter, extract_wikilink_targets, inject_frontmatter
from core.utils.text_utils import rank_concept_nodes

StatusCallback = Callable[[str], None]
EngineCallback = Callable[[str, dict], None]
TokenCallback = Callable[[str], None]
SaveCallback = Callable[[str, str], None]
ErrorCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]


@dataclass
class AnalysisCallbacks:
    """Non-UI callbacks used by the analysis pipeline."""

    on_token: TokenCallback | None = None
    on_status: StatusCallback | None = None
    on_engine_update: EngineCallback | None = None
    on_save_done: SaveCallback | None = None
    on_error: ErrorCallback | None = None
    is_cancelled: CancelCallback | None = None

    def status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def engine(self, name: str, payload: dict) -> None:
        if self.on_engine_update:
            self.on_engine_update(name, payload)

    def saved(self, path: str, topic: str) -> None:
        if self.on_save_done:
            self.on_save_done(path, topic)

    def error(self, message: str) -> None:
        if self.on_error:
            self.on_error(message)

    def cancelled(self) -> bool:
        return bool(self.is_cancelled and self.is_cancelled())


@dataclass
class AnalysisRuntime:
    """Injected dependencies that keep the pipeline independent from PyQt."""

    parse_input: Callable[[], tuple[str, dict]]
    run_analysis: Callable[[str, dict, list[str], Any, str], str]
    run_cognitive_engines: Callable[[str, str], str]
    persist_legacy_graph: Callable[[str, str], None]
    update_semantic_graph: Callable[[str, str], None]
    persist_analysis_cache: Callable[[Any, Any, str, str, str, str, bool], None]
    set_raw_text: Callable[[str], None]
    set_model: Callable[[str], None]
    get_security_layer: Callable[[], Any]
    get_cache_engine: Callable[[], Any]
    get_incremental_engine: Callable[[], Any]
    get_fault_recovery_engine: Callable[[], Any]
    get_resource_governor: Callable[[], Any]
    get_rag_engine: Callable[[str, Any], Any]
    get_rag_observability: Callable[[], Any]
    get_graph_integrity_engine: Callable[[], Any]
    get_memory_trust_engine: Callable[[], Any]
    set_metadata: Callable[[dict[str, Any]], None] | None = None


@dataclass(frozen=True)
class PipelineOutcome:
    """Successful analysis pipeline result."""

    markdown: str
    title: str
    topic: str = "Uncategorized"
    cached: bool = False
    saved_path: str = ""
    deep_context_markdown: str = ""
    deep_context_path: str = ""
    research_intelligence_markdown: str = ""
    research_intelligence_path: str = ""
    methodology_atlas_paths: list[str] = field(default_factory=list)
    engine_outputs: dict[str, dict] = field(default_factory=dict)

    def to_analysis_result(self) -> AnalysisResult:
        return AnalysisResult(
            status=AnalysisStatus.CACHED if self.cached else AnalysisStatus.COMPLETED,
            markdown=self.markdown,
            title=self.title,
            discipline="General",
            epistemic_mode="auto",
            topic=self.topic,
            cached=self.cached,
            engine_outputs=self.engine_outputs,
        )


class AnalysisPipeline:
    """Plain Python implementation of the ROS analysis lifecycle."""

    CANCELLED_MESSAGE = "⏹ 사용자 요청으로 분석을 취소했습니다."

    def __init__(self, runtime: AnalysisRuntime):
        self.runtime = runtime

    def run(
        self,
        *,
        input_type: str,
        raw_text: str,
        metadata: dict[str, Any],
        file_path: str | None,
        llm_config: LLMConfig,
        vault_config: VaultConfig,
        topic_override: str = "",
        callbacks: AnalysisCallbacks | None = None,
    ) -> Result[PipelineOutcome, str]:
        callbacks = callbacks or AnalysisCallbacks()
        metadata = dict(metadata or {})
        raw_text = raw_text or ""
        model = llm_config.model

        callbacks.status("🔒 보안 검증 중...")
        sec = self.runtime.get_security_layer()
        if not sec:
            return Err("🔒 보안 엔진을 불러올 수 없어 분석을 중단합니다.")
        try:
            result = sec.validate_input(raw_text, input_type)
        except Exception as exc:
            return Err(f"🔒 보안 검증 오류로 분석을 중단합니다: {exc}")
        if not result.is_safe:
            threats = "; ".join(t.description for t in result.threats)
            return Err(f"⚠️ 보안 검증 실패: {threats}")
        if result.sanitized_content and raw_text:
            raw_text = result.sanitized_content
            self.runtime.set_raw_text(raw_text)
        callbacks.engine("security", {"trust_score": result.trust_score})
        if callbacks.cancelled():
            return Err(self.CANCELLED_MESSAGE)

        metadata, metadata_error = self._validate_metadata(sec, metadata)
        if metadata_error:
            return Err(metadata_error)
        if self.runtime.set_metadata:
            self.runtime.set_metadata(metadata)

        callbacks.status("📂 입력 파싱 중...")
        content, file_meta = self.runtime.parse_input()
        if raw_text and not file_path:
            content = raw_text
        file_meta = file_meta or {}
        if file_meta.get("parse_error"):
            return Err(f"파싱 실패: {file_meta['parse_error']}")
        if not content:
            return Err("분석할 내용이 없습니다. 텍스트 또는 파일을 입력하세요.")
        if file_meta.get("requires_transcription"):
            return Err(content)

        if file_path:
            try:
                file_result = sec.validate_input(content, f"{input_type}:file")
            except Exception as exc:
                return Err(f"🔒 파일 보안 검증 오류로 분석을 중단합니다: {exc}")
            if not file_result.is_safe:
                threats = "; ".join(t.description for t in file_result.threats)
                return Err(f"⚠️ 보안 검증 실패 (파일 콘텐츠): {threats}")
            content = file_result.sanitized_content
            for meta_key in ("title", "author", "subject"):
                if file_meta.get(meta_key):
                    file_meta[meta_key] = sec.validate_title(str(file_meta[meta_key]))

        title = sec.validate_title(
            str(metadata.get("title") or file_meta.get("title") or "Untitled")
        ) or "Untitled"
        metadata["title"] = title
        if self.runtime.set_metadata:
            self.runtime.set_metadata(metadata)

        if callbacks.cancelled():
            return Err(self.CANCELLED_MESSAGE)

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        cache = self.runtime.get_cache_engine()
        incremental = self.runtime.get_incremental_engine()
        cache_key = f"{input_type}:{metadata.get('title', '')}"
        if cache and incremental and not incremental.needs_recompute(cache_key, content):
            cached_result = cache.get_analysis(content_hash, model)
            if cached_result:
                callbacks.status("⚡ 캐시에서 복원됨")
                try:
                    cached_result = self._apply_epistemic_envelope(
                        cached_result,
                        input_type=input_type,
                        title=title,
                        metadata=metadata,
                        file_path=file_path,
                        model=model,
                    )
                except (TypeError, ValueError) as exc:
                    return Err(f"캐시된 Markdown frontmatter 검증 실패: {exc}")
                deep_context = self._build_deep_context_if_needed(
                    input_type=input_type,
                    title=title,
                    content=content,
                    card_markdown=cached_result,
                    metadata=metadata,
                    existing_nodes=[],
                    rag_context="",
                )
                if deep_context:
                    cached_result = add_deep_context_link(cached_result, title)
                research_intelligence = self._build_research_intelligence_if_needed(
                    input_type=input_type,
                    title=title,
                    content=content,
                    card_markdown=cached_result,
                    deep_context_markdown=deep_context.markdown if deep_context else "",
                )
                if research_intelligence:
                    cached_result = add_research_intelligence_link(cached_result, title)
                saved_path, saved_topic, save_error = self._save_output(
                    markdown=cached_result,
                    title=title,
                    input_type=input_type,
                    metadata=metadata,
                    vault_config=vault_config,
                    topic_override=topic_override,
                    callbacks=callbacks,
                )
                if save_error:
                    return Err(save_error)
                deep_context_path, deep_context_error = self._save_deep_context(
                    deep_context=deep_context,
                    vault_config=vault_config,
                    callbacks=callbacks,
                )
                if deep_context_error:
                    return Err(deep_context_error)
                (
                    research_intelligence_path,
                    methodology_atlas_paths,
                    research_intelligence_error,
                ) = self._save_research_intelligence(
                    research_intelligence=research_intelligence,
                    vault_config=vault_config,
                    callbacks=callbacks,
                )
                if research_intelligence_error:
                    return Err(research_intelligence_error)
                return Ok(
                    PipelineOutcome(
                        markdown=cached_result,
                        title=title,
                        topic=saved_topic,
                        cached=True,
                        saved_path=saved_path,
                        deep_context_markdown=deep_context.markdown if deep_context else "",
                        deep_context_path=deep_context_path,
                        research_intelligence_markdown=(
                            research_intelligence.markdown if research_intelligence else ""
                        ),
                        research_intelligence_path=research_intelligence_path,
                        methodology_atlas_paths=methodology_atlas_paths,
                    )
                )

        governor = self.runtime.get_resource_governor()
        if governor:
            try:
                recommended = governor.get_recommended_model(model)
                if recommended != model:
                    callbacks.status(f"⚡ 리소스 압박: 모델 {model} → {recommended}")
                    model = recommended
                    self.runtime.set_model(model)
            except Exception:
                pass

        callbacks.status("🔍 RAG 컨텍스트 최적화 중...")
        rag_context = ""
        rag_plan = None
        try:
            rag = self.runtime.get_rag_engine(vault_config.vault_path or "", cache)
            if rag:
                rag_context, rag_plan = rag.prepare_context(
                    query=f"{metadata.get('title','')} {input_type}",
                    model=model,
                    force_llm=False,
                    hot_only=False,
                )
                obs = self.runtime.get_rag_observability()
                if obs and rag_plan:
                    obs.record_retrieval(
                        query_hash=hashlib.md5(metadata.get("title", "").encode()).hexdigest()[:8],
                        tokens_used=rag_plan.total_tokens,
                        tokens_saved=0,
                        latency_ms=0.0,
                        candidates_total=len(rag_plan.candidates),
                        candidates_selected=len(rag_plan.selected),
                        path=rag_plan.cognition_path,
                    )
                    callbacks.engine("rag", rag.get_metrics_dict())
                if rag_plan and rag_plan.cache_hit:
                    callbacks.status("⚡ RAG: 캐시 히트 — LLM 호출 절약")
                elif rag_context:
                    selected_count = len(rag_plan.selected if rag_plan else [])
                    callbacks.status(f"✅ RAG: {selected_count}개 노트 검색 완료")
        except Exception as rag_err:
            callbacks.status(f"⚠️ RAG 준비 오류 (무시): {rag_err}")

        existing_nodes = memory.get_concept_list()
        if vault_config.vault_path and Path(vault_config.vault_path).exists():
            try:
                vault_concepts = obsidian_sync.scan_vault_concepts(vault_config.vault_path)
                existing_nodes = list(set(existing_nodes + vault_concepts))
            except Exception:
                pass
        existing_nodes = rank_concept_nodes(existing_nodes, content, MAX_EXISTING_NODES_IN_PROMPT)

        profile = memory.load_profile()

        callbacks.status(f"🤖 LLM 분석 중 ({model})...")
        recovery = self.runtime.get_fault_recovery_engine()
        if recovery:
            provider = ros_engine._detect_provider(llm_config.base_url or "", model or "")

            def _llm_call():
                return self.runtime.run_analysis(
                    content, file_meta, existing_nodes, profile, rag_context
                )

            def _safe_fallback():
                from core.fault_recovery import SafeMode

                note = SafeMode().generate_fallback_note(
                    title=metadata.get("title", "Untitled"),
                    content=content,
                    input_type=input_type,
                    error_reason="LLM API 연결 실패",
                    year=int(metadata.get("year", 0) or 0),
                )
                callbacks.status("🟡 안전 모드 활성화 — API 재연결 후 재분석 필요")
                return note

            analysis, is_fallback = recovery.execute_with_recovery(
                provider=provider,
                func=_llm_call,
                fallback=_safe_fallback,
                max_retries=3,
            )
        else:
            analysis = self.runtime.run_analysis(
                content, file_meta, existing_nodes, profile, rag_context
            )
            is_fallback = False

        if not analysis:
            return Err("LLM이 빈 결과를 반환했습니다. API 키와 모델을 확인하세요.")

        try:
            out_result = sec.validate_llm_output(analysis)
        except Exception as exc:
            return Err(f"🔒 LLM 출력 검증 오류로 분석을 중단합니다: {exc}")
        if not out_result.is_safe:
            threats = "; ".join(t.description for t in out_result.threats)
            return Err(f"⚠️ LLM 출력이 보안 검증을 통과하지 못해 저장하지 않습니다: {threats}")
        analysis = out_result.sanitized_content

        try:
            analysis = self._apply_epistemic_envelope(
                analysis,
                input_type=input_type,
                title=title,
                metadata=metadata,
                file_path=file_path,
                model=model,
            )
        except (TypeError, ValueError) as exc:
            return Err(f"Markdown frontmatter 검증 실패: {exc}")

        if callbacks.cancelled():
            return Err(self.CANCELLED_MESSAGE)

        deep_context = self._build_deep_context_if_needed(
            input_type=input_type,
            title=title,
            content=content,
            card_markdown=analysis,
            metadata=metadata,
            existing_nodes=existing_nodes,
            rag_context=rag_context,
        )
        if deep_context:
            analysis = add_deep_context_link(analysis, title)
        research_intelligence = self._build_research_intelligence_if_needed(
            input_type=input_type,
            title=title,
            content=content,
            card_markdown=analysis,
            deep_context_markdown=deep_context.markdown if deep_context else "",
        )
        if research_intelligence:
            analysis = add_research_intelligence_link(analysis, title)

        enhanced = self.runtime.run_cognitive_engines(analysis, title)

        if callbacks.cancelled():
            return Err(self.CANCELLED_MESSAGE)

        saved_path, saved_topic, save_error = self._save_output(
            markdown=enhanced,
            title=title,
            input_type=input_type,
            metadata=metadata,
            vault_config=vault_config,
            topic_override=topic_override,
            callbacks=callbacks,
        )
        if save_error:
            return Err(save_error)
        deep_context_path, deep_context_error = self._save_deep_context(
            deep_context=deep_context,
            vault_config=vault_config,
            callbacks=callbacks,
        )
        if deep_context_error:
            return Err(deep_context_error)
        (
            research_intelligence_path,
            methodology_atlas_paths,
            research_intelligence_error,
        ) = self._save_research_intelligence(
            research_intelligence=research_intelligence,
            vault_config=vault_config,
            callbacks=callbacks,
        )
        if research_intelligence_error:
            return Err(research_intelligence_error)

        callbacks.status("🔗 지식 그래프 업데이트 중...")
        self.runtime.persist_legacy_graph(title, enhanced)
        self.runtime.update_semantic_graph(title, enhanced)
        if research_intelligence:
            self.runtime.update_semantic_graph(
                research_intelligence.intelligence_title,
                research_intelligence.markdown,
            )
        self._update_graph_integrity(input_type, title, enhanced, callbacks)
        self._store_memory_trust(input_type, metadata, title, enhanced)
        self.runtime.persist_analysis_cache(
            cache, incremental, content_hash, cache_key, content, enhanced, is_fallback
        )

        callbacks.status("✅ 분석 완료")
        return Ok(
            PipelineOutcome(
                markdown=enhanced,
                title=title,
                topic=saved_topic,
                saved_path=saved_path,
                deep_context_markdown=deep_context.markdown if deep_context else "",
                deep_context_path=deep_context_path,
                research_intelligence_markdown=(
                    research_intelligence.markdown if research_intelligence else ""
                ),
                research_intelligence_path=research_intelligence_path,
                methodology_atlas_paths=methodology_atlas_paths,
            )
        )

    def _validate_metadata(self, security: Any, metadata: dict[str, Any]) -> tuple[dict, str]:
        """Treat every string metadata field as untrusted input."""
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if not isinstance(value, str):
                sanitized[key] = value
                continue
            try:
                result = security.validate_input(value, f"metadata:{key}")
            except Exception as exc:
                return {}, f"메타데이터 보안 검증 오류 ({key}): {exc}"
            if not result.is_safe:
                threats = "; ".join(t.description for t in result.threats)
                return {}, f"메타데이터 보안 검증 실패 ({key}): {threats}"
            clean_value = result.sanitized_content
            if key == "title":
                clean_value = security.validate_title(clean_value)
            sanitized[key] = clean_value
        return sanitized, ""

    def _apply_epistemic_envelope(
        self,
        markdown: str,
        *,
        input_type: str,
        title: str,
        metadata: dict[str, Any],
        file_path: str | None,
        model: str,
    ) -> str:
        """Attach non-forgeable AI/provenance state to generated Markdown."""
        frontmatter, _body = extract_frontmatter(markdown)
        now = datetime.now(UTC).isoformat()
        source_ref = str(
            metadata.get("source_ref")
            or metadata.get("zotero")
            or (Path(file_path).name if file_path else "direct-input")
        )
        prior_provenance = frontmatter.get("provenance", {})
        if not isinstance(prior_provenance, dict):
            prior_provenance = {}
        provenance = {
            **prior_provenance,
            "source_type": input_type,
            "source_ref": source_ref,
            "transformation": "analysis_pipeline",
            "model": model,
        }
        updates: dict[str, Any] = {
            "title": title,
            "type": input_type,
            "source_type": input_type,
            "ai_generated": True,
            "human_verified": False,
            "evidence_status": "AI_INTERPRETED",
            "citation_status": "NOT_VERIFIED",
            "updated_at": now,
            "provenance": provenance,
        }
        if "created_at" not in frontmatter:
            updates["created_at"] = now
        return inject_frontmatter(markdown, updates)

    def _save_output(
        self,
        *,
        markdown: str,
        title: str,
        input_type: str,
        metadata: dict[str, Any],
        vault_config: VaultConfig,
        topic_override: str,
        callbacks: AnalysisCallbacks,
    ) -> tuple[str, str, str]:
        """Persist canonical Markdown before updating rebuildable graph state."""
        if not vault_config.auto_save:
            return "", "Uncategorized", ""
        if not vault_config.vault_path:
            message = "자동 저장이 활성화되었지만 Obsidian 볼트 경로가 없습니다."
            callbacks.error(message)
            return "", "Uncategorized", message

        callbacks.status("💾 Obsidian 볼트에 저장 중...")
        try:
            ok, path, topic = obsidian_sync.save_note_to_vault(
                vault_path=vault_config.vault_path,
                markdown_content=markdown,
                title=title,
                input_type=input_type,
                journal=metadata.get("journal", ""),
                topic_override=topic_override,
            )
        except Exception as exc:
            message = f"저장 오류: {exc}"
            callbacks.error(message)
            return "", "Uncategorized", message
        if not ok:
            message = f"저장 실패: {path}"
            callbacks.error(message)
            return "", "Uncategorized", message

        memory.log_session("saved", title, input_type, path)
        callbacks.saved(path, topic)
        return path, topic, ""

    def _build_deep_context_if_needed(
        self,
        *,
        input_type: str,
        title: str,
        content: str,
        card_markdown: str,
        metadata: dict[str, Any],
        existing_nodes: list[str],
        rag_context: str,
    ):
        if input_type != "paper":
            return None
        return build_deep_research_context(
            title=title,
            content=content,
            card_markdown=card_markdown,
            metadata=metadata,
            existing_nodes=existing_nodes,
            rag_context=rag_context,
            depth=str(metadata.get("deep_context_depth", "standard")),
        )

    def _build_research_intelligence_if_needed(
        self,
        *,
        input_type: str,
        title: str,
        content: str,
        card_markdown: str,
        deep_context_markdown: str,
    ):
        if input_type != "paper":
            return None
        return build_research_intelligence(
            title=title,
            content=content,
            card_markdown=card_markdown,
            deep_context_markdown=deep_context_markdown,
        )

    def _save_deep_context(
        self,
        *,
        deep_context,
        vault_config: VaultConfig,
        callbacks: AnalysisCallbacks,
    ) -> tuple[str, str]:
        if not deep_context or not vault_config.auto_save:
            return "", ""
        if not vault_config.vault_path:
            message = "Deep Research Context 저장이 필요하지만 Obsidian 볼트 경로가 없습니다."
            callbacks.error(message)
            return "", message

        callbacks.status("📚 Deep Research Context 저장 중...")
        filename = deep_context.context_title
        try:
            filename = self._avoid_human_verified_context_overwrite(
                vault_config.vault_path,
                filename,
            )
            ok, path, _topic = obsidian_sync.save_note_to_vault(
                vault_path=vault_config.vault_path,
                markdown_content=deep_context.markdown,
                title=deep_context.context_title,
                input_type="research_context",
                custom_filename=filename,
            )
        except Exception as exc:
            message = f"Deep Research Context 저장 오류: {exc}"
            callbacks.error(message)
            return "", message
        if not ok:
            message = f"Deep Research Context 저장 실패: {path}"
            callbacks.error(message)
            return "", message
        callbacks.saved(path, "Contexts")
        return path, ""

    def _save_research_intelligence(
        self,
        *,
        research_intelligence,
        vault_config: VaultConfig,
        callbacks: AnalysisCallbacks,
    ) -> tuple[str, list[str], str]:
        if not research_intelligence or not vault_config.auto_save:
            return "", [], ""
        if not vault_config.vault_path:
            message = "Research Intelligence 저장이 필요하지만 Obsidian 볼트 경로가 없습니다."
            callbacks.error(message)
            return "", [], message

        callbacks.status("🧠 Research Intelligence 저장 중...")
        try:
            ok, path, _topic = obsidian_sync.save_note_to_vault(
                vault_path=vault_config.vault_path,
                markdown_content=research_intelligence.markdown,
                title=research_intelligence.intelligence_title,
                input_type="research_intelligence",
                custom_filename=research_intelligence.intelligence_title,
            )
        except Exception as exc:
            message = f"Research Intelligence 저장 오류: {exc}"
            callbacks.error(message)
            return "", [], message
        if not ok:
            message = f"Research Intelligence 저장 실패: {path}"
            callbacks.error(message)
            return "", [], message

        atlas_paths: list[str] = []
        for method_name, atlas_markdown in research_intelligence.methodology_atlas.items():
            atlas_title = f"Method - {method_name}"
            protected_path = self._human_verified_methodology_atlas_path(
                vault_config.vault_path,
                atlas_title,
            )
            if protected_path:
                atlas_paths.append(str(protected_path))
                continue
            atlas_markdown = self._merge_existing_methodology_atlas(
                vault_config.vault_path,
                atlas_title,
                atlas_markdown,
                research_intelligence.title,
            )
            ok, atlas_path, _topic = obsidian_sync.save_note_to_vault(
                vault_path=vault_config.vault_path,
                markdown_content=atlas_markdown,
                title=atlas_title,
                input_type="methodology_atlas",
                custom_filename=atlas_title,
            )
            if ok:
                atlas_paths.append(atlas_path)
        callbacks.saved(path, "Research Intelligence")
        return path, atlas_paths, ""

    @staticmethod
    def _human_verified_methodology_atlas_path(vault_path: str, atlas_title: str) -> Path | None:
        vault = Path(vault_path).expanduser()
        safe_name = obsidian_sync.sanitize_filename(atlas_title)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        target = vault / "Methodology Atlas" / safe_name
        if not target.exists():
            return None
        try:
            frontmatter, _body = extract_frontmatter(target.read_text(encoding="utf-8"))
        except Exception:
            return None
        if frontmatter.get("human_verified") is True:
            return target
        return None

    @staticmethod
    def _merge_existing_methodology_atlas(
        vault_path: str,
        atlas_title: str,
        generated_markdown: str,
        source_title: str,
    ) -> str:
        vault = Path(vault_path).expanduser()
        safe_name = obsidian_sync.sanitize_filename(atlas_title)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        target = vault / "Methodology Atlas" / safe_name
        if not target.exists():
            return generated_markdown
        existing = target.read_text(encoding="utf-8")
        try:
            frontmatter, _body = extract_frontmatter(existing)
            if frontmatter.get("human_verified") is True:
                return existing
        except Exception:
            pass
        return merge_methodology_atlas_markdown(existing, generated_markdown, source_title)

    @staticmethod
    def _avoid_human_verified_context_overwrite(vault_path: str, filename: str) -> str:
        vault = Path(vault_path).expanduser()
        safe_name = obsidian_sync.sanitize_filename(filename)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        target = vault / "Contexts" / safe_name
        if not target.exists():
            return filename
        try:
            frontmatter, _body = extract_frontmatter(target.read_text(encoding="utf-8"))
        except Exception:
            return filename
        if frontmatter.get("human_verified") is True:
            suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            return f"{target.stem} - AI Update {suffix}.md"
        return filename

    def _update_graph_integrity(
        self, input_type: str, title: str, enhanced: str, callbacks: AnalysisCallbacks
    ) -> None:
        graph_engine = self.runtime.get_graph_integrity_engine()
        if not graph_engine:
            return
        try:
            graph_engine.begin_transaction()
            graph_engine.add_node(title, input_type, trust_score=0.9)
            wikilinks_found = extract_wikilink_targets(enhanced)
            bounded_links = sorted(
                link
                for link in set(wikilinks_found)
                if link != title and len(link) <= MAX_NODE_NAME_LENGTH
            )[:MAX_WIKILINKS_PER_NOTE]
            for link in bounded_links:
                graph_engine.add_node(link, "concept", trust_score=0.7)
                graph_engine.add_edge(title, link, "references", confidence=0.8)
            ok, _msg = graph_engine.commit_transaction()
            stats = graph_engine.get_stats()
            callbacks.engine(
                "graph_integrity",
                {
                    "nodes": stats["nodes"],
                    "edges": stats["edges"],
                    "ok": ok,
                },
            )
        except Exception as exc:
            callbacks.status(f"⚠️ Graph Integrity: {exc}")

    def _store_memory_trust(
        self, input_type: str, metadata: dict[str, Any], title: str, enhanced: str
    ) -> None:
        mem_trust = self.runtime.get_memory_trust_engine()
        if not mem_trust:
            return
        try:
            mem_trust.store_memory(
                content=enhanced[:1000],
                source=title,
                source_type="llm_output",
                tags=[input_type, metadata.get("journal", "")],
            )
        except Exception:
            pass
