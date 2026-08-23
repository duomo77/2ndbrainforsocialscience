"""
intel/figure_detector.py — Figure Detection
==============================================
Detects images, charts, graphs, diagrams, and equations in document text.

Finds by analyzing text patterns that indicate figure references and embedded content:
    - "Figure X:", "Fig. X", "Figure X caption"
    - Image markers like [image], (image), <!-- image -->
    - Chart/graph description blocks
    - Equation blocks ($...$, $$...$$)
    - ASCII art / diagram placeholders
    - Cross-references: "(see Fig. 3)", "(Figure 2)"

Stores references for future multimodal processing.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.intel.models import FigureBlock


class FigureDetector:
    """Detects figures/charts/diagrams/equations in document text."""

    FIGURE_REFERENCE_PATTERNS = [
        r"\b(Figure|Fig\.?)\s*[\dIVXLC]+\s*:\s*",
        r"\b(see\s+)?(?:Figure|Fig\.?)\s*[\dIVXLC]+\b",
        r"\b[fi]g(?:ure)?\.?\s*\w+\s*[=:]\s*.{3,100}\b",
        r"\[(?:image|img|photo|graphic)\s*(?:\d+)?\]",
        r"<!--\s*(?:image|img|picture)\s*(?:\d*)?\s*-->",
    ]

    # Captures kind by keyword presence
    _KIND_MAP = {
        "chart": "chart", "diagram": "diagram", "graph": "graph",
        "scheme": "diagram", "flowchart": "diagram",
        "illustration": "image", "photo": "image", "photograph": "image",
        "picture": "image", "drawing": "image", "sketch": "image",
    }

    def detect(self, text: str, file_path: Optional[Path | str] = None) -> List[FigureBlock]:
        """Full detection pipeline. Returns list of FigureBlock."""
        results: List[FigureBlock] = []

        # 1. Explicit figure references with optional captions
        for ref_pos, match in enumerate(re.finditer(
                r"\b(?:Figure|Fig\.?)\s*[\dIVXLC]+", text)):
            start = match.start()
            caption, end_pos = self._extract_caption(text, match.end())
            kind = self._infer_kind(text[start:end_pos])
            results.append(FigureBlock(
                kind=kind,
                caption=caption.strip(),
                page_number=-1,
                metadata={"file_path": str(file_path)} if file_path else {},
            ))

        # 2. Standalone equation blocks (display-mode)
        for eq_match in re.finditer(r"\$\$(.+?)\$\$", text, re.DOTALL):
            eq_text = eq_match.group(1).strip()
            if eq_text:
                caption, _ = self._extract_caption(text, eq_match.end())
                results.append(FigureBlock(
                    kind="equation",
                    caption=caption.strip(),
                    metadata={
                        "latex_raw": eq_text,
                        "file_path": str(file_path) if file_path else None,
                    },
                ))

        # 3. Equation environment blocks
        for env_match in re.finditer(
                r"\\begin\{(equation|align|align\*|eqnarray)\}(.*?)\\end\{\1\}",
                text, re.DOTALL | re.IGNORECASE):
            env_text = env_match.group(2).strip()
            caption, _ = self._extract_caption(text, env_match.end())
            results.append(FigureBlock(
                kind="equation",
                caption=caption.strip(),
                metadata={
                    "latex_raw": f"\\begin{{{env_match.group(1)}}}{env_text}\\end{{{env_match.group(1)}}}",
                    "environment": env_match.group(1),
                    "file_path": str(file_path) if file_path else None,
                },
            ))

        # 4. Bracketed image markers ([image], <img src="...">)
        for m in re.finditer(r"\[image[^]]*\]|<img\b[^>]*src=[\"']([^\"']*)[\"']", text):
            alt_text = m.group(0)
            results.append(FigureBlock(
                kind="image",
                alt_text=alt_text.strip("[]<>"),
                metadata={"file_path": str(file_path) if file_path else None},
            ))

        # 5. ASCII-art / diagram regions bounded by === or +--- lines
        for region in self._find_ascii_art_regions(text):
            results.append(FigureBlock(
                kind="diagram",
                metadata=dict(region, file_path=str(file_path) if file_path else None),
            ))

        return results

    def _find_figure_references(self, text: str) -> List[Dict[str, Any]]:
        """Find all Figure/Chart/Diagram references in text."""
        refs: List[Dict[str, Any]] = []
        for pat in self.FIGURE_REFERENCE_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                refs.append({"match": m.group(), "span": m.span()})
        return sorted(refs, key=lambda r: r["span"][0])

    def _extract_caption(self, text: str, reference_pos: int) -> tuple[str, int]:
        """Extract caption text following a figure reference."""
        # Grab up to the next double-newline, period followed by newline, or ~300 chars
        block = text[reference_pos:reference_pos + 300]
        # Split on paragraph breaks or end-of-line
        segments = re.split(r"\n\s*\n|\.\n", block)
        if segments:
            caption = segments[0].strip()
            # Trim at reasonable sentence boundaries
            cut = min(len(caption), 300)
            end = caption.rfind(".", 0, cut)
            if end > cut // 2:
                caption = caption[:end + 1]
            return caption, reference_pos + len(caption)
        return text[reference_pos:reference_pos + 100].strip(), reference_pos + 100

    def _find_equation_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Find LaTeX/math display equations."""
        eqs: List[Dict[str, Any]] = []
        for m in re.finditer(r"\$\$(.+?)\$\$", text, re.DOTALL):
            eqs.append({"latex": m.group(1).strip(), "span": m.span()})
        for m in re.finditer(
                r"\\begin\{(equation|align|align\*|eqnarray)\}(.*?)\\end\{\1\}",
                text, re.DOTALL | re.IGNORECASE):
            eqs.append({"latex": m.group(0).strip(), "span": m.span(), "env": m.group(1)})
        return sorted(eqs, key=lambda e: e["span"][0])

    def _find_ascii_art_regions(self, text: str) -> List[Dict[str, Any]]:
        """Detect ASCII art/diagram regions bounded by === or +--- lines."""
        regions: List[Dict[str, Any]] = []
        border_re = re.compile(r"^[+=\-]{3,}$")
        current_lines: List[str] = []
        in_region = False

        for lineno, line in enumerate(text.splitlines()):
            if not in_region:
                if border_re.match(line.strip()):
                    in_region = True
                    current_lines = [line]
            else:
                current_lines.append(line)
                if border_re.match(line.strip()):
                    regions.append({
                        "ascii_art": "\n".join(current_lines),
                        "line_count": len(current_lines),
                    })
                    in_region = False
                    current_lines = []
        return regions

    def count_references_in_text(self, text: str) -> int:
        """Quick count of figure references."""
        return sum(1 for _ in re.finditer(
            r"\b(Figure|Fig\.?)[^a-zA-Z\d]", text, re.IGNORECASE))

    @staticmethod
    def _infer_kind(text: str) -> str:
        lower = text.lower()
        for kw, kind in FigureDetector._KIND_MAP.items():
            if kw in lower:
                return kind
        return "figure"


def detect_figures(text: str, file_path: Optional[Path | str] = None) -> List[FigureBlock]:
    """Convenience function: quick figure detection."""
    return FigureDetector().detect(text)
