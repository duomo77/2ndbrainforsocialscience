"""
pipeline/doc_manager.py — Document Manager Service
=====================================================
Central service for registering, tracking, and managing documents.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.pipeline.models import (
    Document,
    ProcessingStatus,
    ProcessingStage,
    ProcessingHistory,
    DocumentType,
    EXTENSION_TO_DOC_TYPE,
)
from core.pipeline.validator import DocumentValidatorImpl
from core.pipeline.file_storage import FileStorage
from core.utils.hash_utils import content_hash
from logs.log_manager import LogManager, LogCategory, get_log_manager


class DocumentManager:
    """Manages document lifecycle: register, track, retry, query.

    Features:
        - Register new documents for processing
        - Track processing status and history
        - Handle retries for failed documents
        - Query documents by status, type, date range
    """

    def __init__(
        self,
        storage: Optional[FileStorage] = None,
        log_manager: Optional[LogManager] = None,
    ):
        self._storage = storage or FileStorage()
        self._log = log_manager or get_log_manager()
        self._documents: Dict[str, Document] = {}
        self._history: Dict[str, ProcessingHistory] = {}
        self._validator = DocumentValidatorImpl()

    def register(self, file_path: Path | str) -> Document:
        """Register a document for processing.

        Args:
            file_path: Path to the document file

        Returns:
            Registered Document instance
        """
        path = Path(file_path).resolve()
        doc_id = self._generate_id(path)

        # Check if already registered
        if doc_id in self._documents:
            existing = self._documents[doc_id]
            if existing.status in (ProcessingStatus.FAILED, ProcessingStatus.CANCELLED):
                # Allow re-registration of failed documents
                pass
            else:
                return existing

        # Create document
        extension = path.suffix.lower()
        doc_type = EXTENSION_TO_DOC_TYPE.get(extension, DocumentType.UNKNOWN)

        document = Document(
            id=doc_id,
            original_path=path,
            doc_type=doc_type,
            file_size_bytes=path.stat().st_size if path.exists() else 0,
            status=ProcessingStatus.PENDING,
        )

        # Copy raw file to storage
        if path.exists():
            try:
                raw_content = path.read_bytes()
                self._storage.store_raw(document, raw_content)
            except OSError:
                pass

        # Register
        self._documents[doc_id] = document
        self._history[doc_id] = ProcessingHistory(
            document_id=doc_id,
            started_at=datetime.now().isoformat(),
        )

        self._log.log_event(
            LogCategory.PARSER,
            "document_registered",
            f"Document registered: {doc_id} ({path.name})",
            extra={"doc_id": doc_id, "filename": path.name, "size": document.file_size_bytes},
        )

        return document

    def get(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def update(self, document: Document) -> None:
        """Update a document's state."""
        self._documents[document.id] = document

    def record_history(self, document: Document, parser_used: str = "", ocr_engine: str = "") -> None:
        """Record processing history for a document."""
        history = self._history.get(document.id)
        if history:
            history.status = document.status
            history.stages = document.stage_history
            history.parser_used = parser_used
            history.ocr_engine = ocr_engine
            history.total_duration_ms = document.processing_duration_ms
            history.completed_at = document.completed_at
            if document.errors:
                history.failure_reason = "; ".join(
                    e.get("error_message", "") for e in document.errors
                )

    def get_history(self, doc_id: str) -> Optional[ProcessingHistory]:
        """Get processing history for a document."""
        return self._history.get(doc_id)

    def retry(self, doc_id: str) -> Optional[Document]:
        """Retry processing for a failed document."""
        document = self._documents.get(doc_id)
        if not document:
            return None

        if document.status != ProcessingStatus.FAILED:
            return document

        # Reset state for retry
        document.status = ProcessingStatus.PENDING
        document.current_stage = ProcessingStage.RETRYING
        document.errors = []
        document.warnings = []

        history = self._history.get(doc_id)
        if history:
            history.retry_count += 1
            history.status = ProcessingStatus.PENDING

        self._log.log_event(
            LogCategory.PARSER,
            "document_retry",
            f"Retrying document: {doc_id} (attempt {history.retry_count if history else 1})",
        )

        return document

    def cancel(self, doc_id: str) -> bool:
        """Cancel processing for a document."""
        document = self._documents.get(doc_id)
        if not document:
            return False

        document.status = ProcessingStatus.CANCELLED
        document.current_stage = ProcessingStage.FAILED
        return True

    def query(
        self,
        status: Optional[ProcessingStatus] = None,
        doc_type: Optional[DocumentType] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[Document]:
        """Query documents by filter criteria."""
        results = []

        for doc in self._documents.values():
            if status and doc.status != status:
                continue
            if doc_type and doc.doc_type != doc_type:
                continue
            if since and doc.created_at < since:
                continue
            results.append(doc)

        # Sort by creation date (newest first)
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[:limit]

    def list_all(self) -> List[Document]:
        """List all registered documents."""
        return sorted(
            self._documents.values(),
            key=lambda d: d.created_at,
            reverse=True,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get document processing statistics."""
        total = len(self._documents)
        completed = sum(1 for d in self._documents.values() if d.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for d in self._documents.values() if d.status == ProcessingStatus.FAILED)
        processing = sum(1 for d in self._documents.values() if d.status == ProcessingStatus.PROCESSING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "pending": total - completed - failed - processing,
            "storage": self._storage.get_stats(),
        }

    def _generate_id(self, file_path: Path) -> str:
        """Generate a unique document ID."""
        name_hash = content_hash(file_path.name, algorithm="blake2b")[:8]
        short_uuid = uuid.uuid4().hex[:8]
        return f"doc-{name_hash}-{short_uuid}"