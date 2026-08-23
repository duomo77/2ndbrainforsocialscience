"""
pipeline/pipeline.py — Document Processing Pipeline Orchestrator
==================================================================
Orchestrates the complete document processing pipeline:
Validate → Identify → Parse → (OCR) → Clean → Normalize → Store
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from core.pipeline.models import Document, ProcessingStatus, ProcessingStage
from core.pipeline.validator import DocumentValidatorImpl
from core.pipeline.identifier import DocumentIdentifierImpl
from core.pipeline.cleaner import DocumentCleanerImpl
from core.pipeline.parsers import ParserRegistry, create_default_registry
from core.pipeline.file_storage import FileStorage
from core.pipeline.doc_manager import DocumentManager
from core.pipeline.error_recovery import ErrorRecoveryManager
from logs.log_manager import LogManager, LogCategory, get_log_manager


class DocumentPipeline:
    """Orchestrates the complete document processing pipeline.

    Pipeline stages (in order):
        1. Validation — check file is valid and supported
        2. Identification — detect type, language, encoding
        3. Parsing — extract text using appropriate parser
        4. OCR — extract text from images/scanned PDFs (if needed)
        5. Cleaning — remove artifacts, normalize whitespace
        6. Normalization — Unicode normalization
        7. Storage — persist results

    Each stage is independent and can be swapped or extended.
    """

    def __init__(
        self,
        doc_manager: Optional[DocumentManager] = None,
        parser_registry: Optional[ParserRegistry] = None,
        storage: Optional[FileStorage] = None,
        log_manager: Optional[LogManager] = None,
    ):
        self._doc_manager = doc_manager or DocumentManager()
        self._parser_registry = parser_registry or create_default_registry()
        self._storage = storage or FileStorage()
        self._log = log_manager or get_log_manager()

        # Stage services
        self._validator = DocumentValidatorImpl()
        self._identifier = DocumentIdentifierImpl()
        self._cleaner = DocumentCleanerImpl()
        self._error_recovery = ErrorRecoveryManager(self._log)

    def process(self, file_path: Path | str) -> Document:
        """Process a document through the complete pipeline.

        Args:
            file_path: Path to the document file

        Returns:
            Processed Document with all stages recorded

        Raises:
            ValueError: If validation fails irrecoverably
        """
        path = Path(file_path).resolve()
        start_time = time.perf_counter()

        # Register document
        document = self._doc_manager.register(path)
        document.status = ProcessingStatus.PROCESSING

        self._log.log_event(
            LogCategory.PARSER,
            "pipeline_started",
            f"Pipeline started for: {document.id}",
        )

        try:
            # Stage 1: Validation
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.VALIDATING,
                lambda d: self._validate(d, path),
                can_skip=False,  # Validation failure is fatal
            )
            if document.status == ProcessingStatus.FAILED:
                return document

            # Stage 2: Identification
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.IDENTIFYING,
                lambda d: self._identify(d, path),
                can_skip=False,
            )
            if document.status == ProcessingStatus.FAILED:
                return document

            # Stage 3: Parsing
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.PARSING,
                lambda d: self._parse(d),
                can_skip=False,
            )
            if document.status == ProcessingStatus.FAILED:
                return document

            # Stage 4: OCR (if needed)
            if document.needs_ocr:
                document = self._error_recovery.execute_with_recovery(
                    document,
                    ProcessingStage.OCR,
                    lambda d: self._ocr(d),
                    can_skip=True,
                )

            # Stage 5: Cleaning
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.CLEANING,
                lambda d: self._clean(d),
                can_skip=True,
            )

            # Stage 6: Normalization
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.NORMALIZING,
                lambda d: self._normalize(d),
                can_skip=True,
            )

            # Stage 7: Storage
            document = self._error_recovery.execute_with_recovery(
                document,
                ProcessingStage.STORING,
                lambda d: self._store(d),
                can_skip=False,
            )

            # Mark complete
            document.mark_completed()
            document.processing_duration_ms = (time.perf_counter() - start_time) * 1000

            # Record history
            self._doc_manager.record_history(document, parser_used="pipeline")

            self._log.log_event(
                LogCategory.PARSER,
                "pipeline_completed",
                f"Pipeline completed for: {document.id}",
                extra={
                    "duration_ms": document.processing_duration_ms,
                    "doc_type": document.doc_type.value,
                },
            )

        except Exception as e:
            document.mark_failed()
            self._log.log_error(LogCategory.PARSER, e, context=f"Pipeline failed for {document.id}")

        return document

    # ── Stage Implementations ─────────────────────────────────────────────

    def _validate(self, document: Document, file_path: Path) -> Document:
        """Stage 1: Validate document."""
        result = self._validator.validate(file_path)

        if not result.is_valid:
            for err in result.errors:
                document.record_warning(err)
            document.mark_failed()
            return document

        # Update document with validation results
        document.file_size_bytes = result.file_size_bytes
        document.content_hash = result.content_hash

        for warning in result.warnings:
            document.record_warning(warning)

        return document

    def _identify(self, document: Document, file_path: Path) -> Document:
        """Stage 2: Identify document properties."""
        result = self._identifier.identify(file_path)

        document.doc_type = result.doc_type
        document.mime_type = result.mime_type
        document.language = result.language
        document.encoding = result.encoding
        document.needs_ocr = result.needs_ocr
        document.page_count = result.page_count
        document.text_size_estimate = result.text_size_estimate
        document.metadata.update(result.metadata)

        return document

    def _parse(self, document: Document) -> Document:
        """Stage 3: Parse document content."""
        parser = self._parser_registry.get(document.doc_type)
        start = time.perf_counter()

        result = parser.parse(document.original_path, encoding=document.encoding)

        if not result.success:
            document.record_warning(f"Parsing failed: {'; '.join(result.errors)}")
            document.mark_failed()
            return document

        # Store parsed text as metadata for next stages
        document.metadata["parsed_text"] = result.text
        document.metadata["parser_used"] = result.parser_used
        document.metadata.update(result.metadata)
        document.extraction_time_ms = (time.perf_counter() - start) * 1000

        return document

    def _ocr(self, document: Document) -> Document:
        """Stage 4: OCR processing for images/scanned PDFs."""
        # OCR is not yet implemented — placeholder for future implementation
        document.record_warning("OCR not yet implemented — using raw parser output")
        document.ocr_time_ms = 0.0
        return document

    def _clean(self, document: Document) -> Document:
        """Stage 5: Clean extracted text."""
        raw_text = document.metadata.get("parsed_text", "")
        if not raw_text:
            return document

        start = time.perf_counter()
        cleaned = self._cleaner.clean(raw_text, document.doc_type.value)
        document.metadata["cleaned_text"] = cleaned
        document.cleaning_time_ms = (time.perf_counter() - start) * 1000

        return document

    def _normalize(self, document: Document) -> Document:
        """Stage 6: Normalize text."""
        text = document.metadata.get("cleaned_text", document.metadata.get("parsed_text", ""))
        if text:
            text = self._cleaner.normalize(text)
            document.metadata["normalized_text"] = text

        return document

    def _store(self, document: Document) -> Document:
        """Stage 7: Persist processed document."""
        final_text = document.metadata.get("normalized_text", document.metadata.get("parsed_text", ""))

        # Store processed text
        self._storage.store_processed(document, final_text)

        # Store metadata
        storage_metadata = {
            "id": document.id,
            "original_path": str(document.original_path),
            "doc_type": document.doc_type.value,
            "language": document.language,
            "encoding": document.encoding,
            "page_count": document.page_count,
            "file_size_bytes": document.file_size_bytes,
            "content_hash": document.content_hash,
            "needs_ocr": document.needs_ocr,
            "processing_duration_ms": document.processing_duration_ms,
            "stage_history": document.stage_history,
            "errors": document.errors,
            "warnings": document.warnings,
        }
        self._storage.store_metadata(document, storage_metadata)

        # Cleanup temporary files
        self._storage.cleanup(document)

        return document


# ── Convenience function ─────────────────────────────────────────────────

def process_document(file_path: Path | str, expand_scientific_context: bool = False) -> Document:
    """Quick one-shot document processing with default pipeline.

    Args:
        file_path: Path to the document file
        expand_scientific_context: When True, the imported document is
            additionally expanded into its scientific context (EPIC 09)
            after successful processing. Output paths are recorded on
            ``document.metadata["scientific_context"]``. Expansion is
            post-import and fault-isolated: it can never break the import.
            Defaults to False, keeping historical behaviour unchanged.

    Returns:
        Processed Document
    """
    pipeline = DocumentPipeline()
    document = pipeline.process(file_path)

    if expand_scientific_context and document.status == ProcessingStatus.COMPLETED:
        try:
            from literature.context.importer import attach_scientific_context

            document = attach_scientific_context(document)
        except Exception as exc:  # expansion must never break import
            document.record_warning(f"scientific context expansion skipped: {exc}")

    return document