"""
log_manager.py — Centralized Logging System
============================================
Provides structured logging with configurable outputs for all system components.
Supports: application, OCR, embedding, parser, LLM, search, agent, error logs.

Backward compatible: delegates to existing core/ros_logger for current functionality.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Preserve backward compatibility with existing ros_logger
from core.ros_logger import (
    get_logger,
    timed,
    StructuredLogger,
)

__all__ = [
    "get_logger",
    "timed",
    "StructuredLogger",
    "LogManager",
    "get_log_manager",
    "LogCategory",
]

# ── Log directory structure ──────────────────────────────────────────────────
_LOG_ROOT = Path.home() / ".ros_config" / "logs"


class LogCategory:
    """Predefined log categories for consistent logger naming."""

    APP = "ros.app"
    OCR = "ros.ocr"
    EMBEDDING = "ros.embedding"
    PARSER = "ros.parser"
    LLM = "ros.llm"
    SEARCH = "ros.search"
    AGENT = "ros.agent"
    ERROR = "ros.error"
    AUDIT = "ros.audit"
    PERF = "ros.perf"
    GRAPH = "ros.graph"
    VAULT = "ros.vault"


class LogManager:
    """
    Centralized logging manager.

    Configures log outputs per category with rotation and formatting.
    Supports:
        - File-based rotating logs per category
        - Console output in debug mode
        - JSONL structured event logging
        - Configurable log levels
    """

    def __init__(self, log_root: Optional[Path] = None):
        self._log_root = log_root or _LOG_ROOT
        self._log_root.mkdir(parents=True, exist_ok=True)
        self._configured = False
        self._loggers: dict[str, logging.Logger] = {}

    def configure(self, debug: bool = False) -> None:
        """Configure all log categories."""
        if self._configured:
            return
        self._configured = True

        categories = {
            LogCategory.APP: "ros.log",
            LogCategory.OCR: "ros_ocr.log",
            LogCategory.EMBEDDING: "ros_embedding.log",
            LogCategory.PARSER: "ros_parser.log",
            LogCategory.LLM: "ros_llm.log",
            LogCategory.SEARCH: "ros_search.log",
            LogCategory.AGENT: "ros_agent.log",
            LogCategory.ERROR: "ros_error.log",
            LogCategory.AUDIT: "ros_audit.log",
            LogCategory.PERF: "ros_perf.log",
            LogCategory.GRAPH: "ros_graph.log",
            LogCategory.VAULT: "ros_vault.log",
        }

        for category, filename in categories.items():
            logger = logging.getLogger(category)
            logger.setLevel(logging.DEBUG if debug else logging.INFO)
            logger.propagate = False  # Don't bubble to root

            # File handler with rotation (5MB × 3 backups)
            file_path = self._log_root / filename
            fh = logging.handlers.RotatingFileHandler(
                file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            logger.addHandler(fh)

            # Console output in debug mode
            if debug or os.environ.get("ROS_DEBUG"):
                ch = logging.StreamHandler()
                ch.setLevel(logging.DEBUG)
                ch.setFormatter(logging.Formatter(
                    "[%(levelname)s] %(name)s: %(message)s"
                ))
                logger.addHandler(ch)

            self._loggers[category] = logger

    def get(self, category: str) -> logging.Logger:
        """Get a logger for a specific category."""
        if not self._configured:
            self.configure()
        if category in self._loggers:
            return self._loggers[category]
        return get_logger(category)

    def log_event(
        self,
        category: str,
        event_type: str,
        message: str,
        extra: Optional[dict] = None,
    ) -> None:
        """Log a structured event."""
        logger = self.get(category)
        log_data = {
            "ts": datetime.now().isoformat(),
            "type": event_type,
            "category": category,
            **(extra or {}),
        }
        logger.info(f"{message} | {log_data}")

    def log_error(
        self,
        category: str,
        error: Exception,
        context: str = "",
    ) -> None:
        """Log an error with full traceback context."""
        logger = self.get(category)
        logger.error(
            f"[{context}] {type(error).__name__}: {error}",
            exc_info=True,
        )
        # Also log to error category
        error_logger = self.get(LogCategory.ERROR)
        error_logger.error(
            f"[{category}] [{context}] {type(error).__name__}: {error}",
            exc_info=True,
        )

    @property
    def log_root(self) -> Path:
        return self._log_root


# Module-level singleton
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """Get or create the singleton LogManager instance."""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
        _log_manager.configure(debug=os.environ.get("ROS_DEBUG", "").lower() in ("1", "true", "yes"))
    return _log_manager