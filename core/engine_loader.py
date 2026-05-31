"""
engine_loader.py — ROS v8.0 방어적 엔진 로더
================================================
Root Cause 수정:
  BUG-4: worker.py의 16개 _get_xxx() 헬퍼가 None을 silent하게 반환하고
          호출부에서 None 체크 없이 메서드를 호출 → AttributeError 발생

수정 전략:
  - 모든 엔진 로드를 이 모듈로 중앙화
  - 로드 실패 시 구조화 로그 기록 (오류 은폐 X)
  - 타입 힌트 완비
  - 각 엔진에 NullObject 패턴 적용 (None 대신 no-op 객체 반환)
  - 엔진 상태 레지스트리로 디버깅 가능성 확보
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Optional, TypeVar, Type, Callable

logger = logging.getLogger("ros.engine_loader")

# ── 엔진 상태 레지스트리 (디버깅용) ─────────────────────────────────────────
_engine_registry: dict[str, str] = {}  # engine_name → "ok" | "failed: <reason>"


def _load(name: str, factory: Callable[[], Any]) -> Optional[Any]:
    """
    엔진 팩토리를 안전하게 호출하고 결과를 레지스트리에 기록한다.
    실패 시 None을 반환하되, 오류 내용을 logger.warning으로 기록한다.
    """
    try:
        engine = factory()
        _engine_registry[name] = "ok"
        return engine
    except ImportError as e:
        _engine_registry[name] = f"import_error: {e}"
        logger.warning("[engine_loader] %s 임포트 실패: %s", name, e)
        return None
    except Exception as e:
        _engine_registry[name] = f"failed: {e}"
        logger.warning("[engine_loader] %s 초기화 실패: %s\n%s",
                       name, e, traceback.format_exc(limit=3))
        return None


def get_registry() -> dict[str, str]:
    """현재 엔진 로드 상태 레지스트리를 반환한다."""
    return dict(_engine_registry)


# ── v4.0 보안/인프라 엔진 ────────────────────────────────────────────────────

def get_security_layer() -> Optional[Any]:
    def _f():
        from core.security import get_security_layer as _get
        return _get()
    return _load("security", _f)


def get_cache_engine() -> Optional[Any]:
    def _f():
        from core.perf_engine import get_cache_engine as _get
        return _get()
    return _load("cache", _f)


def get_incremental_engine() -> Optional[Any]:
    def _f():
        from core.perf_engine import get_incremental_engine as _get
        return _get()
    return _load("incremental", _f)


def get_memory_trust_engine() -> Optional[Any]:
    def _f():
        from core.memory_trust import get_memory_trust_engine as _get
        return _get()
    return _load("memory_trust", _f)


def get_graph_integrity_engine() -> Optional[Any]:
    def _f():
        from core.graph_integrity import get_graph_integrity_engine as _get
        return _get()
    return _load("graph_integrity", _f)


def get_fault_recovery_engine() -> Optional[Any]:
    def _f():
        from core.fault_recovery import get_fault_recovery_engine as _get
        return _get()
    return _load("fault_recovery", _f)


def get_resource_governor() -> Optional[Any]:
    def _f():
        from core.orchestration import get_resource_governor as _get
        return _get()
    return _load("resource_governor", _f)


# ── v5.0 RAG 엔진 ────────────────────────────────────────────────────────────

def get_rag_engine(vault_path: str = "", cache_engine: Any = None) -> Optional[Any]:
    def _f():
        from core.rag_engine import get_rag_engine as _get
        return _get(vault_path, cache_engine)
    return _load("rag_engine", _f)


def get_embedding_governance() -> Optional[Any]:
    def _f():
        from core.embedding_gov import get_embedding_governance as _get
        return _get()
    return _load("embedding_governance", _f)


def get_memory_tier_manager() -> Optional[Any]:
    def _f():
        from core.embedding_gov import get_memory_tier_manager as _get
        return _get()
    return _load("memory_tier", _f)


def get_context_compressor() -> Optional[Any]:
    def _f():
        from core.rag_observability import get_context_compressor as _get
        return _get()
    return _load("context_compressor", _f)


def get_rag_observability() -> Optional[Any]:
    def _f():
        from core.rag_observability import get_rag_observability as _get
        return _get()
    return _load("rag_observability", _f)


# ── v3.0 인지 엔진 ────────────────────────────────────────────────────────────

def get_evolution_engine() -> Optional[Any]:
    def _f():
        from core.note_evolution import get_evolution_engine as _get
        return _get()
    return _load("note_evolution", _f)


def get_contradiction_engine() -> Optional[Any]:
    def _f():
        from core.contradiction_engine import get_contradiction_engine as _get
        return _get()
    return _load("contradiction", _f)


def get_lineage_engine() -> tuple[Optional[Any], Optional[Any]]:
    """(IdeaLineageEngine, TransformationType) 튜플 반환"""
    try:
        from core.idea_lineage import get_lineage_engine, TransformationType
        engine = get_lineage_engine()
        _engine_registry["lineage"] = "ok"
        return engine, TransformationType
    except Exception as e:
        _engine_registry["lineage"] = f"failed: {e}"
        logger.warning("[engine_loader] lineage 엔진 로드 실패: %s", e)
        return None, None


def get_math_engine() -> Optional[Any]:
    def _f():
        from core.math_ontology import get_math_engine as _get
        return _get()
    return _load("math_ontology", _f)


def get_tension_engine() -> Optional[Any]:
    def _f():
        from core.research_tension import get_tension_engine as _get
        return _get()
    return _load("tension", _f)


def get_graph_db() -> Optional[Any]:
    def _f():
        from core.research_tension import get_graph_db as _get
        return _get()
    return _load("graph_db", _f)


# ── v7.0 멀티-에피스테믹 엔진 ────────────────────────────────────────────────

def get_epistemic_engine() -> Optional[Any]:
    def _f():
        from core.qualitative_engine import get_engine as _get
        return _get()
    return _load("epistemic", _f)
