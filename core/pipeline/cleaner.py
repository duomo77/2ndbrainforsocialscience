"""
pipeline/cleaner.py — Document Cleaning & Normalization Service
=================================================================
Cleans extracted text: removes artifacts, normalizes whitespace, fixes encoding.
"""

from __future__ import annotations

import re
import unicodedata

from core.pipeline.interfaces import DocumentCleaner


class DocumentCleanerImpl(DocumentCleaner):
    """Default document cleaner implementation."""

    # Control characters to remove (except newline, tab)
    CONTROL_CHARS = "".join(
        chr(i) for i in range(32) if chr(i) not in ("\n", "\t", "\r")
    )

    def clean(self, text: str, doc_type: str = "unknown") -> str:
        """Clean extracted text by removing artifacts."""
        if not text:
            return ""

        # Remove null bytes
        text = text.replace("\x00", "")

        # Remove control characters
        text = text.translate(str.maketrans("", "", self.CONTROL_CHARS))

        # Fix common encoding artifacts
        text = self._fix_encoding_artifacts(text)

        # Unify line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive blank lines
        text = re.sub(r"\n{4,}", "\n\n\n", text)

        # Unify quotation marks
        text = self._normalize_quotes(text)

        # Type-specific cleaning
        if doc_type in ("pdf", "image_png", "image_jpg", "image_tiff"):
            text = self._clean_ocr_text(text)
        elif doc_type == "html":
            text = self._clean_html_text(text)
        elif doc_type == "csv":
            text = self._clean_csv_text(text)

        # Trim leading/trailing whitespace
        text = text.strip()

        return text

    def normalize(self, text: str) -> str:
        """Normalize text to Unicode NFC for consistent downstream processing."""
        return unicodedata.normalize("NFC", text)

    def _fix_encoding_artifacts(self, text: str) -> str:
        """Fix common text encoding artifacts."""
        replacements = {
            "\u2018": "'",   # Left single quote
            "\u2019": "'",   # Right single quote
            "\u201c": '"',   # Left double quote
            "\u201d": '"',   # Right double quote
            "\u2013": "-",   # En dash
            "\u2014": "--",  # Em dash
            "\u00a0": " ",   # Non-breaking space
            "\u2026": "...", # Ellipsis
            "\ufffd": "",    # Replacement character
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _normalize_quotes(self, text: str) -> str:
        """Unify quotation marks to straight quotes."""
        text = text.replace("\u201c", '"').replace("\u201d", '"')  # Curly double
        text = text.replace("\u2018", "'").replace("\u2019", "'")  # Curly single
        text = text.replace("\u00ab", '"').replace("\u00bb", '"')  # Guillemets
        return text

    def _clean_ocr_text(self, text: str) -> str:
        """Clean OCR-specific artifacts."""
        # Remove page numbers (standalone numbers on their own line)
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

        # Fix common OCR errors
        ocr_fixes = {
            "|": "I",
            "ﬁ": "fi",
            "ﬂ": "fl",
            "ﬀ": "ff",
            "ﬃ": "ffi",
            "ﬄ": "ffl",
        }
        for wrong, correct in ocr_fixes.items():
            text = text.replace(wrong, correct)

        # Remove hyphenation at line breaks ("con-\ncept" → "concept")
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

        return text

    def _clean_html_text(self, text: str) -> str:
        """Clean HTML-extracted text."""
        # Remove remaining HTML entities
        import html
        text = html.unescape(text)
        # Remove excessive whitespace from HTML layout
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def _clean_csv_text(self, text: str) -> str:
        """Clean CSV content formatting."""
        # CSV cleaning is minimal — preserve structure
        return text.strip()


def clean_text(text: str, doc_type: str = "unknown") -> str:
    """Convenience function: clean text with default cleaner."""
    cleaner = DocumentCleanerImpl()
    cleaned = cleaner.clean(text, doc_type)
    return cleaner.normalize(cleaned)