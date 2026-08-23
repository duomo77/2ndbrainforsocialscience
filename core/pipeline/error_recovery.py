"""
pipeline/error_recovery.py — Error Recovery Service
=====================================================
Handles pipeline failures with retry, graceful degradation, and logging.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from core.pipeline.models import Document, ProcessingStage
from logs.log_manager import LogManager, LogCategory, get_log_manager


class ErrorRecoveryManager:
    """Manages error recovery for pipeline stages.

    Features:
        - Automatic retries with exponential backoff
        - Graceful degradation (skip failed stage, continue pipeline)
        - Error categorization and logging
        - Maximum retry limits per stage
    """

    # Maximum retries per stage type
    MAX_RETRIES: dict[str, int] = {
        "validating": 3,
        "identifying": 3,
        "parsing": 2,
        "ocr": 2,
        "cleaning": 2,
        "normalizing": 2,
        "storing": 3,
    }

    # Base delay in seconds for exponential backoff
    BASE_DELAY_SECONDS: float = 1.0
    MAX_DELAY_SECONDS: float = 30.0

    def __init__(self, log_manager: Optional[LogManager] = None):
        self._log = log_manager or get_log_manager()
        self._failure_counts: dict[str, dict[str, int]] = {}

    def execute_with_recovery(
        self,
        document: Document,
        stage: ProcessingStage,
        operation: Callable[[Document], Document],
        can_skip: bool = True,
    ) -> Document:
        """Execute a pipeline stage with error recovery.

        Args:
            document: The document being processed
            stage: The pipeline stage being executed
            operation: The stage operation to execute
            can_skip: If True, skip this stage on failure instead of aborting

        Returns:
            The document (possibly with errors recorded)
        """
        stage_key = stage.value
        max_retries = self.MAX_RETRIES.get(stage_key, 2)

        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                start_time = time.perf_counter()
                result = operation(document)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                document.record_stage(stage, duration_ms=elapsed_ms)
                self._log.log_event(
                    LogCategory.PARSER,
                    "stage_completed",
                    f"Stage '{stage_key}' completed for {document.id}",
                    extra={"attempt": attempt + 1, "elapsed_ms": elapsed_ms},
                )
                return result

            except Exception as e:
                last_error = e
                document.record_error(stage, e)

                self._log.log_error(
                    LogCategory.PARSER,
                    e,
                    context=f"Stage '{stage_key}' failed (attempt {attempt + 1}/{max_retries + 1}) for {document.id}",
                )

                if attempt < max_retries:
                    delay = min(
                        self.BASE_DELAY_SECONDS * (2 ** attempt),
                        self.MAX_DELAY_SECONDS,
                    )
                    document.record_stage(
                        ProcessingStage.RETRYING,
                        metadata={"attempt": attempt + 1, "delay_seconds": delay},
                    )
                    time.sleep(delay)
                    continue

        # All retries exhausted
        if can_skip:
            document.record_warning(
                f"Stage '{stage_key}' failed after {max_retries + 1} attempts — skipped. "
                f"Error: {last_error}"
            )
            document.record_stage(ProcessingStage.SKIPPED)
            self._log.log_event(
                LogCategory.PARSER,
                "stage_skipped",
                f"Stage '{stage_key}' skipped after failures for {document.id}",
                extra={"error": str(last_error)},
            )
        else:
            document.mark_failed()
            self._log.log_event(
                LogCategory.PARSER,
                "pipeline_failed",
                f"Pipeline failed at stage '{stage_key}' for {document.id}",
                extra={"error": str(last_error)},
            )

        return document

    def can_retry(self, stage_key: str, document_id: str) -> bool:
        """Check if a stage can be retried for a document."""
        key = f"{document_id}:{stage_key}"
        failures = self._failure_counts.get(key, 0)
        max_retries = self.MAX_RETRIES.get(stage_key, 2)
        return failures < max_retries + 1

    def reset(self, document_id: str) -> None:
        """Reset failure counts for a document."""
        keys_to_remove = [k for k in self._failure_counts if k.startswith(f"{document_id}:")]
        for k in keys_to_remove:
            del self._failure_counts[k]