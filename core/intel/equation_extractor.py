r"""
intel/equation_extractor.py — Equation Extraction
====================================================
Identifies and extracts mathematical expressions from documents.

Handles:
    - Inline math: $x^2 + y^2 = z^2$
    - Display math: $$ ... $$
    - LaTeX environments: \begin{equation}...\end{equation}, \begin{align}...\end{align}
    - Numbered equations: Eq. (3), (3.1)
    - Plain text math: integral, summation symbols

Store:
    - Raw LaTeX representation
    - Plain text fallback
    - Location (page, line)
    - Context (text before/after)
    - Reference ID for cross-referencing
"""

from __future__ import annotations
import re
from typing import List, Optional

from core.intel.models import EquationBlock


_MATH_TOKENS = r"[\+\-\*\/=\<>]\s*(?:\\)?[a-zA-Z]|\\(?:partial|sum|int|prod|lim|infty|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega)"


class EquationExtractor:
    """Extracts mathematical expressions from document text."""

    DISPLAY_MATH_PATTERNS = [r"\$\$(.+?)\$\$", r"\\\[(.+?)\\\]"]
    ENV_MATH_PATTERN = (
        r"\\begin\{(equation|align(?:\*)?|eqnarray|gather(?:\*)?)\}"
        r"(.*?)\\end\{\1\}"
    )
    INLINE_MATH_PATTERN = r"\$(.+?)\$"

    EQUATION_REF_PATTERNS = [
        r"(?:Eq\.?|Equation)\s*[\(\s](\d+(?:\.\d+)*)[\)\s]",
    ]

    def extract(self, text: str, page_number: int = -1) -> List[EquationBlock]:
        """Main extraction pipeline. Returns list of EquationBlock."""
        blocks: List[EquationBlock] = []
        consumed_spans: List[tuple] = []  # track already-extracted spans to avoid duplicates

        # 1. Display-level equations ($$ ... $$, \[ ... \])
        blocks.extend(self._extract_display_equations(text, page_number, consumed_spans))

        # 2. LaTeX environment equations (\begin{equation}...)
        blocks.extend(self._extract_env_equations(text, page_number, consumed_spans))

        # 3. Inline equations ($...$) — only ones not inside display blocks
        blocks.extend(self._extract_inline_equations(text, page_number, consumed_spans))

        return sorted(blocks, key=lambda b: b.page_number)

    def _extract_display_equations(
        self, text: str, start_page: int, consumed: List[tuple],
    ) -> List[EquationBlock]:
        """Extract display-level equations ($$ ... $$, \\[ ... \\])."""
        results: List[EquationBlock] = []
        for pattern in self.DISPLAY_MATH_PATTERNS:
            for m in re.finditer(pattern, text, re.DOTALL):
                latex_raw = m.group(1).strip()
                if not self.is_likely_math(latex_raw):
                    continue
                before, after = self._find_context(text, m.start())
                ref_id = self._find_reference_id(text, m.end())
                eq_type = "numbered" if ref_id else "display"
                results.append(EquationBlock(
                    latex=latex_raw,
                    type=eq_type,
                    page_number=start_page,
                    context_before=before,
                    context_after=after,
                    reference_id=ref_id,
                ))
                consumed.append(m.span())
        return results

    def _extract_env_equations(
        self, text: str, start_page: int, consumed: List[tuple],
    ) -> List[EquationBlock]:
        """Extract \\begin{equation} ... \\end{equation} blocks."""
        results: List[EquationBlock] = []
        for m in re.finditer(self.ENV_MATH_PATTERN, text, re.DOTALL | re.IGNORECASE):
            env_name = m.group(1)
            latex_raw = m.group(2).strip()
            if not self.is_likely_math(latex_raw):
                continue
            before, after = self._find_context(text, m.start())
            ref_id = self._find_reference_id(text, m.end())
            eq_type = "numbered" if ref_id else "display"
            results.append(EquationBlock(
                latex=f"\\begin{{{env_name}}}{latex_raw}\\end{{{env_name}}}",
                type=eq_type,
                page_number=start_page,
                context_before=before,
                context_after=after,
                reference_id=ref_id,
                metadata={"environment": env_name},
            ))
            consumed.append(m.span())
        return results

    def _extract_inline_equations(
        self, text: str, start_page: int, consumed: List[tuple],
    ) -> List[EquationBlock]:
        """Extract inline equations ($...$), excluding those inside display blocks."""
        results: List[EquationBlock] = []
        for m in re.finditer(self.INLINE_MATH_PATTERN, text):
            latex_raw = m.group(1).strip()
            if not self.is_likely_math(latex_raw):
                continue
            # Skip if this span overlaps any already-consumed region
            if any(s <= m.start() < e or s < m.end() <= e for s, e in consumed):
                continue
            before, after = self._find_context(text, m.start())
            ref_id = self._find_reference_id(text, m.end())
            results.append(EquationBlock(
                latex=latex_raw,
                type="numbered" if ref_id else "inline",
                page_number=start_page,
                context_before=before,
                context_after=after,
                reference_id=ref_id,
            ))
            consumed.append(m.span())
        return results

    @staticmethod
    def _find_context(text: str, eq_start: int, context_chars: int = 200) -> tuple[str, str]:
        """Get text context before and after an equation."""
        ctx_len = min(context_chars, eq_start)
        before = text[max(0, eq_start - ctx_len):eq_start].rstrip()
        remaining = len(text) - eq_start
        ctx_end = min(context_chars, remaining)
        after_text = text[eq_start:eq_start + ctx_end].lstrip() if eq_start < len(text) else ""
        return before[:context_chars], after_text[:context_chars]

    @staticmethod
    def _find_reference_id(text: str, eq_end: int) -> Optional[str]:
        """Look for equation reference ID nearby: '(3)', 'Eq. (3)'."""
        search_window = text[eq_end:eq_end + 50]
        for pat in EquationExtractor.EQUATION_REF_PATTERNS:
            m = re.search(pat, search_window)
            if m:
                return m.group(0).strip()
        # Also look behind (sometimes refs appear before the equation)
        search_back = text[max(0, eq_end - 50):eq_end]
        for pat in EquationExtractor.EQUATION_REF_PATTERNS:
            m = re.search(pat, search_back)
            if m:
                return m.group(0).strip()
        return None

    @staticmethod
    def is_likely_math(expr: str) -> bool:
        """Check if extracted expression looks like math notation."""
        if expr.startswith("http://") or expr.startswith("https://"):
            return False
        if len(expr) < 3:
            return False
        return len(re.findall(_MATH_TOKENS, expr)) >= 2

    @staticmethod
    def estimate_latex_quality(latex_str: str) -> float:
        """Estimate how complete/reliable the LaTeX extraction is."""
        if not latex_str:
            return 0.0
        score = 0.0
        checks = [
            r"\\begin\{.*?\\end\{.*?\}",
            r"[\^\_{}]",
            r"\\(?:frac|sqrt|overset|underset)",
        ]
        for pattern in checks:
            if re.search(pattern, latex_str):
                score += 1.0 / len(checks)
        unclosed = latex_str.count("$") % 2 if latex_str.count("$") > 0 else 0
        if unclosed:
            score -= 0.2
        return max(0.0, min(1.0, score))


def extract_equations(text: str, page_number: int = -1) -> List[EquationBlock]:
    """Convenience function: quick equation extraction."""
    return EquationExtractor().extract(text, page_number)
