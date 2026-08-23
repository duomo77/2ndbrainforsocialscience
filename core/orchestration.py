"""
orchestration.py — ROS v4.0 Async Queue + Resource Governance
==============================================================
Two subsystems:

  A. Queue Orchestration Engine
     - Priority queue for analysis tasks
     - Checkpoint/resume support
     - Fault recovery
     - Parallel semantic analysis (thread pool)
     - Non-blocking graph updates

  B. Resource Governance Engine
     - RAM/VRAM monitoring
     - Token consumption tracking
     - Queue pressure monitoring
     - Auto model downgrade under pressure
     - Inference throttling
"""

from __future__ import annotations

import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional

logger = _get_logger("ROS.Orchestration")

# ══════════════════════════════════════════════════════════════════════════════
# B. RESOURCE GOVERNANCE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# 모델 다운그레이드 체인 (압박 시 자동 전환)
MODEL_DOWNGRADE_CHAIN = {
    "gpt-4o":          "gpt-4o-mini",
    "gpt-4.1":         "gpt-4.1-mini",
    "gpt-4.1-mini":    "gpt-4.1-nano",
    "deepseek-v3":     "deepseek-chat",
    "qwen-max":        "qwen-plus",
    "qwen-plus":       "qwen3-4b",
    "glm-4-plus":      "glm-4-flash",
    "moonshot-v1-128k": "moonshot-v1-8k",
}

@dataclass
class ResourceSnapshot:
    timestamp:      str
    ram_used_mb:    float
    ram_total_mb:   float
    ram_percent:    float
    cpu_percent:    float
    queue_pressure: int    # 대기 중인 태스크 수
    token_rate:     float  # 분당 토큰 소비

class ResourceGovernor:
    """
    시스템 리소스 모니터링 및 자동 거버넌스.
    압박 시 모델 다운그레이드, 추론 스로틀링.
    """

    RAM_WARNING_PERCENT   = 75.0
    RAM_CRITICAL_PERCENT  = 90.0
    QUEUE_WARNING_SIZE    = 10
    QUEUE_CRITICAL_SIZE   = 30

    def __init__(self):
        self._snapshots:    list[ResourceSnapshot] = []
        self._token_log:    list[tuple[float, int]] = []  # (timestamp, tokens)
        self._throttle_until: float = 0.0
        self._current_model: Optional[str] = None

    def snapshot(self) -> ResourceSnapshot:
        """현재 리소스 상태 스냅샷."""
        ram_used = ram_total = ram_pct = cpu_pct = 0.0
        try:
            import psutil
            vm = psutil.virtual_memory()
            ram_used  = vm.used / 1024 / 1024
            ram_total = vm.total / 1024 / 1024
            ram_pct   = vm.percent
            cpu_pct   = psutil.cpu_percent(interval=0.1)
        except ImportError:
            # psutil 없을 때 기본값
            ram_used = ram_total = 0.0
            ram_pct  = 0.0
            cpu_pct  = 0.0

        snap = ResourceSnapshot(
            timestamp    = datetime.now(UTC).isoformat(),
            ram_used_mb  = round(ram_used, 1),
            ram_total_mb = round(ram_total, 1),
            ram_percent  = round(ram_pct, 1),
            cpu_percent  = round(cpu_pct, 1),
            queue_pressure = 0,
            token_rate   = self._compute_token_rate(),
        )
        self._snapshots.append(snap)
        if len(self._snapshots) > 100:
            self._snapshots = self._snapshots[-100:]
        return snap

    def _compute_token_rate(self) -> float:
        """분당 토큰 소비율 계산."""
        now = time.time()
        recent = [(ts, tok) for ts, tok in self._token_log if now - ts < 60]
        self._token_log = recent
        return sum(tok for _, tok in recent)

    def log_tokens(self, count: int):
        self._token_log.append((time.time(), count))

    def assess_pressure(self, queue_size: int = 0) -> str:
        """리소스 압박 수준 평가: 'normal' | 'warning' | 'critical'."""
        snap = self.snapshot()
        snap.queue_pressure = queue_size

        if (snap.ram_percent >= self.RAM_CRITICAL_PERCENT or
                queue_size >= self.QUEUE_CRITICAL_SIZE):
            return "critical"
        elif (snap.ram_percent >= self.RAM_WARNING_PERCENT or
              queue_size >= self.QUEUE_WARNING_SIZE):
            return "warning"
        return "normal"

    def get_recommended_model(self, preferred_model: str, queue_size: int = 0) -> str:
        """압박 수준에 따라 추천 모델 반환 (자동 다운그레이드)."""
        pressure = self.assess_pressure(queue_size)
        if pressure == "critical":
            # 2단계 다운그레이드
            m = MODEL_DOWNGRADE_CHAIN.get(preferred_model, preferred_model)
            m = MODEL_DOWNGRADE_CHAIN.get(m, m)
            if m != preferred_model:
                logger.warning(f"Critical pressure: downgrading {preferred_model} → {m}")
            return m
        elif pressure == "warning":
            # 1단계 다운그레이드
            m = MODEL_DOWNGRADE_CHAIN.get(preferred_model, preferred_model)
            if m != preferred_model:
                logger.info(f"Warning pressure: downgrading {preferred_model} → {m}")
            return m
        return preferred_model

    def should_throttle(self) -> bool:
        """추론 스로틀링 여부."""
        if time.time() < self._throttle_until:
            return True
        snap = self.snapshot()
        if snap.ram_percent >= self.RAM_CRITICAL_PERCENT:
            self._throttle_until = time.time() + 5.0  # 5초 대기
            return True
        return False

    def get_stats(self) -> dict:
        if not self._snapshots:
            return {}
        latest = self._snapshots[-1]
        return {
            "ram_percent":   latest.ram_percent,
            "ram_used_mb":   latest.ram_used_mb,
            "cpu_percent":   latest.cpu_percent,
            "token_rate_pm": latest.token_rate,
            "pressure":      self.assess_pressure(),
        }

# ══════════════════════════════════════════════════════════════════════════════
# Singleton Access
# ══════════════════════════════════════════════════════════════════════════════

_governor:     Optional[ResourceGovernor]  = None

def get_resource_governor() -> ResourceGovernor:
    global _governor
    if _governor is None:
        _governor = ResourceGovernor()
    return _governor
