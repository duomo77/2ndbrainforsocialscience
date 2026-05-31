"""
observability.py  —  ROS v7.0 Structured Observability Infrastructure
======================================================================
철학: 시스템은 자신의 동작을 완전히 설명할 수 있어야 한다.
      로그는 디버깅 도구가 아니라 시스템 상태의 1급 시민이다.

제공:
  - 구조화 JSON 로깅 (trace_id 포함)
  - 성능 메트릭 수집 (분석 시간, 토큰 사용량, 캐시 히트율)
  - 에러 분류 및 집계
  - 실시간 상태 스냅샷
  - 경고 시스템
"""
from __future__ import annotations

import json
import time
import uuid
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════════════════════
# LOG LEVELS & CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════

class LogLevel(str, Enum):
    DEBUG   = "DEBUG"
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"
    CRITICAL = "CRITICAL"


class EventCategory(str, Enum):
    ANALYSIS    = "analysis"
    SAVE        = "save"
    CACHE       = "cache"
    SECURITY    = "security"
    PERFORMANCE = "performance"
    UI          = "ui"
    SYSTEM      = "system"
    RAG         = "rag"
    EPISTEMIC   = "epistemic"


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURED LOG ENTRY
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LogEntry:
    trace_id:   str
    timestamp:  str
    level:      str
    category:   str
    event:      str
    message:    str
    data:       dict = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error:      Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


# ══════════════════════════════════════════════════════════════════════════════
# METRICS COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnalysisMetric:
    trace_id:       str
    input_type:     str
    discipline:     str
    epistemic_mode: str
    model:          str
    duration_ms:    float
    tokens_used:    int
    cached:         bool
    success:        bool
    timestamp:      str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SystemMetrics:
    total_analyses:     int = 0
    successful:         int = 0
    failed:             int = 0
    cached_hits:        int = 0
    total_tokens:       int = 0
    avg_duration_ms:    float = 0.0
    disciplines_seen:   set = field(default_factory=set)
    models_used:        set = field(default_factory=set)
    error_counts:       dict = field(default_factory=lambda: defaultdict(int))
    last_updated:       str = ""

    def cache_hit_rate(self) -> float:
        if self.total_analyses == 0: return 0.0
        return self.cached_hits / self.total_analyses

    def success_rate(self) -> float:
        if self.total_analyses == 0: return 0.0
        return self.successful / self.total_analyses


# ══════════════════════════════════════════════════════════════════════════════
# ALERT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class AlertSeverity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    alert_id:   str
    severity:   AlertSeverity
    title:      str
    message:    str
    timestamp:  str = field(default_factory=lambda: datetime.now().isoformat())
    resolved:   bool = False


class AlertManager:
    """경고 생성 및 관리."""

    def __init__(self, max_alerts: int = 100):
        self._alerts: deque[Alert] = deque(maxlen=max_alerts)
        self._lock = threading.Lock()

    def emit(self, severity: AlertSeverity, title: str, message: str) -> Alert:
        alert = Alert(
            alert_id=str(uuid.uuid4())[:8],
            severity=severity,
            title=title,
            message=message,
        )
        with self._lock:
            self._alerts.append(alert)
        return alert

    def get_active(self) -> list[Alert]:
        with self._lock:
            return [a for a in self._alerts if not a.resolved]

    def resolve(self, alert_id: str) -> bool:
        with self._lock:
            for alert in self._alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    return True
        return False

    def get_critical_count(self) -> int:
        return sum(1 for a in self.get_active() if a.severity == AlertSeverity.CRITICAL)


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TIMER (context manager)
# ══════════════════════════════════════════════════════════════════════════════

class Timer:
    """성능 측정 컨텍스트 매니저."""

    def __init__(self, name: str = ""):
        self.name = name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000


# ══════════════════════════════════════════════════════════════════════════════
# MAIN OBSERVABILITY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ObservabilityEngine:
    """
    ROS v7.0 구조화 관측성 엔진.

    책임:
      - 구조화 JSON 로그 기록
      - 성능 메트릭 집계
      - 경고 생성
      - 시스템 상태 스냅샷 제공

    소유권: 이 클래스만이 로그 파일과 메트릭 상태를 소유한다.
    """

    def __init__(self, log_dir: Optional[str] = None):
        self._metrics = SystemMetrics()
        self._recent_logs: deque[LogEntry] = deque(maxlen=500)
        self._analysis_history: deque[AnalysisMetric] = deque(maxlen=1000)
        self._alerts = AlertManager()
        self._lock = threading.Lock()

        # 로그 파일 설정
        if log_dir:
            log_path = Path(log_dir) / "ros_v7.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = str(log_path)
        else:
            import os
            default_dir = Path.home() / ".econometric_wiki" / "logs"
            default_dir.mkdir(parents=True, exist_ok=True)
            self._log_file = str(default_dir / "ros_v7.log")

        # Python 표준 로거 설정
        self._logger = _get_logger("ROS_v7")
        if not self._logger.handlers:
            handler = logging.FileHandler(self._log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    # ── 로깅 ─────────────────────────────────────────────────────────────────

    def log(
        self,
        level: LogLevel,
        category: EventCategory,
        event: str,
        message: str,
        data: Optional[dict] = None,
        trace_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> LogEntry:
        entry = LogEntry(
            trace_id=trace_id or str(uuid.uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            level=level.value,
            category=category.value,
            event=event,
            message=message,
            data=data or {},
            duration_ms=duration_ms,
            error=error,
        )
        with self._lock:
            self._recent_logs.append(entry)
        try:
            self._logger.info(entry.to_json())
        except Exception:
            pass

        # 자동 경고 생성
        if level == LogLevel.ERROR:
            self._alerts.emit(AlertSeverity.WARNING, f"Error: {event}", message)
        elif level == LogLevel.CRITICAL:
            self._alerts.emit(AlertSeverity.CRITICAL, f"Critical: {event}", message)

        return entry

    def info(self, category: EventCategory, event: str, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.INFO, category, event, message, **kwargs)

    def warning(self, category: EventCategory, event: str, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.WARNING, category, event, message, **kwargs)

    def error(self, category: EventCategory, event: str, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.ERROR, category, event, message, **kwargs)

    # ── 메트릭 기록 ──────────────────────────────────────────────────────────

    def record_analysis(
        self,
        input_type: str,
        discipline: str,
        epistemic_mode: str,
        model: str,
        duration_ms: float,
        tokens_used: int,
        cached: bool,
        success: bool,
        trace_id: str = "",
    ) -> None:
        metric = AnalysisMetric(
            trace_id=trace_id or str(uuid.uuid4())[:8],
            input_type=input_type,
            discipline=discipline,
            epistemic_mode=epistemic_mode,
            model=model,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            cached=cached,
            success=success,
        )
        with self._lock:
            self._analysis_history.append(metric)
            m = self._metrics
            m.total_analyses += 1
            if success:   m.successful += 1
            else:         m.failed += 1
            if cached:    m.cached_hits += 1
            m.total_tokens += tokens_used
            m.disciplines_seen.add(discipline)
            m.models_used.add(model)
            # 이동 평균 업데이트
            n = m.total_analyses
            m.avg_duration_ms = (m.avg_duration_ms * (n - 1) + duration_ms) / n
            m.last_updated = datetime.now().isoformat()

        # 성능 경고
        if duration_ms > 60_000:
            self._alerts.emit(
                AlertSeverity.WARNING,
                "Slow Analysis",
                f"Analysis took {duration_ms/1000:.1f}s for {discipline}/{input_type}",
            )

    def record_error(self, error_type: str) -> None:
        with self._lock:
            self._metrics.error_counts[error_type] += 1

    # ── 스냅샷 & 리포트 ───────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """현재 시스템 상태 스냅샷 반환."""
        with self._lock:
            m = self._metrics
            recent = list(self._recent_logs)[-20:]
        return {
            "total_analyses":  m.total_analyses,
            "success_rate":    round(m.success_rate(), 3),
            "cache_hit_rate":  round(m.cache_hit_rate(), 3),
            "avg_duration_ms": round(m.avg_duration_ms, 1),
            "total_tokens":    m.total_tokens,
            "disciplines":     list(m.disciplines_seen),
            "models_used":     list(m.models_used),
            "error_counts":    dict(m.error_counts),
            "active_alerts":   len(self._alerts.get_active()),
            "critical_alerts": self._alerts.get_critical_count(),
            "last_updated":    m.last_updated,
            "recent_events":   [e.event for e in recent],
        }

    def efficiency_report(self) -> str:
        """사람이 읽을 수 있는 효율성 리포트."""
        snap = self.snapshot()
        lines = [
            "═══ ROS v7.0 Observability Report ═══",
            f"Total Analyses  : {snap['total_analyses']}",
            f"Success Rate    : {snap['success_rate']*100:.1f}%",
            f"Cache Hit Rate  : {snap['cache_hit_rate']*100:.1f}%",
            f"Avg Duration    : {snap['avg_duration_ms']:.0f}ms",
            f"Total Tokens    : {snap['total_tokens']:,}",
            f"Disciplines     : {', '.join(snap['disciplines'][:5]) or 'none'}",
            f"Models Used     : {', '.join(snap['models_used']) or 'none'}",
            f"Active Alerts   : {snap['active_alerts']} ({snap['critical_alerts']} critical)",
        ]
        if snap["error_counts"]:
            lines.append("Error Breakdown :")
            for k, v in snap["error_counts"].items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def get_recent_logs(self, n: int = 50) -> list[LogEntry]:
        with self._lock:
            return list(self._recent_logs)[-n:]

    def get_alerts(self) -> list[Alert]:
        return self._alerts.get_active()

    def new_trace_id(self) -> str:
        return str(uuid.uuid4())[:8]


# ── 모듈 레벨 싱글톤 ──────────────────────────────────────────────────────────
_obs: Optional[ObservabilityEngine] = None

def get_observability(log_dir: Optional[str] = None) -> ObservabilityEngine:
    global _obs
    if _obs is None:
        _obs = ObservabilityEngine(log_dir)
    return _obs
