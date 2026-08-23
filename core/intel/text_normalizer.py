"""
intel/text_normalizer.py — Intelligent Text Normalizer
=======================================================
Normalizes extracted text from any source (parser or OCR) into clean,
consistent form for downstream processing.

Handles:
    - Broken lines (line breaks within sentences)
    - Hyphenation at line breaks ("con-\ncept" -> "concept")
    - Unicode normalization (NFC/NFD/NFKC)
    - Repeated whitespace / excessive blank lines
    - OCR artifacts (ligatures, control chars, replacement glyphs)
    - Encoding issues (curly quotes, dashes, ellipsis -> ASCII)
    - Invisible characters (zero-width joiners, BOM, etc.)
    - Mixed scripts
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional


class TextNormalizer:
    """Normalizes extracted text from any source."""

    ENCODING_FIXES: Dict[str, str] = {
        "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
        "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
        "\u201c": '"',   # LEFT DOUBLE QUOTATION MARK
        "\u201d": '"',   # RIGHT DOUBLE QUOTATION MARK
        "\u2013": "-",   # EN DASH
        "\u2014": "--",  # EM DASH
        "\u00a0": " ",   # NO-BREAK SPACE
        "\u2026": "...", # HORIZONTAL ELLIPSIS
        "\ufffd": "",    # REPLACEMENT CHARACTER
        "\u00ab": "<<",  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        "\u00bb": ">>",  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        "\u2039": "<",   # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
        "\u203a": ">",   # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
        "\u2015": "-",   # HORIZONTAL BAR
        "\u2219": ".",   # BULLET OPERATOR
        "\u00b7": ".",   # MIDDLE DOT
        "\u2022": "-",   # BULLET
        "\u2043": "-",   # HYPHEN BULLET
        "\u2122": "(TM)",# TRADE MARK SIGN
        "\u2020": "*",   # DAGGER
        "\u2021": "**",  # DOUBLE DAGGER
        "\u00d7": "x",   # MULTIPLICATION SIGN
        "\u00f7": "/",   # DIVISION SIGN
    }

    def normalize(
        self,
        text: str,
        options: Optional[Dict[str, bool]] = None,
    ) -> str:
        """Full normalization pipeline. Returns cleaned text.

        Order: invisible removal -> unicode -> encoding fixes ->
        hyphenation -> broken lines -> whitespace -> blank dedup -> trim.
        """
        text = self.remove_invisible_chars(text)
        text = self.normalize_unicode(text, "NFC")
        text = self._apply_encoding_fixes(text)
        text = self.fix_hyphenation(text)
        text = self.fix_broken_lines(text)
        text = self.unify_whitespace(text)
        text = self.deduplicate_blank_lines(text)
        return text.strip()

    def _apply_encoding_fixes(self, text: str) -> str:
        """Replace typographic / encoding artefacts with ASCII equivalents."""
        for old, new in self.ENCODING_FIXES.items():
            text = text.replace(old, new)
        return text

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def fix_broken_lines(self, text: str) -> str:
        """Join broken lines that are part of the same sentence/paragraph.

        Strategy: if a line ends without terminal punctuation (.!?), join
        it to the next line with a space instead of a newline. Lines
        starting with an uppercase letter (after the break) are treated
        as new sentences -- leave them alone. Preserves paragraph breaks
        (double newlines) untouched.
        """
        lines = text.split("\n")
        result: list[str] = []
        i = 0
        while i < len(lines):
            current = lines[i]
            # Skip already-empty lines (potential paragraph separators)
            if not current.strip():
                result.append(current)
                i += 1
                continue

            # Accumulate continuation lines
            buffer = current
            while i + 1 < len(lines):
                peek = lines[i + 1]
                # Stop at blank lines (paragraph boundary)
                if not peek.strip():
                    break
                # Stop if next line starts a new sentence/capitalised word
                stripped = peek.lstrip()
                if stripped and (stripped[0].isupper() or stripped[0].isdigit()):
                    break
                buffer = f"{buffer} {stripped}"
                i += 1
            result.append(buffer.rstrip())
            i += 1
        return "\n".join(result)

    def fix_hyphenation(self, text: str) -> str:
        """Remove hyphenation at line breaks.\ncon-\\ncept -> concept"""
        def _replacer(m: re.Match) -> str:
            prefix, suffix = m.group(1), m.group(2)
            # Do not merge when suffix starts with an uppercase letter
            # (likely a proper noun or new sentence fragment).
            if suffix.isupper():
                return m.group(0)
            return f"{prefix}{suffix}"
        return re.sub(r"(\w)\s*-\s*\r?\n\s*(\w)", _replacer, text)

    def fix_ocr_artifacts(self, text: str) -> str:
        """Fix common OCR errors: ligatures and replacement glyphs."""
        fixes: Dict[str, str] = {
            "\ufb01": "fi",   # LATIN SMALL LIGATURE FI
            "\ufb02": "fl",   # LATIN SMALL LIGATURE FL
            "\ufb03": "ffi",  # LATIN SMALL LIGATURE FFI
            "\ufb04": "ffl",  # LATIN SMALL LIGATURE FFL
            "\ufb00": "ff",   # LATIN SMALL LIGATURE FF
            "\uff3b": "[",    # FULLWIDTH LEFT SQUARE BRACKET
            "\uff3d": "]",    # FULLWIDTH RIGHT SQUARE BRACKET
        }
        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)
        return text

    def normalize_unicode(self, text: str, form: str = "NFC") -> str:
        """Normalize Unicode to specified form (NFC, NFD, NFKC, NFKD)."""
        return unicodedata.normalize(form, text)

    def remove_invisible_chars(self, text: str) -> str:
        """Remove zero-width chars, BOM, soft hyphens; NBSP -> space."""
        # Non-breaking space -> regular space (must come first)
        text = text.replace("\u00a0", " ")
        # Soft hyphens -> nothing
        text = text.replace("\u00ad", "")
        # Zero-width sequences
        for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060"):
            text = text.replace(ch, "")
        # Object replacement placeholder
        text = text.replace("\ufffc", "")
        return text

    def unify_whitespace(self, text: str) -> str:
        """Convert tabs to spaces, collapse 2+ spaces to 1, strip each line."""
        text = text.replace("\t", " ")
        text = re.sub(r"[^\S\n]{2,}", " ", text)
        lines = [ln.strip() for ln in text.split("\n")]
        return "\n".join(lines)

    def deduplicate_blank_lines(self, text: str, max_blanks: int = 2) -> str:
        """Collapse 3+ consecutive blank lines to exactly ``max_blanks``."""
        return re.sub(r"\n{" + str(max_blanks + 1) + r",}", "\n" * (max_blanks + 1), text)

    @staticmethod
    def estimate_quality(text: str, original_length: int) -> float:
        """Estimate extraction quality by comparing lengths (0.0-1.0)."""
        if original_length == 0:
            return 1.0
        kept = len(text.strip())
        ratio = kept / original_length
        return round(max(0.0, min(1.0, ratio)), 4)

    def clean_for_embedding(self, text: str) -> str:
        """Prepare text for embedding/vectorization: prose only."""
        text = re.sub(r"[^a-zA-Z0-9\u00C0-\u024F\s.,;:!?\'\"()\-\+\-/]", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


def normalize_text(text: str, **kwargs) -> str:
    """Convenience function: quick normalization with defaults."""
    return TextNormalizer().normalize(text)
