"""
pipeline/models.py — Data Models for Document Processing Pipeline
==================================================================
Immutable data structures for documents, processing status, and results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    EPUB = "epub"
    PPTX = "pptx"
    CSV = "csv"
    EXCEL = "excel"
    IMAGE_PNG = "image_png"
    IMAGE_JPG = "image_jpg"
    IMAGE_TIFF = "image_tiff"
    TRANSCRIPT_SRT = "transcript_srt"
    TRANSCRIPT_VTT = "transcript_vtt"
    CODE_PYTHON = "code_python"
    CODE_R = "code_r"
    CODE_STATA = "code_stata"
    CODE_JULIA = "code_julia"
    CODE_MATALAB = "code_matlab"
    CODE_STAN = "code_stan"
    UNKNOWN = "unknown"


class ProcessingStage(Enum):
    """Pipeline processing stages."""
    UPLOADED = "uploaded"
    QUEUED = "queued"
    VALIDATING = "validating"
    IDENTIFYING = "identifying"
    PARSING = "parsing"
    OCR = "ocr"
    CLEANING = "cleaning"
    NORMALIZING = "normalizing"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class ProcessingStatus(Enum):
    """Overall processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Document ─────────────────────────────────────────────────────────────────

@dataclass
class Document:
    """Represents a document in the processing pipeline.

    Tracks the document from ingestion through all processing stages.
    """
    id: str
    original_path: Path
    raw_path: Optional[Path] = None
    processed_path: Optional[Path] = None
    metadata_path: Optional[Path] = None

    # Identification
    doc_type: DocumentType = DocumentType.UNKNOWN
    mime_type: str = ""
    file_size_bytes: int = 0
    content_hash: str = ""
    language: str = ""
    encoding: str = "utf-8"
    needs_ocr: bool = False
    page_count: int = 0
    text_size_estimate: int = 0

    # Processing state
    status: ProcessingStatus = ProcessingStatus.PENDING
    current_stage: ProcessingStage = ProcessingStage.UPLOADED
    stage_history: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # Processing metrics
    processing_duration_ms: float = 0.0
    extraction_time_ms: float = 0.0
    ocr_time_ms: float = 0.0
    cleaning_time_ms: float = 0.0

    def record_stage(
        self,
        stage: ProcessingStage,
        duration_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a completed processing stage."""
        self.current_stage = stage
        self.updated_at = datetime.now().isoformat()
        entry = {
            "stage": stage.value,
            "timestamp": self.updated_at,
            "duration_ms": duration_ms,
            **(metadata or {}),
        }
        self.stage_history.append(entry)

    def record_error(self, stage: ProcessingStage, error: Exception) -> None:
        """Record a processing error."""
        self.errors.append({
            "stage": stage.value,
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        })

    def record_warning(self, message: str) -> None:
        """Record a non-fatal warning."""
        self.warnings.append(f"[{datetime.now().isoformat()}] {message}")

    def mark_completed(self) -> None:
        """Mark document processing as complete."""
        self.status = ProcessingStatus.COMPLETED
        self.current_stage = ProcessingStage.COMPLETED
        self.completed_at = datetime.now().isoformat()

    def mark_failed(self) -> None:
        """Mark document processing as failed."""
        self.status = ProcessingStatus.FAILED
        self.current_stage = ProcessingStage.FAILED

    @property
    def is_processed(self) -> bool:
        return self.status == ProcessingStatus.COMPLETED

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# ── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of document validation."""
    is_valid: bool
    file_path: Path
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_size_bytes: int = 0
    extension: str = ""
    mime_type: str = ""
    content_hash: str = ""
    is_duplicate: bool = False


@dataclass
class IdentificationResult:
    """Result of document identification."""
    doc_type: DocumentType = DocumentType.UNKNOWN
    mime_type: str = ""
    language: str = ""
    encoding: str = "utf-8"
    needs_ocr: bool = False
    page_count: int = 0
    text_size_estimate: int = 0
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Result of document parsing."""
    success: bool
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[str] = field(default_factory=list)
    parser_used: str = ""
    extraction_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class ProcessingHistory:
    """Complete processing history for a document."""
    document_id: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    pipeline_version: str = "1.0.0"
    stages: List[Dict[str, Any]] = field(default_factory=list)
    parser_used: str = ""
    ocr_engine: str = ""
    total_duration_ms: float = 0.0
    failure_reason: str = ""
    retry_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── File Type Mapping ───────────────────────────────────────────────────────

EXTENSION_TO_DOC_TYPE: Dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".doc": DocumentType.DOCX,
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MARKDOWN,
    ".rst": DocumentType.MARKDOWN,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
    ".epub": DocumentType.EPUB,
    ".pptx": DocumentType.PPTX,
    ".ppt": DocumentType.PPTX,
    ".csv": DocumentType.CSV,
    ".tsv": DocumentType.CSV,
    ".xlsx": DocumentType.EXCEL,
    ".xls": DocumentType.EXCEL,
    ".png": DocumentType.IMAGE_PNG,
    ".jpg": DocumentType.IMAGE_JPG,
    ".jpeg": DocumentType.IMAGE_JPG,
    ".tiff": DocumentType.IMAGE_TIFF,
    ".tif": DocumentType.IMAGE_TIFF,
    # Transcript formats
    ".srt": DocumentType.TRANSCRIPT_SRT,
    ".vtt": DocumentType.TRANSCRIPT_VTT,
    # Code files
    ".py": DocumentType.CODE_PYTHON,
    ".r": DocumentType.CODE_R,
    ".do": DocumentType.CODE_STATA,
    ".jl": DocumentType.CODE_JULIA,
    ".m": DocumentType.CODE_MATALAB,
    ".stan": DocumentType.CODE_STAN,
}

MIME_TO_DOC_TYPE: Dict[str, DocumentType] = {
    "application/pdf": DocumentType.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.DOCX,
    "application/msword": DocumentType.DOCX,
    "text/plain": DocumentType.TXT,
    "text/markdown": DocumentType.MARKDOWN,
    "text/html": DocumentType.HTML,
    "application/epub+zip": DocumentType.EPUB,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": DocumentType.PPTX,
    "text/csv": DocumentType.CSV,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocumentType.EXCEL,
    "application/vnd.ms-excel": DocumentType.EXCEL,
    "image/png": DocumentType.IMAGE_PNG,
    "image/jpeg": DocumentType.IMAGE_JPG,
    "image/tiff": DocumentType.IMAGE_TIFF,
    "application/x-subrip": DocumentType.TRANSCRIPT_SRT,
    "text/vtt": DocumentType.TRANSCRIPT_VTT,
}