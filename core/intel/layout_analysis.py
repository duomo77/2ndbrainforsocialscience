"""
intel/layout_analysis.py — Page Layout Analyzer
==================================================
Detects headings, paragraphs, lists, tables, footnotes,
headers/footers, page numbers, multi-column layout, reading order.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional


class LayoutAnalyzer:
    """Analyzes document layout from extracted text."""

    LIST_MARKERS = [
        (r"^\s*[-*+]\s+", "bullet"),
        (r"^\s*\d+\.\s+", "ordered"),
        (r"^\s*[ivxlcdm]+\.\s+", "roman"),
        (r"^[A-Z]\.\s+", "lettered"),
    ]

    FOOTNOTE_PATTERNS = [
        r"(?i)^footnote[s]?\b", r"(?i)^note[s]?:\b",
        r"\[\^?\d+\]", r"^\d+[a-d]?\.",
    ]

    def analyze(self, text: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Full layout analysis pipeline. Returns structured layout info."""
        heads = self.detect_headings(text)
        paras = self.detect_paragraphs(text)
        lists = self.detect_lists(text)
        tbls = self.detect_tables_structure(text)
        fns = self.detect_footnotes(text)
        hf = self.detect_headers_footers(text)
        pnums = self.detect_page_numbers(text)
        mc = self.detect_multicolumn(text)

        info: Dict[str, Any] = {
            "headings": heads, "paragraphs": paras, "lists": lists,
            "tables": tbls, "footnotes": fns,
            "headers_footers": hf, "page_numbers": pnums,
            "multi_column": mc,
        }
        info["reading_order"] = self.determine_reading_order(info)
        info["total_elements"] = sum(len(v) for k, v in info.items()
                                     if isinstance(v, list) and k != "reading_order")
        return info

    def detect_headings(self, text: str) -> List[Dict[str, Any]]:
        """Find headings via markdown (#), numbered (3. Intro), title-case patterns."""
        lines = text.split("\n")
        results = []
        for i, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            # Markdown
            m = re.match(r"^(#{1,6})\s+(.+)$", s)
            if m:
                results.append({"line_number": i, "level": len(m.group(1)),
                                "text": m.group(2).strip(), "is_confirmed_heading": True,
                                "marker_type": "markdown"})
                continue
            # Numbered heading
            m = re.match(r"^(\d+(?:\.\d+)*)\.\s+([A-Z].{3,99}?)$", s)
            if m:
                results.append({"line_number": i,
                                "level": 1 + m.group(1).count("."),
                                "text": m.group(2), "is_confirmed_heading": True,
                                "marker_type": "numbered"})
                continue
            # Title-case: >= 3 words, 3-80 chars, majority capitalized
            if 3 <= len(s) <= 80:
                words = s.split()
                if len(words) >= 3:
                    ratio = sum(1 for w in words if w[0].isupper() and len(w) > 1) / max(len(words), 1)
                    if ratio > 0.6:
                        results.append({"line_number": i, "level": 2,
                                        "text": s, "is_confirmed_heading": False,
                                        "marker_type": "title_case"})
        return results

    def detect_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """Split text into blocks separated by blank lines."""
        blocks = re.split(r"\n{2,}", text)
        paras = []
        for b in blocks:
            s = b.strip()
            if not s:
                continue
            lines = s.split("\n")
            wc = len(s.split())
            paras.append({"index": len(paras), "word_count": wc,
                          "line_count": len(lines), "text": s,
                          "is_caption": len(lines) == 1 and len(s) < 15})
        return paras

    def detect_lists(self, text: str) -> List[Dict[str, Any]]:
        """Detect runs of >= 2 consecutive list items grouped by type."""
        lines = text.split("\n")
        blocks: List[Dict[str, Any]] = []
        run: List[Dict[str, Any]] = []
        cur_type: Optional[str] = None

        for i, line in enumerate(lines):
            mt = None
            for pat, lt in self.LIST_MARKERS:
                if re.match(pat, line):
                    mt = lt; break
            if mt:
                if cur_type is None:
                    cur_type, run = mt, []
                elif cur_type != mt:
                    if len(run) >= 2:
                        blocks.append({"type": cur_type,
                            "start_line": run[0]["line_number"],
                            "items": run, "item_count": len(run)})
                    cur_type, run = mt, []
                run.append({"line_number": i, "text": line.strip()})
            else:
                if run and len(run) >= 2:
                    blocks.append({"type": cur_type,
                        "start_line": run[0]["line_number"],
                        "items": run, "item_count": len(run)})
                run, cur_type = [], None

        if run and len(run) >= 2:
            blocks.append({"type": cur_type,
                "start_line": run[0]["line_number"],
                "items": run, "item_count": len(run)})
        return blocks

    def detect_tables_structure(self, text: str) -> List[Dict[str, Any]]:
        """Detect table-like blocks via pipes, tabs, or ASCII art borders."""
        lines = text.split("\n")
        tables: List[Dict[str, Any]] = []
        cand: List[int] = []

        for i, line in enumerate(lines):
            hit = False
            if "|" in line:
                cells = [c for c in line.split("|") if c.strip()]
                if len(cells) >= 3:
                    cand.append(i); hit = True
            elif "\t" in line:
                cells = [c for c in line.split("\t") if c.strip()]
                if len(cells) >= 3:
                    cand.append(i); hit = True
            elif re.search(r"[-=]{3,}[+][-=]{3,}", line):
                cand.append(i); hit = True

            if not hit:
                if cand and len(cand) >= 2:
                    cols = set()
                    for ci in cand:
                        cl = lines[ci]
                        if "|" in cl:
                            cols.add(len([c for c in cl.split("|") if c.strip()]))
                        elif "\t" in cl:
                            cols.add(len([c for c in cl.split("\t") if c.strip()]))
                    if len(cols) == 1 and min(cols) >= 3:
                        first = lines[cand[0]]
                        det = "pipe" if "|" in first else "tab" if "\t" in first else "ascii"
                        tables.append({"rows": len(cand), "columns": cols.pop(),
                                       "row_start": cand[0], "row_end": cand[-1],
                                       "delimiter_type": det})
                cand = []
        return tables

    def detect_footnotes(self, text: str) -> List[Dict[str, Any]]:
        """Detect footnote references ([1], [^1]) and footnote blocks."""
        lines = text.split("\n")
        results: List[Dict[str, Any]] = []
        fn_lines: List[int] = []

        for i, line in enumerate(lines):
            s = line.strip()
            if any(re.match(p, s) for p in self.FOOTNOTE_PATTERNS[:2]):
                fn_lines.clear()
            for ref in re.findall(r"\[\^?\d+\]", s):
                results.append({"type": "inline_reference", "reference": ref,
                                "line_number": i, "context": s[:100]})
            if re.match(r"^\d+[a-d]?\.\s.{10}", s):
                results.append({"type": "block_footnote", "text": s,
                                "line_number": i})
                fn_lines.append(i)

        if fn_lines:
            results.append({"type": "footnote_section", "lines": fn_lines})
        return results

    def detect_headers_footers(self, text: str) -> List[Dict[str, Any]]:
        """Identify repeated top/bottom line patterns as headers or footers."""
        lines = text.split("\n")
        if len(lines) < 4:
            return []

        n = min(10, len(lines) // 4)
        top_d: Dict[str, int] = {}; bot_d: Dict[str, int] = {}
        cnt = 0
        for i, l in enumerate(lines):
            if cnt >= n: break
            s = l.strip()
            if s: top_d[s] = i; cnt += 1

        cnt = 0
        for i in range(len(lines) - 1, -1, -1):
            if cnt >= n: break
            s = lines[i].strip()
            if s: bot_d[s] = i; cnt += 1

        seen = set(); out = []
        for tv, ti in top_d.items():
            if tv in bot_d and tv not in seen:
                bi = bot_d[tv]; mid = len(lines) // 2
                out.append({"text": tv, "region": "header" if bi < mid else "footer",
                            "top_line": ti, "bottom_line": bi}); seen.add(tv)
        return out

    def detect_page_numbers(self, text: str) -> List[int]:
        """Find page numbers: standalone digits, 'Page X', Roman numerals."""
        lines = text.split("\n")
        values: List[int] = []
        roman = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

        for line in lines:
            s = line.strip()
            m = re.fullmatch(r"\d{1,4}", s)
            if m:
                v = int(s)
                if 0 < v <= 9999: values.append(v); continue
            m = re.search(r"(?i)\bpage\s+(\d+)\b", s)
            if m: values.append(int(m.group(1))); continue
            if re.fullmatch(r"[IVXLCDM]+", s):
                total, prev = 0, 0
                for ch in reversed(s.upper()):
                    v = roman.get(ch, 0)
                    total -= v if v < prev else v
                    prev = v
                if total > 0: values.append(total)
        return values

    def detect_multicolumn(self, text: str) -> bool:
        """Heuristic: short avg line length + frequent mid-sentence breaks."""
        ne = [l for l in text.split("\n") if l.strip()]
        if len(ne) < 10: return False
        avg = sum(len(l.strip()) for l in ne) / len(ne)
        abrupt = sum(1 for l in ne if not re.search(r"[.,;:?!\)]\s*$", l.strip()))
        ratio = abrupt / max(len(ne), 1)
        return avg < 50 and ratio > 0.7

    def determine_reading_order(self, layout_info: Dict[str, Any]) -> List[str]:
        """Sort elements by their estimated position in the document."""
        events: List[tuple] = []
        for h in layout_info.get("headings", []):
            events.append((h["line_number"], "heading"))
        pos = 0
        for p in layout_info.get("paragraphs", []):
            events.append((pos, "paragraph")); pos += p.get("word_count", 0)
        for li in layout_info.get("lists", []):
            events.append((li.get("start_line", 0), "list"))
        for t in layout_info.get("tables", []):
            events.append((t["row_start"], "table"))
        for f in layout_info.get("footnotes", []):
            ln = f.get("line_number", 9999) if isinstance(f, dict) else 9999
            events.append((ln, "footnote"))
        return [t for _, t in sorted(events)]


def layout_analyze(text: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function: quick layout analysis."""
    return LayoutAnalyzer().analyze(text, file_path)
