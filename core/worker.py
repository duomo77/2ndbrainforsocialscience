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
from core.constants import (
    MAX_EXISTING_NODES_IN_PROMPT,
    MAX_NODE_NAME_LENGTH,
    MAX_WIKILINKS_PER_NOTE,
)
from core.utils.markdown_utils import extract_wikilink_targets
from core.utils.text_utils import rank_concept_nodes


# ── v8.0 엔진 로더 (중앙화, 구조화 로깅, BUG-4 수정) ────────────────────────
# 기존 _get_xxx() 헬퍼는 오류를 silent하게 None으로 반환했음.
# engine_loader가 실패 시 logger.warning으로 기록하고 레지스트리에 상태를 저장함.
from core import engine_loader as _el
from core.ros_logger import get_logger as _get_logger, StructuredLogger as _SL  # noqa: F401 (re-export)

_wlog = _get_logger("core.worker")

# 하위 호환 래퍼 — 기존 호출부 코드 변경 없이 engine_loader 위임
def _get_security_layer():         return _el.get_security_layer()
def _get_cache_engine():            return _el.get_cache_engine()
def _get_incremental_engine():      return _el.get_incremental_engine()
def _get_memory_trust_engine():     return _el.get_memory_trust_engine()
def _get_graph_integrity_engine():  return _el.get_graph_integrity_engine()
def _get_fault_recovery_engine():   return _el.get_fault_recovery_engine()
def _get_resource_governor():       return _el.get_resource_governor()
def _get_rag_engine(vault_path: str = "", cache_engine=None):
    return _el.get_rag_engine(vault_path, cache_engine)
def _get_context_compressor():      return _el.get_context_compressor()
def _get_rag_observability():       return _el.get_rag_observability()
def _get_evolution_engine():        return _el.get_evolution_engine()
def _get_contradiction_engine():    return _el.get_contradiction_engine()
def _get_lineage_engine():          return _el.get_lineage_engine()
def _get_math_engine():             return _el.get_math_engine()
def _get_tension_engine():          return _el.get_tension_engine()


# ══════════════════════════════════════════════════════════════════════════════
# Main Analysis Worker
# ══════════════════════════════════════════════════════════════════════════════

class AnalysisWorker(QThread):
    """백그라운드 분석 워커 — 기존 시그널 이름 완전 호환."""

    token_received  = pyqtSignal(str)       # 스트리밍 청크
    analysis_done   = pyqtSignal(str)       # 최종 Markdown
    save_done       = pyqtSignal(str, str)  # (save_path, topic)
    error_occurred  = pyqtSignal(str)       # 오류 메시지
    status_update   = pyqtSignal(str)       # 상태 메시지
    engine_update   = pyqtSignal(str, dict) # (engine_name, result_dict) — 신규

    def __init__(
        self,
        api_key, base_url, model,
        input_type, file_path, raw_text,
        metadata, vault_path, auto_save, topic_override,
        parent=None,
    ):
        super().__init__(parent)
        self.api_key        = api_key
        self.base_url       = base_url
        self.model          = model
        self.input_type     = input_type
        self.file_path      = file_path
        self.raw_text       = raw_text
        self.metadata       = metadata
        self.vault_path     = vault_path
        self.auto_save      = auto_save
        self.topic_override = topic_override
        self._result        = ""
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
        import hashlib

        # ── 0. 보안 검증 (v4.0, fail-closed — X-02 수정) ────────────────────────
        self.status_update.emit("🔒 보안 검증 중...")
        sec = _get_security_layer()
        if not sec:
            self.error_occurred.emit("🔒 보안 엔진을 불러올 수 없어 분석을 중단합니다.")
            return
        try:
            result = sec.validate_input(self.raw_text or "", self.input_type)
        except Exception as e:
            # fail-closed: 검증 중 오류 시 절대 원본 입력으로 진행하지 않음
            self.error_occurred.emit(f"🔒 보안 검증 오류로 분석을 중단합니다: {e}")
            return
        if not result.is_safe:
            threats = "; ".join(t.description for t in result.threats)
            self.error_occurred.emit(f"⚠️ 보안 검증 실패: {threats}")
            return
        if self.raw_text:
            self.raw_text = result.sanitized_content
        self.engine_update.emit("security", {"trust_score": result.trust_score})
        if self._cancel_requested:
            self.error_occurred.emit("⏹ 사용자 요청으로 분석을 취소했습니다.")
            return

        # ── 1. 입력 파싱 ──────────────────────────────────────────────────────
        self.status_update.emit("📂 입력 파싱 중...")
        content, file_meta = self._parse_input()
        # B-14: 파싱 오류는 콘텐츠가 아니라 신호로 처리 — 절대 LLM에 보내지 않음
        if file_meta.get("parse_error"):
            self.error_occurred.emit(f"파싱 실패: {file_meta['parse_error']}")
            return
        if not content:
            self.error_occurred.emit("분석할 내용이 없습니다. 텍스트 또는 파일을 입력하세요.")
            return
        if file_meta.get("requires_transcription"):
            self.error_occurred.emit(content)
            return

        # ── 1.1 파일 파생 콘텐츠 보안 검증 (X-02: 파싱 후 게이트 통과) ─────────
        if self.file_path:
            try:
                file_result = sec.validate_input(content, f"{self.input_type}:file")
            except Exception as e:
                self.error_occurred.emit(f"🔒 파일 보안 검증 오류로 분석을 중단합니다: {e}")
                return
            if not file_result.is_safe:
                threats = "; ".join(t.description for t in file_result.threats)
                self.error_occurred.emit(f"⚠️ 보안 검증 실패 (파일 콘텐츠): {threats}")
                return
            content = file_result.sanitized_content
            # 파일 메타데이터는 신뢰할 수 없음 — 그래프/볼트 식별자로 쓰기 전 무해화
            for meta_key in ("title", "author", "subject"):
                if file_meta.get(meta_key):
                    file_meta[meta_key] = sec.validate_title(str(file_meta[meta_key]))

        if self._cancel_requested:
            self.error_occurred.emit("⏹ 사용자 요청으로 분석을 취소했습니다.")
            return

        # ── 1.5 캐시 확인 (v4.0) ─────────────────────────────────────────────
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        cache = _get_cache_engine()
        incremental = _get_incremental_engine()
        cache_key = f"{self.input_type}:{self.metadata.get('title', '')}"
        if cache and incremental and not incremental.needs_recompute(cache_key, content):
            cached_result = cache.get_analysis(content_hash, self.model)
            if cached_result:
                self.status_update.emit("⚡ 캐시에서 복원됨")
                self.analysis_done.emit(cached_result)
                return

        # ── 1.6 리소스 거버넌스 (v4.0) ───────────────────────────────────────
        governor = _get_resource_governor()
        if governor:
            try:
                recommended = governor.get_recommended_model(self.model)
                if recommended != self.model:
                    self.status_update.emit(f"⚡ 리소스 압박: 모델 {self.model} → {recommended}")
                    self.model = recommended
            except Exception:
                pass

        # ── 1.7 RAG 컨텍스트 준비 (v5.0 Cheapest-Cognition-First) ────────────
        self.status_update.emit("🔍 RAG 컨텍스트 최적화 중...")
        rag_context = ""
        rag_plan = None
        try:
            rag = _get_rag_engine(self.vault_path or "", cache)
            if rag:
                rag_context, rag_plan = rag.prepare_context(
                    query       = f"{self.metadata.get('title','')} {self.input_type}",
                    model       = self.model,
                    force_llm   = False,
                    hot_only    = False,
                )
                # RAG 관측성 기록
                obs = _get_rag_observability()
                if obs and rag_plan:
                    import hashlib as _hl
                    obs.record_retrieval(
                        query_hash        = _hl.md5(self.metadata.get('title','').encode()).hexdigest()[:8],
                        tokens_used       = rag_plan.total_tokens,
                        tokens_saved      = 0,
                        latency_ms        = 0.0,
                        candidates_total  = len(rag_plan.candidates),
                        candidates_selected = len(rag_plan.selected),
                        path              = rag_plan.cognition_path,
                    )
                    self.engine_update.emit("rag", rag.get_metrics_dict())
                if rag_plan and rag_plan.cache_hit:
                    self.status_update.emit("⚡ RAG: 캐시 히트 — LLM 호출 절약")
                elif rag_context:
                    self.status_update.emit(f"✅ RAG: {len(rag_plan.selected if rag_plan else [])}개 노트 검색 완료")
        except Exception as _rag_err:
            self.status_update.emit(f"⚠️ RAG 준비 오류 (무시): {_rag_err}")

        # ── 2. 기존 볼트 스캔 ─────────────────────────────────────────────────
        existing_nodes = memory.get_concept_list()
        if self.vault_path and Path(self.vault_path).exists():
            try:
                vault_concepts = obsidian_sync.scan_vault_concepts(self.vault_path)
                existing_nodes = list(set(existing_nodes + vault_concepts))
            except Exception:
                pass
        # C-14: prevent context flooding — rank by content relevance, then cap
        existing_nodes = rank_concept_nodes(existing_nodes, content, MAX_EXISTING_NODES_IN_PROMPT)

        profile = memory.load_profile()

        # ── 3. LLM 분석 (장애 복구 포함, v4.0) ──────────────────────────────
        self.status_update.emit(f"🤖 LLM 분석 중 ({self.model})...")
        recovery = _get_fault_recovery_engine()
        if recovery:
            # F-11: 차단기 키는 원시 URL이 아니라 감지된 프로바이더 이름
            provider = ros_engine._detect_provider(self.base_url or "", self.model or "")
            def _llm_call():
                return self._run_analysis(content, file_meta, existing_nodes, profile, rag_context)
            def _safe_fallback():
                from core.fault_recovery import SafeMode
                sm = SafeMode()
                note = sm.generate_fallback_note(
                    title       = self.metadata.get("title", "Untitled"),
                    content     = content,
                    input_type  = self.input_type,
                    error_reason = "LLM API 연결 실패",
                    year        = int(self.metadata.get("year", 0) or 0),
                )
                self.status_update.emit("🟡 안전 모드 활성화 — API 재연결 후 재분석 필요")
                return note
            result, is_fallback = recovery.execute_with_recovery(
                provider    = provider,
                func        = _llm_call,
                fallback    = _safe_fallback,
                max_retries = 3,
            )
        else:
            result = self._run_analysis(content, file_meta, existing_nodes, profile, rag_context)
            is_fallback = False

        if not result:
            self.error_occurred.emit("LLM이 빈 결과를 반환했습니다. API 키와 모델을 확인하세요.")
            return
        self._result = result

        # ── 3.5 LLM 출력 검증 경계 (B-04) ────────────────────────────────────
        # 모델 출력은 그래프/메모리/볼트 어떤 변형보다 먼저 게이트를 통과해야 함.
        try:
            out_result = sec.validate_llm_output(result)
        except Exception as e:
            self.error_occurred.emit(f"🔒 LLM 출력 검증 오류로 분석을 중단합니다: {e}")
            return
        if not out_result.is_safe:
            threats = "; ".join(t.description for t in out_result.threats)
            self.error_occurred.emit(f"⚠️ LLM 출력이 보안 검증을 통과하지 못해 저장하지 않습니다: {threats}")
            return
        result = out_result.sanitized_content
        self._result = result

        if self._cancel_requested:
            self.error_occurred.emit("⏹ 사용자 요청으로 분석을 취소했습니다.")
            return

        # ── 4. 인지 엔진 파이프라인 (5개 엔진) ───────────────────────────────
        title = self.metadata.get("title", file_meta.get("title", "Untitled"))
        enhanced = self._run_cognitive_engines(result, title)

        if self._cancel_requested:
            self.error_occurred.emit("⏹ 사용자 요청으로 분석을 취소했습니다.")
            return

        # ── 5. 지식 그래프 업데이트 (트랜잭션, v4.0) ─────────────────────────
        self.status_update.emit("🔗 지식 그래프 업데이트 중...")
        self._persist_legacy_graph(title, enhanced)

        # 그래프 무결성 트랜잭션 (v4.0)
        # Write the typed graph alongside the legacy graph during migration.
        # Analysis remains available if graph persistence fails, while the
        # failure is surfaced through the worker status channel.
        self._update_semantic_graph(title, enhanced)

        graph_engine = _get_graph_integrity_engine()
        if graph_engine:
            try:
                graph_engine.begin_transaction()
                graph_engine.add_node(title, self.input_type, trust_score=0.9)
                wikilinks_found = extract_wikilink_targets(enhanced)
                # B-04: 출력 측 홍수 제한 — 링크 수와 노드 이름 길이에 상한 적용
                bounded_links = sorted(
                    link for link in set(wikilinks_found)
                    if link != title and len(link) <= MAX_NODE_NAME_LENGTH
                )[:MAX_WIKILINKS_PER_NOTE]
                for link in bounded_links:
                    graph_engine.add_node(link, "concept", trust_score=0.7)
                    graph_engine.add_edge(title, link, "references", confidence=0.8)
                ok, msg = graph_engine.commit_transaction()
                stats = graph_engine.get_stats()
                self.engine_update.emit("graph_integrity", {
                    "nodes": stats["nodes"],
                    "edges": stats["edges"],
                    "ok":    ok,
                })
            except Exception as e:
                self.status_update.emit(f"⚠️ Graph Integrity: {e}")

        # 메모리 신뢰 저장 (v4.0)
        mem_trust = _get_memory_trust_engine()
        if mem_trust:
            try:
                # C-09 수정: 저장되는 내용은 사용자 문서가 아니라 LLM 생성물이므로
                # 출처 유형을 입력 유형이 아닌 "llm_output"(기본 신뢰 0.45)으로 기록.
                mem_trust.store_memory(
                    content     = enhanced[:1000],
                    source      = title,
                    source_type = "llm_output",
                    tags        = [self.input_type, self.metadata.get("journal", "")],
                )
            except Exception:
                pass

        # 캐시 저장 (v4.0) — B-05: SafeMode 폴백은 절대 캐시하지 않음
        self._persist_analysis_cache(
            cache, incremental, content_hash, cache_key, content, enhanced, is_fallback
        )

        # ── 6. Obsidian 저장 ──────────────────────────────────────────────────
        if self.auto_save and self.vault_path:
            self.status_update.emit("💾 Obsidian 볼트에 저장 중...")
            try:
                ok, path, topic = obsidian_sync.save_note_to_vault(
                    vault_path       = self.vault_path,
                    markdown_content = enhanced,
                    title            = title,
                    input_type       = self.input_type,
                    journal          = self.metadata.get("journal", ""),
                    topic_override   = self.topic_override,
                )
                if ok:
                    memory.log_session("saved", title, self.input_type, path)
                    self.save_done.emit(path, topic)
                else:
                    self.error_occurred.emit(f"저장 실패: {path}")
            except Exception as e:
                self.error_occurred.emit(f"저장 오류: {e}")

        self.analysis_done.emit(enhanced)
        self.status_update.emit("✅ 분석 완료")

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
        m  = self.metadata
        cb = lambda t: self.token_received.emit(t)

        if self.input_type == "paper":
            return ros_engine.analyze_paper(
                api_key=self.api_key, base_url=self.base_url, model=self.model,
                title   = m.get("title", file_meta.get("title", "Unknown")),
                authors = m.get("authors", file_meta.get("author", "")),
                year    = m.get("year", ""),
                journal = m.get("journal", ""),
                zotero  = m.get("zotero", ""),
                existing_nodes     = existing_nodes,
                researcher_profile = profile,
                content  = content,
                rag_context = rag_context,
                callback = cb,
                is_cancelled = lambda: self._cancel_requested,
            )
        elif self.input_type in ("transcript", "lecture", "meeting", "voice", "seminar", "podcast"):
            return ros_engine.analyze_transcript(
                api_key=self.api_key, base_url=self.base_url, model=self.model,
                source_name = m.get("title", "Untitled"),
                input_type  = self.input_type,
                date        = m.get("year", datetime.now().strftime("%Y-%m-%d")),
                context     = m.get("context", ""),
                existing_nodes     = existing_nodes,
                researcher_profile = profile,
                content  = content,
                rag_context = rag_context,
                callback = cb,
                is_cancelled = lambda: self._cancel_requested,
            )
        elif self.input_type == "dataset":
            return ros_engine.analyze_dataset(
                api_key=self.api_key, base_url=self.base_url, model=self.model,
                dataset_name = m.get("title", "Unknown Dataset"),
                file_info    = m.get("file_info", ""),
                context      = m.get("context", ""),
                existing_nodes     = existing_nodes,
                researcher_profile = profile,
                content  = content,
                rag_context = rag_context,
                callback = cb,
                is_cancelled = lambda: self._cancel_requested,
            )
        elif self.input_type == "equation":
            return ros_engine.analyze_equation(
                api_key=self.api_key, base_url=self.base_url, model=self.model,
                context            = m.get("context", ""),
                researcher_profile = profile,
                content  = content,
                rag_context = rag_context,
                callback = cb,
                is_cancelled = lambda: self._cancel_requested,
            )
        else:
            return ros_engine.analyze_transcript(
                api_key=self.api_key, base_url=self.base_url, model=self.model,
                source_name = m.get("title", "Notes"),
                input_type  = "notes",
                date        = m.get("year", datetime.now().strftime("%Y-%m-%d")),
                context     = m.get("context", "General notes"),
                existing_nodes     = existing_nodes,
                researcher_profile = profile,
                content  = content,
                rag_context = rag_context,
                callback = cb,
                is_cancelled = lambda: self._cancel_requested,
            )

    # ── 5개 인지 엔진 파이프라인 ──────────────────────────────────────────────

    def _run_cognitive_engines(self, markdown: str, title: str) -> str:
        """5개 인지 엔진 순차 실행 → Markdown 섹션 추가."""
        additions = []
        wikilinks = re.findall(r'\[\[([^\]|]+)\]\]', markdown)

        # ── Engine A: Note Evolution ──────────────────────────────────────────
        self.status_update.emit("🌱 [Engine A] Note Evolution 분석 중...")
        try:
            evo = _get_evolution_engine()
            if evo:
                # 실제 API: inject_evolution_frontmatter (frontmatter에 stage 주입)
                # + register_note 로 stage 정보 획득
                record = evo.register_note(
                    title    = title,
                    content  = markdown,
                    wikilinks = wikilinks,
                )
                from core.note_evolution import STAGE_ICONS, NoteStage
                stage = record.current_stage
                icon  = STAGE_ICONS.get(NoteStage(stage), "💭")
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
                self.engine_update.emit("evolution", {
                    "stage": stage,
                    "score": record.maturity_score,
                    "title": title,
                })
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
                    self.engine_update.emit("contradiction", {
                        "count": len(contradictions),
                        "types": [c.contradiction_type for c in contradictions],
                    })
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
                    TransType.FORMALIZATION
                    if self.input_type == "equation"
                    else TransType.ORIGIN
                )
                node = lineage.register_idea(
                    title          = title,
                    content        = markdown[:2000],
                    parent_titles  = parent_titles,
                    transform_type = transform,
                    tags           = [self.input_type],
                    note_stage     = (
                        "literature_note" if self.input_type == "paper"
                        else "fleeting_note"
                    ),
                )
                section = lineage.format_lineage_markdown(title)
                if section:
                    additions.append(section)
                self.engine_update.emit("lineage", {
                    "lineage_id": node.lineage_id,
                    "parents":    node.parent_ids,
                })
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
                    self.engine_update.emit("math_ontology", {
                        "count":   len(math_objects),
                        "objects": [o.name for o in math_objects[:10]],
                    })
        except Exception as e:
            self.status_update.emit(f"⚠️ Math Ontology: {e}")

        # ── Engine E: Research Tension + Graph DB ─────────────────────────────
        self.status_update.emit("🔭 [Engine E] 연구 긴장 감지 및 그래프 통합 중...")
        try:
            tension = _get_tension_engine()
            if tension:
                math_objs = []
                contras   = []
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
                    note_title     = title,
                    content        = markdown,
                    wikilinks      = wikilinks,
                    math_objects   = math_objs,
                    contradictions = contras,
                )
                section = tension.generate_tension_report(title)
                if section:
                    additions.append(section)

                stats = tension.graph_db.get_graph_stats()
                self.engine_update.emit("tension", {
                    "graph_nodes": stats["total_nodes"],
                    "graph_edges": stats["total_edges"],
                })
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
        self, cache, incremental, content_hash: str, cache_key: str,
        content: str, enhanced: str, is_fallback: bool,
    ) -> None:
        """F-12: 캐시 저장 — B-05에 따라 폴백 결과는 캐시하지 않는다."""
        if not (cache and incremental):
            return
        if is_fallback:
            self.status_update.emit("🟡 안전 모드 결과는 캐시되지 않았습니다 — API 복구 후 재분석하세요.")
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
            self.engine_update.emit("semantic_graph", {
                "nodes": report.total_nodes,
                "edges": report.total_edges,
                "nodes_upserted": report.nodes_upserted,
                "edges_upserted": report.edges_upserted,
            })
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
        self.api_key  = api_key
        self.base_url = base_url
        self.model    = model

    def run(self):
        try:
            ok, msg = ros_engine.validate_api(self.api_key, self.base_url, self.model)
            self.validation_complete.emit(ok, msg)
        except Exception as e:
            self.validation_complete.emit(False, str(e))
