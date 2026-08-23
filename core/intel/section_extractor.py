"""
intel/section_extractor.py — Section Extractor
==================================================
Extracts logical document sections from parsed text.

Detects standard academic/professional sections:
    Abstract, Introduction, Background, Literature Review,
    Methodology, Methods, Data, Results, Findings, Discussion,
    Conclusion, Acknowledgments, References, Appendix, Supplementary,
    Figure Captions, Table Captions, Footnotes

Also handles non-standard sections by grouping by heading hierarchy.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

from core.intel.models import Section, SectionType


class SectionExtractor:
    """Extracts logical sections from document text."""

    # Canonical section name → SectionType mapping (case-insensitive).
    SECTION_PATTERNS: List[tuple[str, SectionType]] = [
        (r"\babstract\b", SectionType.ABSTRACT),
        (r"\bsummary\b", SectionType.ABSTRACT),

        (r"\bintroduction\b", SectionType.INTRODUCTION),
        (r"\binroduct\b", SectionType.INTRODUCTION),

        (r"\bbackground\b", SectionType.BACKGROUND),
        (r"\bliterature\s+review\b", SectionType.LITERATURE_REVIEW),
        (r"\brlated\s+(?:work|works)\b", SectionType.LITERATURE_REVIEW),
        (r"\bcontext\b", SectionType.BACKGROUND),

        (r"\bmethodology\b", SectionType.METHODOLOGY),
        (r"\bmethods\b", SectionType.METHODS),
        (r"\bmethdb?\b", SectionType.METHODS),
        (r"\bdatal?\s+collection\b", SectionType.DATA),
        (r"\bdatal?\s+sources?\b", SectionType.DATA),
        (r"\bbaterial[s]?\s*and\s*method[s]?\b", SectionType.METHODS),

        (r"\bresult[s]?\b", SectionType.RESULTS),
        (r"\bfinding[s]?\b", SectionType.FINDINGS),
        (r"\boutcome[s]?\b", SectionType.RESULTS),
        (r"\bempirical\s+results\b", SectionType.RESULTS),

        (r"\bdiscussion\b", SectionType.DISCUSSION),
        (r"\binterpretation\b", SectionType.DISCUSSION),
        (r"\banalys(?:i|s)\b", SectionType.DISCUSSION),
        (r"\bimplication[s]?\b", SectionType.DISCUSSION),

        (r"\bconclusion[b]?\b", SectionType.CONCLUSION),
        (r"\ben[d]\b", SectionType.CONCLUSION),
        (r"\bsummary\b", SectionType.CONCLUSION),

        (r"\bacnowledg[eé]ments?\b", SectionType.ACKNOWLEDGMENTS),

        (r"\breference[s]?\b", SectionType.REFERENCES),
        (r"\bbibliography\b", SectionType.REFERENCES),
        (r"\bworks\s+cited\b", SectionType.REFERENCES),

        (r"\bappendix[ex]?\b", SectionType.APPENDIX),
        (r"\bsupplementary\s+material\b", SectionType.SUPPLEMENTARY),
        (r"\baddditional\s+material\b", SectionType.SUPPLEMENTARY),

        (r"\bfigure\s+\d+", SectionType.FIGURE_CAPTION),
        (r"\bfig\.?\s+\d+", SectionType.FIGURE_CAPTION),
        (r"\btable\s+\d+", SectionType.TABLE_CAPTION),
        (r"\btab\.?\s+\d+", SectionType.TABLE_CAPTION),

        (r"(?<!\w)\d+[.)]\s", SectionType.FOOTNOTE),
    ]

    # Heading regex that catches numbered, plain, or bold headings at start of line.
    HEADING_RE = re.compile(
        r"^(?:#{1,6}\s+|\d+(?:\.[\d]*)*\s+|[•●–]\s+)?"  # optional prefix markers
        r"(.{3,100}?)\s*$",                                # heading text (non-greedy)
        re.MULTILINE | re.IGNORECASE,
    )

    def extract(self, text: str, headings: Optional[List[Dict]] = None) -> List[Section]:
        """Main extraction pipeline. Returns list of Sections."""
        if headings is not None:
            return self._extract_from_headings(text, headings)

        boundaries = self._find_section_boundaries(text)
        if not boundaries:
            return [Section(title="Full Document", type=SectionType.GENERAL)]

        sections: List[Section] = []
        for boundary in boundaries:
            sec_type = self._classify_heading(boundary["heading"]) or SectionType.GENERAL
            content = text[boundary["start"]:boundary["end"]].strip()
            word_count = len(content.split())

            sections.append(Section(
                title=boundary["heading"],
                type=sec_type,
                level=boundary.get("level", 1),
                word_count=word_count,
            ))

        return self._build_hierarchy(sections)

    def _extract_from_headings(self, text: str, headings: List[Dict]) -> List[Section]:
        """Build sections from pre-extracted heading info (page-level API)."""
        sections: List[Section] = []
        total_len = len(text)

        for i, h in enumerate(headings):
            h_start = int(h.get("top", 0))
            h_end = int(headings[i + 1]["top"]) if i + 1 < len(headings) else total_len
            sec_type = self._classify_heading(h.get("text", "")) or SectionType.GENERAL
            chunk = text[h_start:h_end].strip()
            sections.append(Section(
                title=h.get("text", ""),
                type=sec_type,
                level=int(h.get("level", 1)),
                page_start=int(h.get("page", -1)),
                word_count=len(chunk.split()),
            ))

        return self._build_hierarchy(sections)

    def _find_section_boundaries(self, text: str) -> List[Dict[str, Any]]:
        """Find where each section starts and ends based on heading patterns."""
        lines = text.split("\n")
        boundaries: List[Dict[str, Any]] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this line looks like a section heading.
            for pattern, sec_type in self.SECTION_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    # Infer heading level from leading spaces/markers.
                    indent = len(line) - len(line.lstrip())
                    level = 1 if indent == 0 else min(indent // 4 + 1, 6)
                    boundaries.append({
                        "heading": stripped,
                        "start": sum(len(l) + 1 for l in lines[:i]),
                        "end": 0,  # filled after loop
                        "level": level,
                        "type": sec_type,
                    })
                    break

        # Close last boundary at EOF; fill gaps.
        eof = len(text)
        for i, b in enumerate(boundaries):
            b["end"] = boundaries[i + 1]["start"] if i + 1 < len(boundaries) else eof

        return boundaries

    def _classify_heading(self, heading_text: str) -> Optional[SectionType]:
        """Classify a heading string into a canonical SectionType."""
        normalized = re.sub(r"[#①②③④⑤⑥⑦⑧⑨⑩·\-—]", " ", heading_text).strip()
        for pattern, sec_type in self.SECTION_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return sec_type
        return None

    def _build_hierarchy(self, sections: List[Section]) -> List[Section]:
        """Build nested subsection structure from flat section list."""
        if not sections:
            return sections

        result: List[Section] = []
        stack: List[tuple[int, Section]] = []  # (level, section)

        for sec in sections:
            # Pop stack until we find a parent at lower level.
            while stack and stack[-1][0] >= sec.level:
                stack.pop()

            if stack:
                stack[-1][1].subsections.append(sec)
            else:
                result.append(sec)

            stack.append((sec.level, sec))

        return result

    @staticmethod
    def _extract_appendices(text: str) -> List[Section]:
        """Separately identify appendix/supplementary sections."""
        appendix_sections: List[Section] = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r"^(appendix|supplementary)", stripped, re.IGNORECASE):
                # Collect everything until next top-level section or EOF.
                end_line = i
                for j in range(i + 1, len(lines)):
                    ls = lines[j].strip()
                    if ls and re.match(r"^(abstract|introduction|methods|results|discussion|conclusion|references)", ls, re.IGNORECASE):
                        break
                    end_line = j

                content = "\n".join(lines[i:end_line + 1]).strip()
                appendix_sections.append(Section(
                    title=re.sub(r"^#\s*", "", stripped),
                    type=SectionType.APPENDIX,
                    word_count=len(content.split()),
                ))

        return appendix_sections

    @staticmethod
    def detect_irmad(sections: List[Section]) -> bool:
        """Return True when methods+results+discussion are all present."""
        types_present = {s.type for s in sections}
        return (SectionType.METHODS in types_present
                or SectionType.METHODOLOGY in types_present) and \
               SectionType.RESULTS in types_present and \
               SectionType.DISCUSSION in types_present


def extract_sections(text: str, headings: Optional[List[Dict]] = None) -> List[Section]:
    """Convenience function: quick section extraction."""
    return SectionExtractor().extract(text, headings)
