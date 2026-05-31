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
import os
import platform
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = _get_logger("ROS.Orchestration")


# ══════════════════════════════════════════════════════════════════════════════
# A. QUEUE ORCHESTRATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TaskPriority(Enum):
    CRITICAL  = 0   # 즉시 처리 (사용자 대기 중)
    HIGH      = 1   # 활성 연구 컨텍스트
    NORMAL    = 2   # 일반 분석
    LOW       = 3   # 백그라운드 인덱싱
    IDLE      = 4   # 유휴 시간 처리


class TaskStatus(Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    RETRYING   = "retrying"
    CANCELLED  = "cancelled"


@dataclass
class AnalysisTask:
    task_id:     str
    priority:    int           # TaskPriority.value
    task_type:   str           # paper | transcript | dataset | equation | notes
    payload:     dict          # 분석에 필요한 모든 파라미터
    status:      str = TaskStatus.PENDING.value
    created_at:  str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at:  Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    checkpoint:  Optional[dict] = None   # 재개 지점
    result:      Optional[str] = None
    error:       Optional[str] = None
    progress:    float = 0.0             # 0.0 ~ 1.0

    def __lt__(self, other):
        return self.priority < other.priority


class TaskQueue:
    """우선순위 기반 태스크 큐."""

    def __init__(self):
        self._q: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: dict[str, AnalysisTask] = {}
        self._lock = threading.Lock()

    def enqueue(self, task: AnalysisTask) -> str:
        with self._lock:
            self._tasks[task.task_id] = task
            self._q.put((task.priority, time.time(), task.task_id))
        logger.info(f"Task enqueued: {task.task_id} (priority={task.priority})")
        return task.task_id

    def dequeue(self, timeout: float = 1.0) -> Optional[AnalysisTask]:
        try:
            _, _, task_id = self._q.get(timeout=timeout)
            with self._lock:
                task = self._tasks.get(task_id)
                if task and task.status == TaskStatus.PENDING.value:
                    task.status     = TaskStatus.RUNNING.value
                    task.started_at = datetime.utcnow().isoformat()
                    return task
        except queue.Empty:
            pass
        return None

    def update(self, task: AnalysisTask):
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[AnalysisTask]:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING.value:
                task.status = TaskStatus.CANCELLED.value
                return True
        return False

    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING.value)

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING.value)

    def stats(self) -> dict:
        counts = {}
        for s in TaskStatus:
            counts[s.value] = sum(1 for t in self._tasks.values() if t.status == s.value)
        return counts


class QueueOrchestrator:
    """
    비동기 큐 오케스트레이터.
    백그라운드 스레드 풀로 태스크 처리.
    """

    def __init__(self, max_workers: int = 2):
        self.task_queue  = TaskQueue()
        self._max_workers = max_workers
        self._workers:   list[threading.Thread] = []
        self._running    = False
        self._handlers:  dict[str, Callable] = {}
        self._callbacks: dict[str, list[Callable]] = {}

    def register_handler(self, task_type: str, handler: Callable):
        """태스크 타입별 핸들러 등록."""
        self._handlers[task_type] = handler

    def on_complete(self, task_id: str, callback: Callable):
        """태스크 완료 콜백 등록."""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)

    def submit(
        self,
        task_type:  str,
        payload:    dict,
        priority:   TaskPriority = TaskPriority.NORMAL,
        task_id:    Optional[str] = None,
    ) -> str:
        import hashlib
        if task_id is None:
            task_id = hashlib.sha256(
                f"{task_type}{time.time()}".encode()
            ).hexdigest()[:12]

        task = AnalysisTask(
            task_id  = task_id,
            priority = priority.value,
            task_type = task_type,
            payload  = payload,
        )
        return self.task_queue.enqueue(task)

    def start(self):
        """워커 스레드 시작."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"ROS-Worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        logger.info(f"QueueOrchestrator started ({self._max_workers} workers)")

    def stop(self):
        self._running = False

    def _worker_loop(self):
        while self._running:
            task = self.task_queue.dequeue(timeout=0.5)
            if task is None:
                continue
            self._process_task(task)

    def _process_task(self, task: AnalysisTask):
        handler = self._handlers.get(task.task_type)
        if not handler:
            task.status = TaskStatus.FAILED.value
            task.error  = f"No handler for task type: {task.task_type}"
            self.task_queue.update(task)
            return

        try:
            task.progress = 0.1
            self.task_queue.update(task)

            # 체크포인트 복원
            if task.checkpoint:
                result = handler(task.payload, checkpoint=task.checkpoint)
            else:
                result = handler(task.payload)

            task.status       = TaskStatus.COMPLETED.value
            task.result       = result
            task.completed_at = datetime.utcnow().isoformat()
            task.progress     = 1.0
            self.task_queue.update(task)

            # 완료 콜백
            for cb in self._callbacks.get(task.task_id, []):
                try:
                    cb(task)
                except Exception:
                    pass

        except Exception as e:
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING.value
                task.error  = str(e)
                self.task_queue.update(task)
                # 재시도 큐에 다시 넣기
                time.sleep(2 ** task.retry_count)  # 지수 백오프
                task.status = TaskStatus.PENDING.value
                self.task_queue._q.put((task.priority, time.time(), task.task_id))
            else:
                task.status = TaskStatus.FAILED.value
                task.error  = str(e)
                self.task_queue.update(task)
                logger.error(f"Task {task.task_id} failed after {task.retry_count} retries: {e}")

    def get_stats(self) -> dict:
        return {
            "queue": self.task_queue.stats(),
            "workers": len(self._workers),
            "running": self._running,
        }


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
            timestamp    = datetime.utcnow().isoformat(),
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

_orchestrator: Optional[QueueOrchestrator] = None
_governor:     Optional[ResourceGovernor]  = None


def get_orchestrator() -> QueueOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = QueueOrchestrator()
        _orchestrator.start()
    return _orchestrator


def get_resource_governor() -> ResourceGovernor:
    global _governor
    if _governor is None:
        _governor = ResourceGovernor()
    return _governor
