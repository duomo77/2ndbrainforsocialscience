"""
pipeline/__init__.py — Document Processing Pipeline
=====================================================
Modular, extensible document ingestion and processing pipeline.

Architecture:
    Document → Validate → Identify → Parse → OCR(opt) → Clean → Normalize → Store

All stages are independent services implementing defined interfaces.
"""

from core.pipeline.interfaces import (
    DocumentParser,
    DocumentValidator,
    DocumentIdentifier,
    DocumentCleaner,
    DocumentStorage,
    PipelineStage,
)
from core.pipeline.models import (
    Document,
    ProcessingStatus,
    ProcessingStage,
    ValidationResult,
    IdentificationResult,
    ParseResult,
    ProcessingHistory,
    DocumentType,
)
from core.pipeline.pipeline import DocumentPipeline
from core.pipeline.doc_manager import DocumentManager
from core.pipeline.validator import DocumentValidatorImpl
from core.pipeline.identifier import DocumentIdentifierImpl
from core.pipeline.cleaner import DocumentCleanerImpl
from core.pipeline.parsers import (
    ParserRegistry,
    create_default_registry,
    TextParser,
    PDFParser,
    CSVExcelParser,
    HTMLParser,
    DOCXParser,
    PPTXParser,
    EPUBParser,
    SRTParser,
    VTTParser,
    CodeParser,
)
from core.pipeline.error_recovery import ErrorRecoveryManager

__all__ = [
    # Interfaces
    "DocumentParser",
    "DocumentValidator",
    "DocumentIdentifier",
    "DocumentCleaner",
    "DocumentStorage",
    "PipelineStage",
    # Models
    "Document",
    "ProcessingStatus",
    "ProcessingStage",
    "ValidationResult",
    "IdentificationResult",
    "ParseResult",
    "ProcessingHistory",
    "DocumentType",
    # Services
    "DocumentPipeline",
    "DocumentManager",
    "DocumentValidatorImpl",
    "DocumentIdentifierImpl",
    "DocumentCleanerImpl",
    "ErrorRecoveryManager",
    # Parser implementations
    "ParserRegistry",
    "create_default_registry",
    "TextParser",
    "PDFParser",
    "CSVExcelParser",
    "HTMLParser",
    "DOCXParser",
    "PPTXParser",
    "EPUBParser",
    "SRTParser",
    "VTTParser",
    "CodeParser",
]