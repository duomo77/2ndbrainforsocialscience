"""
pipeline/interfaces.py — Abstract Interfaces for Pipeline Components
=====================================================================
Defines contracts for all swappable pipeline stages.
Implementations can be registered and swapped without affecting the pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from core.pipeline.models import (  # noqa: F401 (re-export)
    Document,
    ValidationResult,
    IdentificationResult,
    ParseResult,
    ProcessingStatus,
)


class PipelineStage(ABC):
    """Base interface for all pipeline stages."""

    @abstractmethod
    def execute(self, document: Document) -> Document:
        """Execute this pipeline stage on a document.

        Args:
            document: The document to process

        Returns:
            The document with updated processing state
        """
        ...

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Human-readable name of this pipeline stage."""
        ...

    @abstractmethod
    def can_handle(self, document: Document) -> bool:
        """Check if this stage can process the given document."""
        ...


class DocumentValidator(ABC):
    """Interface for document validation."""

    @abstractmethod
    def validate(self, file_path: Path) -> ValidationResult:
        """Validate that a file can be processed.

        Checks:
            - File exists and is readable
            - Extension is supported
            - File size is within limits
            - File is not corrupted (basic check)
            - File is not a duplicate (content hash check)
            - MIME type matches extension

        Args:
            file_path: Path to the file

        Returns:
            ValidationResult with validation details
        """
        ...

    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return set of supported file extensions."""
        ...

    @abstractmethod
    def max_file_size_bytes(self) -> int:
        """Maximum supported file size in bytes."""
        ...


class DocumentIdentifier(ABC):
    """Interface for document identification and classification."""

    @abstractmethod
    def identify(self, file_path: Path) -> IdentificationResult:
        """Identify document properties.

        Detects:
            - Document type (PDF, DOCX, TXT, etc.)
            - Language (if text)
            - Encoding
            - Estimated page count
            - Estimated text size
            - Whether OCR is required

        Args:
            file_path: Path to the file

        Returns:
            IdentificationResult with detected properties
        """
        ...

    @abstractmethod
    def detect_language(self, text: str) -> str:
        """Detect language of text content."""
        ...

    @abstractmethod
    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding."""
        ...

    @abstractmethod
    def needs_ocr(self, file_path: Path) -> bool:
        """Determine if OCR is required for this file."""
        ...


class DocumentParser(ABC):
    """Interface for document parsing."""

    @abstractmethod
    def parse(self, file_path: Path, **options) -> ParseResult:
        """Parse a document file into structured content.

        Args:
            file_path: Path to the document
            **options: Parser-specific options

        Returns:
            ParseResult with extracted text, metadata, and chunks
        """
        ...

    @abstractmethod
    def supported_types(self) -> List[str]:
        """List of document types this parser handles."""
        ...

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract document metadata (author, title, dates, etc.)."""
        ...


class DocumentCleaner(ABC):
    """Interface for document text cleaning and normalization."""

    @abstractmethod
    def clean(self, text: str, doc_type: str = "unknown") -> str:
        """Clean and normalize extracted text.

        Operations:
            - Remove excessive whitespace
            - Normalize line endings
            - Fix common encoding issues
            - Remove control characters
            - Unify quotation marks
            - Normalize Unicode

        Args:
            text: Raw extracted text
            doc_type: Type of document (for type-specific cleaning)

        Returns:
            Cleaned text
        """
        ...

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Normalize text for downstream processing (Unicode NFC)."""
        ...


class DocumentStorage(ABC):
    """Interface for document storage and retrieval."""

    @abstractmethod
    def store_raw(self, document: Document, content: bytes) -> Path:
        """Store the raw uploaded document file."""
        ...

    @abstractmethod
    def store_processed(self, document: Document, content: str) -> Path:
        """Store the processed document text."""
        ...

    @abstractmethod
    def store_metadata(self, document: Document, metadata: Dict[str, Any]) -> Path:
        """Store document metadata as JSON."""
        ...

    @abstractmethod
    def get_raw_path(self, document: Document) -> Path:
        """Get the raw file storage path."""
        ...

    @abstractmethod
    def get_processed_path(self, document: Document) -> Path:
        """Get the processed text storage path."""
        ...

    @abstractmethod
    def get_metadata_path(self, document: Document) -> Path:
        """Get the metadata storage path."""
        ...

    @abstractmethod
    def cleanup(self, document: Document) -> None:
        """Remove temporary files for a document."""
        ...