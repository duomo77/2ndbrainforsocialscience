"""
ros_logger.py — ROS v8.0 통합 구조화 로깅
==========================================
Root Cause 수정:
  - 전체 코드베이스에 print() 디버그 문 산재
  - 예외 발생 시 오류 내용이 사용자 UI 메시지로만 전달되고 파일에 기록되지 않음
  - 모듈별 로거가 없어 오류 발생 위치 추적 불가

수정 전략:
  - 중앙화된 로거 팩토리 제공
  - JSON 구조화 로그 파일 기록 (~/.econometric_wiki/logs/)
  - 콘솔 출력은 개발 모드에서만
  - 성능 타이머 컨텍스트 매니저 제공
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional


# ── 로그 디렉토리 설정 ────────────────────────────────────────────────────────
_LOG_DIR = Path.home() / ".econometric_wiki" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOG_DIR / "ros.log"
_ERROR_FILE = _LOG_DIR / "ros_errors.log"

# ── 루트 로거 설정 (1회만 실행) ──────────────────────────────────────────────
_configured = False


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("ros")
    root.setLevel(logging.DEBUG)

    # 파일 핸들러 (회전, 최대 5MB × 3개)
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    root.addHandler(fh)

    # 에러 전용 파일 핸들러
    eh = logging.handlers.RotatingFileHandler(
        _ERROR_FILE, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    eh.setLevel(logging.ERROR)
    eh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s\n%(exc_info)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    root.addHandler(eh)

    # 개발 모드에서만 콘솔 출력
    if os.environ.get("ROS_DEBUG"):
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(ch)


_configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    """모듈별 로거를 반환한다. name은 'ros.core.worker' 형식을 권장."""
    if not name.startswith("ros."):
        name = f"ros.{name}"
    return logging.getLogger(name)


# ── 성능 타이머 ──────────────────────────────────────────────────────────────

@contextmanager
def timed(logger: logging.Logger, operation: str) -> Generator[None, None, None]:
    """
    코드 블록의 실행 시간을 측정하고 로깅한다.

    Usage:
        with timed(logger, "LLM 분석"):
            result = analyze(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("[PERF] %s: %.1f ms", operation, elapsed_ms)


# ── 구조화 이벤트 로거 ───────────────────────────────────────────────────────

class StructuredLogger:
    """JSON 구조화 이벤트를 기록하는 로거."""

    _event_file: Optional[Path] = None

    @classmethod
    def _get_event_file(cls) -> Path:
        if cls._event_file is None:
            cls._event_file = _LOG_DIR / "ros_events.jsonl"
        return cls._event_file

    @classmethod
    def log_event(
        cls,
        event_type: str,
        data: dict[str, Any],
        level: str = "info",
    ) -> None:
        """JSONL 형식으로 이벤트를 기록한다."""
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            "level": level,
            **data,
        }
        try:
            with open(cls._get_event_file(), "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 로그 기록 실패는 앱 동작에 영향 없음

    @classmethod
    def log_analysis_start(cls, title: str, input_type: str, model: str) -> None:
        cls.log_event("analysis_start", {
            "title": title, "input_type": input_type, "model": model
        })

    @classmethod
    def log_analysis_complete(cls, title: str, tokens: int, elapsed_ms: float) -> None:
        cls.log_event("analysis_complete", {
            "title": title, "tokens": tokens, "elapsed_ms": elapsed_ms
        })

    @classmethod
    def log_error(cls, context: str, error: Exception) -> None:
        cls.log_event("error", {
            "context": context,
            "error_type": type(error).__name__,
            "error_msg": str(error),
            "traceback": traceback.format_exc(limit=5),
        }, level="error")

    @classmethod
    def log_engine_status(cls, engine_name: str, status: str, details: dict) -> None:
        cls.log_event("engine_status", {
            "engine": engine_name, "status": status, **details
        })
