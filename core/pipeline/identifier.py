"""
pipeline/identifier.py — Document Identification Service
==========================================================
Identifies document type, language, encoding, and determines if OCR is needed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.pipeline.interfaces import DocumentIdentifier
from core.pipeline.models import (
    IdentificationResult,
    DocumentType,
    EXTENSION_TO_DOC_TYPE,
)


class DocumentIdentifierImpl(DocumentIdentifier):
    """Default document identifier implementation."""

    # File signatures (magic bytes) for common document types
    FILE_SIGNATURES: dict[bytes, DocumentType] = {
        b"%PDF": DocumentType.PDF,
        b"PK\x03\x04": DocumentType.DOCX,  # ZIP-based (DOCX, EPUB, PPTX, XLSX all share this)
        b"\xd0\xcf\x11\xe0": DocumentType.DOCX,  # OLE2 (older .doc, .ppt, .xls)
        b"<!DOCTYPE html": DocumentType.HTML,
        b"<html": DocumentType.HTML,
        b"\x89PNG": DocumentType.IMAGE_PNG,
        b"\xff\xd8\xff": DocumentType.IMAGE_JPG,
        b"II*\x00": DocumentType.IMAGE_TIFF,
        b"MM\x00*": DocumentType.IMAGE_TIFF,
    }

    # Common language patterns for detection
    LANGUAGE_PATTERNS: dict[str, str] = {
        "en": r"\b(the|and|that|have|for|not|with|you|this|but|his|from|they)\b",
        "ko": r"[\uac00-\ud7af]",
        "zh": r"[\u4e00-\u9fff]",
        "ja": r"[\u3040-\u309f\u30a0-\u30ff]",
        "fr": r"\b(le|la|les|des|est|une|dans|pas|que|par|sur)\b",
        "de": r"\b(der|die|das|und|ist|ein|nicht|von|mit|sich|auf)\b",
        "es": r"\b(el|la|los|las|de|que|en|por|con|para|una)\b",
    }

    def identify(self, file_path: Path) -> IdentificationResult:
        """Identify document properties."""
        extension = file_path.suffix.lower()
        doc_type = EXTENSION_TO_DOC_TYPE.get(extension, DocumentType.UNKNOWN)
        mime_type = self._guess_mime_type(file_path)

        # Only use file signature to refine type when the extension didn't
        # already give us a definitive answer. Signature-based detection is
        # unreliable for text-based formats (.srt, .vtt, .py, .r, etc.)
        # because _check_file_signature falls back to DocumentType.TXT.
        if doc_type == DocumentType.UNKNOWN:
            sig_type = self._check_file_signature(file_path)
            if sig_type and sig_type != DocumentType.UNKNOWN:
                doc_type = sig_type

        # Check if OCR is needed
        needs_ocr = self.needs_ocr(file_path)

        # Estimate page count
        page_count = self._estimate_page_count(file_path, doc_type)

        # Detect encoding
        encoding = self.detect_encoding(file_path)

        # Attempt language detection for text-based files (skip images/PDFs)
        language = ""
        if not needs_ocr and doc_type not in (
            DocumentType.IMAGE_PNG, DocumentType.IMAGE_JPG, DocumentType.IMAGE_TIFF,
        ):
            try:
                sample = file_path.read_text(encoding=encoding, errors="replace")[:3000]
                language = self.detect_language(sample)
            except Exception:
                pass

        return IdentificationResult(
            doc_type=doc_type,
            mime_type=mime_type,
            language=language,
            encoding=encoding,
            needs_ocr=needs_ocr,
            page_count=page_count,
            text_size_estimate=file_path.stat().st_size,
            metadata={"file_path": str(file_path)},
        )

    def detect_language(self, text: str) -> str:
        """Detect language by scoring pattern matches normalized by text length.

        Uses a weighted approach: character-set languages (ko, zh, ja) get a base
        bonus since even a single match is highly diagnostic. Word-based languages
        are scored by density (matches / total words).
        """
        if not text or len(text.strip()) < 10:
            return "unknown"

        cleaned = text[:5000]  # Limit analysis window
        word_count = max(1, len(cleaned.split()))

        scores: dict[str, float] = {}
        match_counts: dict[str, int] = {}

        for lang, pattern in self.LANGUAGE_PATTERNS.items():
            matches = re.findall(pattern, cleaned, re.IGNORECASE)
            count = len(matches)
            match_counts[lang] = count

            if count == 0:
                continue

            # Character-set languages (CJK): any match is strongly diagnostic
            if lang in ("ko", "zh", "ja"):
                scores[lang] = count * 3.0
            else:
                # Word-density languages: score by proportional frequency
                density = count / word_count
                # Boost languages with short common words (more frequent hits)
                boost = {"en": 1.5, "fr": 1.2, "de": 1.2, "es": 1.2}.get(lang, 1.0)
                scores[lang] = density * boost

        if not scores:
            return "unknown"

        best_lang = max(scores, key=scores.get)  # type: ignore[arg-type]
        # Require either a reasonable density score OR multiple unambiguous matches
        # This handles both short and long texts correctly
        has_enough_matches = match_counts[best_lang] >= 2
        meets_threshold = scores[best_lang] >= 0.5
        if not (has_enough_matches or meets_threshold):
            return "unknown"
        return best_lang

    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding using common BOM signatures."""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(4)

            # Check BOM (Byte Order Mark)
            if raw.startswith(b"\xef\xbb\xbf"):
                return "utf-8-sig"
            elif raw.startswith(b"\xff\xfe\x00\x00"):
                return "utf-32-le"
            elif raw.startswith(b"\x00\x00\xfe\xff"):
                return "utf-32-be"
            elif raw.startswith(b"\xff\xfe"):
                return "utf-16-le"
            elif raw.startswith(b"\xfe\xff"):
                return "utf-16-be"

            # Try reading as utf-8
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    f.read(1024)
                return "utf-8"
            except UnicodeDecodeError:
                pass

            # Try reading as latin-1 (never fails)
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    f.read(1024)
                return "latin-1"
            except Exception:
                return "utf-8"
        except OSError:
            return "utf-8"

    def needs_ocr(self, file_path: Path) -> bool:
        """Determine if a file requires OCR processing."""
        extension = file_path.suffix.lower()
        doc_type = EXTENSION_TO_DOC_TYPE.get(extension, DocumentType.UNKNOWN)

        # Image files always need OCR
        if doc_type in (
            DocumentType.IMAGE_PNG,
            DocumentType.IMAGE_JPG,
            DocumentType.IMAGE_TIFF,
        ):
            return True

        # PDF may need OCR if it's scanned
        if doc_type == DocumentType.PDF:
            return self._pdf_needs_ocr(file_path)

        # Text-based files don't need OCR
        return False

    def _pdf_needs_ocr(self, file_path: Path) -> bool:
        """Check if a PDF file is likely scanned (needs OCR)."""
        try:
            from core.parsers import parse_pdf
            text, _ = parse_pdf(str(file_path))
            # If extracted text is very short, likely a scanned PDF
            return len(text.strip()) < 100
        except Exception:
            return True  # Assume OCR needed if we can't read it

    def _estimate_page_count(self, file_path: Path, doc_type: DocumentType) -> int:
        """Estimate page count based on file size and type."""
        file_size = file_path.stat().st_size

        # Rough estimates based on file size
        estimates: dict[DocumentType, int] = {
            DocumentType.PDF: file_size // 50_000,     # ~50KB per page
            DocumentType.DOCX: file_size // 25_000,     # ~25KB per page
            DocumentType.PPTX: max(file_size // 200_000, file_size // 50_000),
            DocumentType.TXT: max(1, file_size // 3_000),
        }

        # Image files = 1 page each
        if doc_type in (DocumentType.IMAGE_PNG, DocumentType.IMAGE_JPG, DocumentType.IMAGE_TIFF):
            return 1

        return max(1, estimates.get(doc_type, file_size // 50_000))

    def _check_file_signature(self, file_path: Path) -> Optional[DocumentType]:
        """Check file magic bytes for type identification."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)

            for signature, doc_type in self.FILE_SIGNATURES.items():
                if header.startswith(signature):
                    return doc_type

            # Check for text files (no binary signature)
            if self._is_likely_text(header):
                # Determine if it's CSV
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        first_line = f.readline().strip()
                    if "," in first_line or "\t" in first_line:
                        return DocumentType.CSV
                except Exception:
                    pass
                return DocumentType.TXT

            return None
        except OSError:
            return None

    def _is_likely_text(self, header: bytes) -> bool:
        """Check if bytes look like text (not binary)."""
        if not header:
            return False
        # Text files have mostly printable ASCII or UTF-8 sequences
        text_chars = sum(1 for b in header if 32 <= b <= 126 or b in (9, 10, 13))
        return text_chars / len(header) > 0.85

    def _guess_mime_type(self, file_path: Path) -> str:
        """Guess MIME type from extension."""
        import mimetypes
        mime, _ = mimetypes.guess_type(str(file_path))
        return mime or "application/octet-stream"