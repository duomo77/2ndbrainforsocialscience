"""
state_manager.py  —  ROS v7.0 Explicit State Ownership
=======================================================
철학: 글로벌 상태는 존재하지 않는다.
      모든 상태는 명시적 소유자가 있고, 변경은 추적 가능하다.

원칙:
  - 단일 진실 소스 (Single Source of Truth)
  - 불변 스냅샷 (immutable snapshots for reads)
  - 명시적 변경 로그 (every mutation is logged)
  - 캐시 무효화 규칙 명문화
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ══════════════════════════════════════════════════════════════════════════════
# STATE DOMAINS — 각 도메인은 독립적 소유권
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMState:
    """LLM 연결 상태 — config.py가 소유."""
    api_key:    str   = ""
    base_url:   str   = ""
    model:      str   = "gpt-4o-mini"
    provider:   str   = "openai"
    connected:  bool  = False
    last_tested: str  = ""


@dataclass
class VaultState:
    """볼트 상태 — obsidian_sync.py가 소유."""
    vault_path:        str   = ""
    use_topic_folders: bool  = True
    auto_save:         bool  = True
    note_count:        int   = 0
    known_nodes:       list  = field(default_factory=list)
    last_synced:       str   = ""


@dataclass
class AnalysisState:
    """현재 분석 세션 상태 — worker.py가 소유."""
    is_running:     bool  = False
    current_title:  str   = ""
    current_type:   str   = ""
    current_discipline: str = ""
    progress:       float = 0.0   # 0.0 ~ 1.0
    trace_id:       str   = ""
    started_at:     str   = ""
    result_markdown: str  = ""
    last_error:     str   = ""


@dataclass
class ResearcherState:
    """연구자 프로파일 상태 — memory.py가 소유."""
    name:       str   = ""
    discipline: str   = ""
    interests:  list  = field(default_factory=list)
    methods:    list  = field(default_factory=list)
    projects:   list  = field(default_factory=list)
    questions:  list  = field(default_factory=list)


@dataclass
class UIState:
    """UI 상태 — main_window.py가 소유."""
    focus_mode:         bool  = False
    current_tab:        str   = "paper"
    infra_panel_open:   bool  = False
    monetization_shown: bool  = False
    last_activity_ts:   float = field(default_factory=time.time)

    def is_idle(self, threshold_seconds: float = 120.0) -> bool:
        return (time.time() - self.last_activity_ts) > threshold_seconds

    def touch(self) -> None:
        self.last_activity_ts = time.time()


# ══════════════════════════════════════════════════════════════════════════════
# MUTATION LOG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MutationRecord:
    domain:    str
    field:     str
    old_value: Any
    new_value: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source:    str = ""


# ══════════════════════════════════════════════════════════════════════════════
# STATE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class StateManager:
    """
    ROS v7.0 중앙 상태 관리자.

    소유권 규칙:
      - LLMState     → config.py / settings_dialog.py
      - VaultState   → obsidian_sync.py
      - AnalysisState → worker.py
      - ResearcherState → memory.py
      - UIState      → main_window.py

    변경 규칙:
      - update_*() 메서드를 통해서만 상태 변경
      - 모든 변경은 MutationRecord에 기록
      - 구독자(subscriber)에게 변경 사실 알림
    """

    def __init__(self):
        self._llm       = LLMState()
        self._vault     = VaultState()
        self._analysis  = AnalysisState()
        self._researcher = ResearcherState()
        self._ui        = UIState()
        self._mutations: list[MutationRecord] = []
        self._subscribers: dict[str, list[Callable]] = {
            "llm": [], "vault": [], "analysis": [],
            "researcher": [], "ui": [],
        }
        self._lock = threading.RLock()

    # ── 읽기 (불변 스냅샷) ───────────────────────────────────────────────────

    @property
    def llm(self) -> LLMState:
        with self._lock: return deepcopy(self._llm)

    @property
    def vault(self) -> VaultState:
        with self._lock: return deepcopy(self._vault)

    @property
    def analysis(self) -> AnalysisState:
        with self._lock: return deepcopy(self._analysis)

    @property
    def researcher(self) -> ResearcherState:
        with self._lock: return deepcopy(self._researcher)

    @property
    def ui(self) -> UIState:
        with self._lock: return deepcopy(self._ui)

    # ── 쓰기 (명시적 변경) ───────────────────────────────────────────────────

    def update_llm(self, **kwargs) -> None:
        self._update_domain("llm", self._llm, kwargs)

    def update_vault(self, **kwargs) -> None:
        self._update_domain("vault", self._vault, kwargs)

    def update_analysis(self, **kwargs) -> None:
        self._update_domain("analysis", self._analysis, kwargs)

    def update_researcher(self, **kwargs) -> None:
        self._update_domain("researcher", self._researcher, kwargs)

    def update_ui(self, **kwargs) -> None:
        self._update_domain("ui", self._ui, kwargs)

    def _update_domain(self, domain: str, state_obj: Any, updates: dict) -> None:
        with self._lock:
            records: list[MutationRecord] = []
            for field_name, new_val in updates.items():
                if not hasattr(state_obj, field_name):
                    continue
                old_val = getattr(state_obj, field_name)
                if old_val != new_val:
                    setattr(state_obj, field_name, new_val)
                    records.append(MutationRecord(
                        domain=domain, field=field_name,
                        old_value=old_val, new_value=new_val,
                    ))
            self._mutations.extend(records)
            # 최근 500개만 유지
            if len(self._mutations) > 500:
                self._mutations = self._mutations[-500:]

        # 구독자 알림 (락 밖에서)
        if records:
            for cb in self._subscribers.get(domain, []):
                try: cb(domain, records)
                except Exception: pass

    # ── 구독 ─────────────────────────────────────────────────────────────────

    def subscribe(self, domain: str, callback: Callable) -> None:
        """상태 변경 구독. callback(domain, records) 형태로 호출됨."""
        if domain in self._subscribers:
            self._subscribers[domain].append(callback)

    def unsubscribe(self, domain: str, callback: Callable) -> None:
        if domain in self._subscribers:
            try: self._subscribers[domain].remove(callback)
            except ValueError: pass

    # ── 캐시 무효화 규칙 ─────────────────────────────────────────────────────

    def invalidate_analysis_cache_if_needed(self, changed_domain: str) -> bool:
        """
        캐시 무효화 규칙:
          - LLM 설정 변경 → 분석 캐시 무효화
          - 볼트 경로 변경 → 노드 캐시 무효화
        """
        if changed_domain == "llm":
            self.update_analysis(result_markdown="", last_error="")
            return True
        return False

    # ── 진단 ─────────────────────────────────────────────────────────────────

    def get_mutation_log(self, n: int = 20) -> list[MutationRecord]:
        with self._lock:
            return list(self._mutations)[-n:]

    def snapshot(self) -> dict:
        return {
            "llm":        {"model": self._llm.model, "connected": self._llm.connected},
            "vault":      {"path": self._vault.vault_path, "notes": self._vault.note_count},
            "analysis":   {"running": self._analysis.is_running, "title": self._analysis.current_title},
            "researcher": {"name": self._researcher.name, "discipline": self._researcher.discipline},
            "ui":         {"focus_mode": self._ui.focus_mode, "tab": self._ui.current_tab},
            "mutations":  len(self._mutations),
        }


# ── 모듈 레벨 싱글톤 ──────────────────────────────────────────────────────────
_state: Optional[StateManager] = None

def get_state() -> StateManager:
    global _state
    if _state is None:
        _state = StateManager()
    return _state
