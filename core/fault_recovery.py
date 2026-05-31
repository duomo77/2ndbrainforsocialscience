"""
fault_recovery.py — ROS v4.0 Fault Recovery & Safe Mode
=========================================================
Implements:
  - Circuit breaker pattern (API failure isolation)
  - Automatic safe mode activation
  - Graceful degradation strategies
  - Recovery checkpoints
  - Error taxonomy and routing
  - Exponential backoff with jitter
"""

from __future__ import annotations

import json
import logging
try:
    from core.ros_logger import get_logger as _get_logger
except ImportError:
    _get_logger = logging.getLogger
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = _get_logger("ROS.FaultRecovery")


# ══════════════════════════════════════════════════════════════════════════════
# Error Taxonomy
# ══════════════════════════════════════════════════════════════════════════════

class ErrorCategory(Enum):
    API_AUTH        = "api_auth"         # 인증 오류 (401, 403)
    API_RATE_LIMIT  = "api_rate_limit"   # 속도 제한 (429)
    API_TIMEOUT     = "api_timeout"      # 타임아웃
    API_SERVER      = "api_server"       # 서버 오류 (500, 503)
    PARSE_ERROR     = "parse_error"      # 입력 파싱 오류
    GRAPH_CORRUPT   = "graph_corrupt"    # 그래프 무결성 오류
    MEMORY_OVERFLOW = "memory_overflow"  # 메모리 초과
    PROMPT_INJECT   = "prompt_inject"    # 프롬프트 인젝션 감지
    UNKNOWN         = "unknown"


def classify_error(error: Exception) -> ErrorCategory:
    msg = str(error).lower()
    if "401" in msg or "403" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return ErrorCategory.API_AUTH
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return ErrorCategory.API_RATE_LIMIT
    if "timeout" in msg or "timed out" in msg:
        return ErrorCategory.API_TIMEOUT
    if "500" in msg or "502" in msg or "503" in msg or "server error" in msg:
        return ErrorCategory.API_SERVER
    if "parse" in msg or "decode" in msg or "pdf" in msg:
        return ErrorCategory.PARSE_ERROR
    if "graph" in msg or "integrity" in msg:
        return ErrorCategory.GRAPH_CORRUPT
    if "memory" in msg or "oom" in msg:
        return ErrorCategory.MEMORY_OVERFLOW
    if "injection" in msg or "prompt" in msg:
        return ErrorCategory.PROMPT_INJECT
    return ErrorCategory.UNKNOWN


# ══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker
# ══════════════════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED   = "closed"    # 정상 동작
    OPEN     = "open"      # 차단 (장애 격리)
    HALF_OPEN = "half_open" # 복구 시도 중


@dataclass
class CircuitBreaker:
    """
    API 장애 격리를 위한 회로 차단기.
    연속 실패 임계값 초과 시 OPEN 상태로 전환.
    """
    name:              str
    failure_threshold: int   = 5
    recovery_timeout:  float = 60.0   # 초
    success_threshold: int   = 2      # HALF_OPEN → CLOSED 전환 필요 성공 수

    state:             str   = field(default=CircuitState.CLOSED.value)
    failure_count:     int   = 0
    success_count:     int   = 0
    last_failure_time: float = 0.0
    total_calls:       int   = 0
    total_failures:    int   = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        self.total_calls += 1

        if self.state == CircuitState.OPEN.value:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state         = CircuitState.HALF_OPEN.value
                self.success_count = 0
                logger.info(f"Circuit {self.name}: OPEN → HALF_OPEN")
            else:
                raise RuntimeError(
                    f"Circuit breaker OPEN for {self.name}. "
                    f"Retry in {self.recovery_timeout - elapsed:.0f}s"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN.value:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state         = CircuitState.CLOSED.value
                self.failure_count = 0
                logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED (recovered)")
        elif self.state == CircuitState.CLOSED.value:
            self.failure_count = 0

    def _on_failure(self, error: Exception):
        self.failure_count     += 1
        self.total_failures    += 1
        self.last_failure_time  = time.time()

        if self.state == CircuitState.HALF_OPEN.value:
            self.state = CircuitState.OPEN.value
            logger.warning(f"Circuit {self.name}: HALF_OPEN → OPEN (recovery failed)")
        elif (self.state == CircuitState.CLOSED.value and
              self.failure_count >= self.failure_threshold):
            self.state = CircuitState.OPEN.value
            logger.error(
                f"Circuit {self.name}: CLOSED → OPEN "
                f"({self.failure_count} consecutive failures)"
            )

    def is_available(self) -> bool:
        if self.state == CircuitState.OPEN.value:
            return time.time() - self.last_failure_time >= self.recovery_timeout
        return True

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════════
# Backoff Strategy
# ══════════════════════════════════════════════════════════════════════════════

def exponential_backoff_with_jitter(
    attempt:   int,
    base:      float = 1.0,
    max_wait:  float = 60.0,
    jitter:    float = 0.3,
) -> float:
    """지수 백오프 + 지터 (thundering herd 방지)."""
    wait = min(base * (2 ** attempt), max_wait)
    jitter_amount = wait * jitter * random.random()
    return wait + jitter_amount


# ══════════════════════════════════════════════════════════════════════════════
# Safe Mode
# ══════════════════════════════════════════════════════════════════════════════

class SafeMode:
    """
    안전 모드 — API 완전 장애 시 로컬 처리로 폴백.
    LLM 없이 규칙 기반 분석만 수행.
    """

    SAFE_MODE_TEMPLATE = """---
title: "{title}"
authors: []
year: {year}
tags: [safe-mode, needs-review]
status: draft
safe_mode: true
---

# {title}

> ⚠️ **Safe Mode** — LLM API 연결 불가. 규칙 기반 분석만 수행됨.
> 정상 연결 후 재분석 필요.

## 입력 내용 (원본 보존)

```
{content_preview}
```

## 기본 메타데이터

- **입력 유형**: {input_type}
- **처리 시각**: {timestamp}
- **오류 원인**: {error_reason}

## 수동 분석 필요 항목

- [ ] 식별 전략 분류 ([[DML]] / [[IV]] / [[DID]] / [[RDD]] / [[Causal Forest]])
- [ ] 핵심 추정식 LaTeX 작성
- [ ] 핵심 가정 목록화
- [ ] 관련 노드 WikiLink 연결

---
*ROS Safe Mode — 재분석 대기 중*
"""

    def generate_fallback_note(
        self,
        title:        str,
        content:      str,
        input_type:   str = "unknown",
        error_reason: str = "API unavailable",
        year:         int = 0,
    ) -> str:
        return self.SAFE_MODE_TEMPLATE.format(
            title          = title,
            year           = year or datetime.utcnow().year,
            content_preview = content[:500].replace("`", "'"),
            input_type     = input_type,
            timestamp      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            error_reason   = error_reason,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Fault Recovery Engine
# ══════════════════════════════════════════════════════════════════════════════

class FaultRecoveryEngine:
    """
    통합 장애 복구 관리자.
    회로 차단기 + 안전 모드 + 복구 로그.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".econometric_wiki"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = data_dir / "fault_log.json"

        # API 제공자별 회로 차단기
        self._breakers: dict[str, CircuitBreaker] = {}
        self.safe_mode = SafeMode()
        self._fault_log: list[dict] = []
        self._load_log()

    def get_breaker(self, provider: str) -> CircuitBreaker:
        if provider not in self._breakers:
            self._breakers[provider] = CircuitBreaker(name=provider)
        return self._breakers[provider]

    def execute_with_recovery(
        self,
        provider:   str,
        func:       Callable,
        *args,
        fallback:   Optional[Callable] = None,
        max_retries: int = 3,
        **kwargs,
    ) -> tuple[Any, bool]:
        """
        회로 차단기 + 재시도 + 폴백으로 보호된 함수 실행.
        Returns: (result, is_fallback_used)
        """
        breaker = self.get_breaker(provider)

        for attempt in range(max_retries):
            try:
                result = breaker.call(func, *args, **kwargs)
                return result, False
            except RuntimeError as e:
                # 회로 차단기 OPEN
                self._log_fault(provider, "circuit_open", str(e))
                break
            except Exception as e:
                category = classify_error(e)
                self._log_fault(provider, category.value, str(e))

                # 재시도 불가 오류
                if category in (ErrorCategory.API_AUTH, ErrorCategory.PROMPT_INJECT):
                    break

                # 재시도 가능 오류
                if attempt < max_retries - 1:
                    wait = exponential_backoff_with_jitter(attempt)
                    logger.warning(
                        f"[{provider}] {category.value} — retry {attempt+1}/{max_retries} "
                        f"in {wait:.1f}s"
                    )
                    time.sleep(wait)

        # 폴백 실행
        if fallback:
            try:
                result = fallback(*args, **kwargs)
                return result, True
            except Exception as fe:
                logger.error(f"Fallback also failed: {fe}")

        return None, True

    def _log_fault(self, provider: str, category: str, message: str):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider":  provider,
            "category":  category,
            "message":   message[:500],
        }
        self._fault_log.append(entry)
        if len(self._fault_log) > 500:
            self._fault_log = self._fault_log[-500:]
        self._save_log()

    def _load_log(self):
        if self._log_path.exists():
            try:
                self._fault_log = json.loads(self._log_path.read_text(encoding="utf-8"))
            except Exception:
                self._fault_log = []

    def _save_log(self):
        try:
            tmp = self._log_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._fault_log, indent=2), encoding="utf-8")
            tmp.replace(self._log_path)
        except Exception:
            pass

    def get_health_report(self) -> dict:
        breaker_states = {
            name: {
                "state":          b.state,
                "failure_count":  b.failure_count,
                "total_failures": b.total_failures,
                "available":      b.is_available(),
            }
            for name, b in self._breakers.items()
        }
        recent_faults = self._fault_log[-10:] if self._fault_log else []
        return {
            "circuit_breakers": breaker_states,
            "recent_faults":    recent_faults,
            "total_faults":     len(self._fault_log),
        }

    def format_status_badge(self, provider: str) -> str:
        breaker = self._breakers.get(provider)
        if not breaker:
            return "⚪ Unknown"
        state = breaker.state
        if state == CircuitState.CLOSED.value:
            return "🟢 Healthy"
        elif state == CircuitState.HALF_OPEN.value:
            return "🟡 Recovering"
        else:
            return "🔴 Circuit Open"


# ── 싱글톤 ────────────────────────────────────────────────────────────────────
_engine: Optional[FaultRecoveryEngine] = None

def get_fault_recovery_engine() -> FaultRecoveryEngine:
    global _engine
    if _engine is None:
        _engine = FaultRecoveryEngine()
    return _engine
