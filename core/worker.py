"""
worker.py — ROS v4.0 Analysis Worker
=====================================
5개 인지 엔진 + 7개 인프라 엔진 완전 통합 파이프라인:
  Cognitive Engines:
    A. Note Evolution System
    B. Contradiction Engine
    C. Idea Lineage Tracking
    D. Mathematical Object Linking
    E. Research Tension Detection + Graph DB
  Infrastructure Engines (v4.0 신규):
    F. Security Layer (프롬프트 인젝션 방어)
    G. Graph Integrity (트랜잭션 뮤테이션)
    H. Memory Trust (신뢰도 감쇠 + 격리)
    I. Performance Engine (캐시 + 증분 계산)
    J. Orchestration (큐 + 리소스 거버넌스)
    K. Fault Recovery (회로 차단기 + 안전 모드)
"""

from __future__ import annotations

import re
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core import ros_engine, parsers, obsidian_sync, memory
from core.analysis_pipeline import AnalysisCallbacks, AnalysisPipeline, AnalysisRuntime
from core.contracts import LLMConfig, VaultConfig

# ── v8.0 엔진 로더 (중앙화, 구조화 로깅, BUG-4 수정) ────────────────────────
# 기존 _get_xxx() 헬퍼는 오류를 silent하게 None으로 반환했음.
# engine_loader가 실패 시 logger.warning으로 기록하고 레지스트리에 상태를 저장함.
from core import engine_loader as _el
from core.ros_logger import (
    get_logger as _get_logger,
    StructuredLogger as _SL,
)  # noqa: F401 (re-export)

_wlog = _get_logger("core.worker")


# 하위 호환 래퍼 — 기존 호출부 코드 변경 없이 engine_loader 위임
def _get_security_layer():
    return _el.get_security_layer()


def _get_cache_engine():
    return _el.get_cache_engine()


def _get_incremental_engine():
    return _el.get_incremental_engine()


def _get_memory_trust_engine():
    return _el.get_memory_trust_engine()


def _get_graph_integrity_engine():
    return _el.get_graph_integrity_engine()


def _get_fault_recovery_engine():
    return _el.get_fault_recovery_engine()


def _get_resource_governor():
    return _el.get_resource_governor()


def _get_rag_engine(vault_path: str = "", cache_engine=None):
    return _el.get_rag_engine(vault_path, cache_engine)


def _get_context_compressor():
    return _el.get_context_compressor()


def _get_rag_observability():
    return _el.get_rag_observability()


def _get_evolution_engine():
    return _el.get_evolution_engine()


def _get_contradiction_engine():
    return _el.get_contradiction_engine()


def _get_lineage_engine():
    return _el.get_lineage_engine()


def _get_math_engine():
    return _el.get_math_engine()


def _get_tension_engine():
    return _el.get_tension_engine()


# ══════════════════════════════════════════════════════════════════════════════
# Main Analysis Worker
# ══════════════════════════════════════════════════════════════════════════════


class AnalysisWorker(QThread):
    """백그라운드 분석 워커 — 기존 시그널 이름 완전 호환."""

    token_received = pyqtSignal(str)  # 스트리밍 청크
    analysis_done = pyqtSignal(str)  # 최종 Markdown
    save_done = pyqtSignal(str, str)  # (save_path, topic)
    error_occurred = pyqtSignal(str)  # 오류 메시지
    status_update = pyqtSignal(str)  # 상태 메시지
    engine_update = pyqtSignal(str, dict)  # (engine_name, result_dict) — 신규

    def __init__(
        self,
        api_key,
        base_url,
        model,
        input_type,
        file_path,
        raw_text,
        metadata,
        vault_path,
        auto_save,
        topic_override,
        parent=None,
    ):
        super().__init__(parent)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.input_type = input_type
        self.file_path = file_path
        self.raw_text = raw_text
        self.metadata = metadata
        self.vault_path = vault_path
        self.auto_save = auto_save
        self.topic_override = topic_override
        self._result = ""
        self._cancel_requested = False  # B-06: 협동 취소 플래그

    def run(self):
        try:
            self._execute()
        except Exception as e:
            self.error_occurred.emit(f"Worker error: {e}\n{traceback.format_exc()}")

    def cancel(self):
        """B-06: 협동 취소 요청. 다음 체크포인트에서 분석을 중단한다."""
        self._cancel_requested = True

    def _execute(self):
        runtime = AnalysisRuntime(
            parse_input=self._parse_input,
            run_analysis=self._run_analysis,
            run_cognitive_engines=self._run_cognitive_engines,
            persist_legacy_graph=self._persist_legacy_graph,
            update_semantic_graph=self._update_semantic_graph,
            persist_analysis_cache=self._persist_analysis_cache,
            set_raw_text=self._set_raw_text,
            set_model=self._set_model,
            set_metadata=self._set_metadata,
            get_security_layer=_get_security_layer,
            get_cache_engine=_get_cache_engine,
            get_incremental_engine=_get_incremental_engine,
            get_fault_recovery_engine=_get_fault_recovery_engine,
            get_resource_governor=_get_resource_governor,
            get_rag_engine=_get_rag_engine,
            get_rag_observability=_get_rag_observability,
            get_graph_integrity_engine=_get_graph_integrity_engine,
            get_memory_trust_engine=_get_memory_trust_engine,
        )
        callbacks = AnalysisCallbacks(
            on_token=lambda text: self.token_received.emit(text),
            on_status=lambda text: self.status_update.emit(text),
            on_engine_update=lambda name, data: self.engine_update.emit(name, data),
            on_save_done=lambda path, topic: self.save_done.emit(path, topic),
            on_error=lambda message: self.error_occurred.emit(message),
            is_cancelled=lambda: self._cancel_requested,
        )
        outcome = AnalysisPipeline(runtime).run(
            input_type=self.input_type,
            raw_text=self.raw_text or "",
            metadata=self.metadata,
            file_path=self.file_path,
            llm_config=LLMConfig(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
            ),
            vault_config=VaultConfig(
                vault_path=self.vault_path,
                auto_save=self.auto_save,
            ),
            topic_override=self.topic_override,
            callbacks=callbacks,
        )
        if outcome.ok:
            self._result = outcome.value.markdown
            self.analysis_done.emit(outcome.value.markdown)
            return
        self.error_occurred.emit(outcome.error)

    def _set_model(self, model: str) -> None:
        self.model = model

    def _set_raw_text(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def _set_metadata(self, metadata: dict) -> None:
        self.metadata = dict(metadata)

    # ── 입력 파싱 ─────────────────────────────────────────────────────────────

    def _parse_input(self):
        if self.file_path:
            detected = parsers.detect_input_type(self.file_path)
            if detected == "paper" or self.file_path.endswith(".pdf"):
                return parsers.parse_pdf(self.file_path)
            elif detected == "dataset":
                return parsers.parse_dataset(self.file_path)
            elif detected == "transcript":
                return parsers.parse_transcript(self.file_path, raw_text=self.raw_text)
            elif detected == "audio":
                return parsers.parse_audio(self.file_path)
            elif detected == "code":
                return parsers.parse_code(self.file_path)
            else:
                return parsers.parse_text(self.file_path), {}
        return self.raw_text, {}

    # ── LLM 분석 라우터 ───────────────────────────────────────────────────────

    def _run_analysis(self, content, file_meta, existing_nodes, profile, rag_context=""):
        m = self.metadata
        cb = lambda t: self.token_received.emit(t)

        if self.input_type == "paper":
            return ros_engine.analyze_paper(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                title=m.get("title", file_meta.get("title", "Unknown")),
                authors=m.get("authors", file_meta.get("author", "")),
                year=m.get("year", ""),
                journal=m.get("journal", ""),
                zotero=m.get("zotero", ""),
                existing_nodes=existing_nodes,
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=cb,
                is_cancelled=lambda: self._cancel_requested,
            )
        elif self.input_type in ("transcript", "lecture", "meeting", "voice", "seminar", "podcast"):
            return ros_engine.analyze_transcript(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                source_name=m.get("title", "Untitled"),
                input_type=self.input_type,
                date=m.get("year", datetime.now().strftime("%Y-%m-%d")),
                context=m.get("context", ""),
                existing_nodes=existing_nodes,
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=cb,
                is_cancelled=lambda: self._cancel_requested,
            )
        elif self.input_type == "dataset":
            return ros_engine.analyze_dataset(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                dataset_name=m.get("title", "Unknown Dataset"),
                file_info=m.get("file_info", ""),
                context=m.get("context", ""),
                existing_nodes=existing_nodes,
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=cb,
                is_cancelled=lambda: self._cancel_requested,
            )
        elif self.input_type == "equation":
            return ros_engine.analyze_equation(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                context=m.get("context", ""),
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=cb,
                is_cancelled=lambda: self._cancel_requested,
            )
        else:
            return ros_engine.analyze_transcript(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                source_name=m.get("title", "Notes"),
                input_type="notes",
                date=m.get("year", datetime.now().strftime("%Y-%m-%d")),
                context=m.get("context", "General notes"),
                existing_nodes=existing_nodes,
                researcher_profile=profile,
                content=content,
                rag_context=rag_context,
                callback=cb,
                is_cancelled=lambda: self._cancel_requested,
            )

    # ── 5개 인지 엔진 파이프라인 ──────────────────────────────────────────────

    def _run_cognitive_engines(self, markdown: str, title: str) -> str:
        """5개 인지 엔진 순차 실행 → Markdown 섹션 추가."""
        additions = []
        wikilinks = re.findall(r"\[\[([^\]|]+)\]\]", markdown)

        # ── Engine A: Note Evolution ──────────────────────────────────────────
        self.status_update.emit("🌱 [Engine A] Note Evolution 분석 중...")
        try:
            evo = _get_evolution_engine()
            if evo:
                # 실제 API: inject_evolution_frontmatter (frontmatter에 stage 주입)
                # + register_note 로 stage 정보 획득
                record = evo.register_note(
                    title=title,
                    content=markdown,
                    wikilinks=wikilinks,
                )
                from core.note_evolution import STAGE_ICONS, NoteStage

                stage = record.current_stage
                icon = STAGE_ICONS.get(NoteStage(stage), "💭")
                badge_section = (
                    f"\n### 🌱 Note Evolution\n"
                    f"- **Stage**: `{stage}` {icon}\n"
                    f"- **Maturity Score**: `{record.maturity_score:.3f}`\n"
                    f"- **Version**: `v{record.version}`\n"
                    f"- **Note ID**: `{record.note_id}`\n"
                )
                additions.append(badge_section)
                # frontmatter에도 stage 주입
                markdown = evo.inject_evolution_frontmatter(markdown, title, wikilinks)
                self.engine_update.emit(
                    "evolution",
                    {
                        "stage": stage,
                        "score": record.maturity_score,
                        "title": title,
                    },
                )
        except Exception as e:
            self.status_update.emit(f"⚠️ Evolution: {e}")

        # ── Engine B: Contradiction Detection ────────────────────────────────
        self.status_update.emit("⚡ [Engine B] 모순 감지 중...")
        try:
            contra = _get_contradiction_engine()
            if contra:
                # 실제 API: scan_rule_based (not scan_contradictions)
                contradictions = contra.scan_rule_based(markdown, title)
                if contradictions:
                    report = contra.format_contradiction_report(title)
                    if report:
                        additions.append(report)
                    self.engine_update.emit(
                        "contradiction",
                        {
                            "count": len(contradictions),
                            "types": [c.contradiction_type for c in contradictions],
                        },
                    )
        except Exception as e:
            self.status_update.emit(f"⚠️ Contradiction: {e}")

        # ── Engine C: Idea Lineage ────────────────────────────────────────────
        self.status_update.emit("🧬 [Engine C] 아이디어 계보 추적 중...")
        try:
            lineage, TransType = _get_lineage_engine()
            if lineage and TransType:
                # C-04: 노트 자신은 부모가 될 수 없음 — 필터 후 상위 3개만
                parent_titles = [w for w in wikilinks if w != title][:3]
                transform = (
                    TransType.FORMALIZATION if self.input_type == "equation" else TransType.ORIGIN
                )
                node = lineage.register_idea(
                    title=title,
                    content=markdown[:2000],
                    parent_titles=parent_titles,
                    transform_type=transform,
                    tags=[self.input_type],
                    note_stage=(
                        "literature_note" if self.input_type == "paper" else "fleeting_note"
                    ),
                )
                section = lineage.format_lineage_markdown(title)
                if section:
                    additions.append(section)
                self.engine_update.emit(
                    "lineage",
                    {
                        "lineage_id": node.lineage_id,
                        "parents": node.parent_ids,
                    },
                )
        except Exception as e:
            self.status_update.emit(f"⚠️ Lineage: {e}")

        # ── Engine D: Math Ontology ───────────────────────────────────────────
        self.status_update.emit("📐 [Engine D] 수학 온톨로지 스캔 중...")
        try:
            math = _get_math_engine()
            if math:
                math_objects = math.scan_content(markdown, title)
                if math_objects:
                    section = math.format_math_section(math_objects)
                    if section:
                        additions.append(section)
                    dep_graph = math.build_theorem_dependency_graph(markdown)
                    if dep_graph:
                        additions.append("\n### Theorem Dependency Graph\n" + dep_graph)
                    self.engine_update.emit(
                        "math_ontology",
                        {
                            "count": len(math_objects),
                            "objects": [o.name for o in math_objects[:10]],
                        },
                    )
        except Exception as e:
            self.status_update.emit(f"⚠️ Math Ontology: {e}")

        # ── Engine E: Research Tension + Graph DB ─────────────────────────────
        self.status_update.emit("🔭 [Engine E] 연구 긴장 감지 및 그래프 통합 중...")
        try:
            tension = _get_tension_engine()
            if tension:
                math_objs = []
                contras = []
                try:
                    me = _get_math_engine()
                    if me:
                        math_objs = me.scan_content(markdown, title)
                except Exception:
                    pass
                try:
                    ce = _get_contradiction_engine()
                    if ce:
                        # scan_rule_based 사용
                        contras = ce.scan_rule_based(markdown, title)
                except Exception:
                    pass

                tension.integrate_all_engines(
                    note_title=title,
                    content=markdown,
                    wikilinks=wikilinks,
                    math_objects=math_objs,
                    contradictions=contras,
                )
                section = tension.generate_tension_report(title)
                if section:
                    additions.append(section)

                stats = tension.graph_db.get_graph_stats()
                self.engine_update.emit(
                    "tension",
                    {
                        "graph_nodes": stats["total_nodes"],
                        "graph_edges": stats["total_edges"],
                    },
                )
        except Exception as e:
            self.status_update.emit(f"⚠️ Tension: {e}")

        # ── 최종 조합 ─────────────────────────────────────────────────────────
        if additions:
            sep = "\n\n---\n\n## 🧠 ROS Cognitive Engine Output\n\n"
            return markdown.rstrip() + sep + "\n".join(additions)
        return markdown

    def _persist_legacy_graph(self, title: str, enhanced: str) -> None:
        """F-12: 레거시 개념 그래프 갱신 — 실패해도 분석 흐름은 계속된다.

        실패를 조용히 삼키되(기존 동작 유지) 상태 채널로 노출한다.
        """
        try:
            edges = ros_engine.extract_graph_edges(
                self.api_key, self.base_url, self.model, enhanced
            )
            memory.update_graph(title, "", edges)
            memory.register_concepts(
                edges.get("explicit_links", []) + edges.get("implicit_links", [])
            )
        except Exception as e:
            self.status_update.emit(f"⚠️ 레거시 그래프 갱신 실패: {e}")

    def _persist_analysis_cache(
        self,
        cache,
        incremental,
        content_hash: str,
        cache_key: str,
        content: str,
        enhanced: str,
        is_fallback: bool,
    ) -> None:
        """F-12: 캐시 저장 — B-05에 따라 폴백 결과는 캐시하지 않는다."""
        if not (cache and incremental):
            return
        if is_fallback:
            self.status_update.emit(
                "🟡 안전 모드 결과는 캐시되지 않았습니다 — API 복구 후 재분석하세요."
            )
            return
        try:
            cache.put_analysis(content_hash, self.model, enhanced)
            incremental.mark_computed(cache_key, content)
        except Exception as e:
            self.status_update.emit(f"⚠️ 캐시 저장 실패: {e}")

    def _update_semantic_graph(self, title: str, markdown: str) -> None:
        try:
            from core.knowledge_graph import get_knowledge_graph_service

            # C-02 Stage 1: 레거시 개념 그래프 → 타입드 그래프 일회성 이관.
            # 센티널 기반 멱등; 실패해도 분석 흐름에 영향 없음 (fail-isolated).
            try:
                from core.graph_migration import migrate_legacy_to_typed

                migrate_legacy_to_typed()
            except Exception:
                pass

            report = get_knowledge_graph_service().ingest_markdown(
                title=title,
                markdown=markdown,
                source_type=self.input_type,
                source_ref=self.file_path or "",
            )
            self.engine_update.emit(
                "semantic_graph",
                {
                    "nodes": report.total_nodes,
                    "edges": report.total_edges,
                    "nodes_upserted": report.nodes_upserted,
                    "edges_upserted": report.edges_upserted,
                },
            )
        except Exception as exc:
            self.status_update.emit(f"Semantic graph update failed: {exc}")

    def get_result(self) -> str:
        return self._result


# ══════════════════════════════════════════════════════════════════════════════
# Validation Worker (API 연결 테스트)
# ══════════════════════════════════════════════════════════════════════════════


class ValidationWorker(QThread):
    validation_complete = pyqtSignal(bool, str)

    def __init__(self, api_key, base_url, model, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def run(self):
        try:
            ok, msg = ros_engine.validate_api(self.api_key, self.base_url, self.model)
            self.validation_complete.emit(ok, msg)
        except Exception as e:
            self.validation_complete.emit(False, str(e))
