"""
pipeline/validator.py — Document Validation Service
=====================================================
Validates documents before they enter the processing pipeline.
Checks: extension, file size, corruption, duplicates, MIME type.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Set

from core.pipeline.interfaces import DocumentValidator
from core.pipeline.models import (
    ValidationResult,
    EXTENSION_TO_DOC_TYPE,
    MIME_TO_DOC_TYPE,
)
from core.utils.hash_utils import file_hash
from core.constants import MAX_RAG_FILE_BYTES


class DocumentValidatorImpl(DocumentValidator):
    """Default document validator implementation."""

    # Maximum file sizes per document type
    SIZE_LIMITS: dict[str, int] = {
        "pdf": 100 * 1024 * 1024,      # 100 MB
        "docx": 50 * 1024 * 1024,       # 50 MB
        "txt": 10 * 1024 * 1024,        # 10 MB
        "markdown": 10 * 1024 * 1024,
        "html": 20 * 1024 * 1024,
        "epub": 50 * 1024 * 1024,
        "pptx": 100 * 1024 * 1024,
        "csv": 50 * 1024 * 1024,
        "excel": 50 * 1024 * 1024,
        "image": 50 * 1024 * 1024,
        "transcript_srt": 10 * 1024 * 1024,   # 10 MB
        "transcript_vtt": 10 * 1024 * 1024,
        "code_python": 5 * 1024 * 1024,       # 5 MB
        "code_r": 5 * 1024 * 1024,
        "code_stata": 5 * 1024 * 1024,
        "code_julia": 5 * 1024 * 1024,
        "code_matlab": 5 * 1024 * 1024,
        "code_stan": 5 * 1024 * 1024,
        "default": 50 * 1024 * 1024,
    }

    def __init__(self, max_file_size: int = MAX_RAG_FILE_BYTES):
        self._max_file_size = max_file_size
        self._known_hashes: Set[str] = set()

    def validate(self, file_path: Path) -> ValidationResult:
        """Run all validation checks."""
        errors = []
        warnings = []

        # Check for broken symlinks first — before general existence checks
        # Broken symlinks return False for .exists() on most platforms, so we
        # need to detect them early with a more specific error message.
        if file_path.is_symlink() and not file_path.resolve().exists():
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                errors=["Broken symlink detected"],
            )

        # Check file exists
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                errors=["File does not exist"],
            )

        # Check file is readable
        if not file_path.is_file():
            return ValidationResult(
                is_valid=False,
                file_path=file_path,
                errors=["Path is not a file"],
            )

        # Get file size (follow symlinks via stat())
        file_size = file_path.stat().st_size

        # Check extension
        extension = file_path.suffix.lower()
        if extension not in EXTENSION_TO_DOC_TYPE:
            errors.append(f"Unsupported file extension: {extension}")

        # Check file size
        if file_size <= 0:
            errors.append("File is empty")
        elif file_size > self._max_file_size:
            errors.append(
                f"File too large: {file_size:,} bytes (max: {self._max_file_size:,} bytes)"
            )
            warnings.append("File may be truncated during processing")

        # Warn about symlinked files (potential security concern)
        if file_path.is_symlink():
            warnings.append("File is a symbolic link — resolved path used for validation")

        # Check type-specific size limits
        doc_type = EXTENSION_TO_DOC_TYPE.get(extension)
        if doc_type:
            type_name = doc_type.value
            type_limit = self.SIZE_LIMITS.get(type_name, self.SIZE_LIMITS["default"])
            if file_size > type_limit:
                errors.append(
                    f"File exceeds size limit for {type_name}: {file_size:,} > {type_limit:,}"
                )

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
            warnings.append(f"Could not determine MIME type, using: {mime_type}")

        # Check MIME type matches extension
        expected_doc_type = MIME_TO_DOC_TYPE.get(mime_type)
        if expected_doc_type and doc_type and expected_doc_type != doc_type:
            warnings.append(
                f"MIME type ({mime_type}) does not match extension ({extension})"
            )

        # Generate content hash
        content_hash = file_hash(file_path) or ""

        # Check for duplicates
        is_duplicate = content_hash in self._known_hashes if content_hash else False
        if is_duplicate:
            warnings.append("Duplicate file detected (same content hash)")

        # Register hash for future duplicate detection
        if content_hash and not is_duplicate:
            self._known_hashes.add(content_hash)

        return ValidationResult(
            is_valid=len(errors) == 0,
            file_path=file_path,
            errors=errors,
            warnings=warnings,
            file_size_bytes=file_size,
            extension=extension,
            mime_type=mime_type or "",
            content_hash=content_hash,
            is_duplicate=is_duplicate,
        )

    def supported_extensions(self) -> set[str]:
        return set(EXTENSION_TO_DOC_TYPE.keys())

    def max_file_size_bytes(self) -> int:
        return self._max_file_size