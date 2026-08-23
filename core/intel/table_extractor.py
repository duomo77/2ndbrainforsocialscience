"""
intel/table_extractor.py — Table Extraction
==============================================
Extracts structured tables from document text while preserving:
    - Rows, Columns, Headers
    - Merged Cells (rowspan, colspan)
    - Cell Coordinates
    - Export formats: JSON, CSV, Markdown

Supports pipe-delimited, tab-separated, and ASCII-art table formats.
"""

from __future__ import annotations
import csv
import io
import json
import re
from typing import Dict, List, Optional, Tuple

from core.intel.models import TableBlock


class TableExtractor:
    """Extracts tables from parsed document text."""

    PIPE_ROW_RE = re.compile(r"^\s*\|[\s\w][\s\S]*?\|\s*$")
    BORDER_ROW_RE = re.compile(r"^[\s+-]+[+][-+]*[+][\s+-]*$")
    TSV_ROW_RE = re.compile(r"^\t.{2,}\t.*$")

    def extract(self, text: str) -> List[TableBlock]:
        """Find and extract all tables from text. Returns list of TableBlock."""
        regions = self._detect_table_regions(text)
        if not regions:
            return []

        lines = text.split("\n")
        tables: List[TableBlock] = []

        for start_line, end_line in regions:
            chunk_lines = lines[start_line:end_line + 1]
            if len(chunk_lines) < 2:
                continue  # Too small to be a table.

            table = self._classify_and_parse(chunk_lines)
            if table is not None:
                tables.append(table)

        return tables

    def _detect_table_regions(self, text: str) -> List[Tuple[int, int]]:
        """Identify line ranges that contain tables."""
        lines = text.split("\n")
        regions: List[Tuple[int, int]] = []
        in_region = False
        region_start = 0
        contiguous = 0

        for i, line in enumerate(lines):
            is_pipe = bool(self.PIPE_ROW_RE.match(line))
            is_border = bool(self.BORDER_ROW_RE.match(line))
            is_tsv = bool(self.TSV_ROW_RE.match(line))

            if is_pipe or is_border or is_tsv:
                if not in_region:
                    region_start = i
                    in_region = True
                    contiguous = 0
                contiguous += 1
            else:
                if in_region and contiguous >= 2:  # minimum 2 data lines.
                    regions.append((region_start, i - 1))
                elif in_region and contiguous == 1:
                    # Could be a single-border row spanning multi-column cells;
                    # extend by looking ahead for more content rows.
                    peek_end = i
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if self.PIPE_ROW_RE.match(lines[j]) or self.BORDER_ROW_RE.match(lines[j]):
                            peek_end = j
                        else:
                            break
                    regions.append((region_start, peek_end))
                in_region = False
                contiguous = 0

        if in_region and contiguous >= 2:
            regions.append((region_start, len(lines) - 1))

        return regions

    def _classify_and_parse(self, lines: List[str]) -> Optional[TableBlock]:
        """Determine table format and parse it."""
        pipe_rows = sum(1 for l in lines if self.PIPE_ROW_RE.match(l))
        border_rows = sum(1 for l in lines if self.BORDER_ROW_RE.match(l))

        if pipe_rows > 0 and pipe_rows >= border_rows:
            return self._parse_pipe_table(lines)
        elif border_rows > 0:
            return self._parse_ascii_table(lines)
        else:
            return self._parse_tabular_table(lines)

    def _parse_pipe_table(self, lines: List[str]) -> TableBlock:
        """Parse pipe | delimited table format."""
        rows: List[List[str]] = []

        for line in lines:
            if self.BORDER_ROW_RE.match(line):
                continue  # skip separator rows like |-|-|-|

            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if any(c for c in cells):  # skip fully-empty rows.
                rows.append(cells)

        if not rows:
            return TableBlock()

        headers = rows[0]
        data = rows[1:]

        # Detect merged cells via continuation markers in first data row.
        merged: List[tuple] = []
        for r_idx, row in enumerate(data):
            for c_idx, cell in enumerate(row):
                if cell in ("...", "-", "~"):
                    merged.append((r_idx + 1, c_idx, r_idx + 1, c_idx + 1))

        block = TableBlock(
            headers=headers,
            cells=[[c for c in row] for row in data],
            row_count=len(data),
            col_count=max(len(r) for r in ([headers] + data)) if data else 0,
            merged_cells=merged,
        )
        return block

    def _parse_tabular_table(self, lines: List[str]) -> TableBlock:
        """Parse tab-or-whitespace separated table format."""
        rows: List[List[str]] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Try tab first, then collapse multiple spaces.
            if "\t" in stripped:
                cells = [c.strip() for c in stripped.split("\t")]
            else:
                cells = [c.strip() for c in re.split(r"\s{2,}", stripped)]
            if any(c for c in cells):
                rows.append(cells)

        if not rows:
            return TableBlock()

        headers = rows[0]
        data = rows[1:]

        block = TableBlock(
            headers=headers,
            cells=data,
            row_count=len(data),
            col_count=max((len(r) for r in rows), default=0),
        )
        return block

    def _parse_ascii_table(self, lines: List[str]) -> TableBlock:
        """Parse ASCII art bordered table format (+---+---+)."""
        # Strip border characters to get raw cell content.
        rows: List[List[str]] = []

        for line in lines:
            if self.BORDER_ROW_RE.match(line):
                continue
            # Remove leading/trailing | and split on |.
            cleaned = line.strip().strip("|").strip()
            cells = [c.strip() for c in cleaned.split("|")]
            if any(c for c in cells):
                rows.append(cells)

        if not rows:
            return TableBlock()

        headers = rows[0]
        data = rows[1:]

        # Attempt colspan detection: border-row column count.
        border_row = next((l for l in lines if self.BORDER_ROW_RE.match(l)), "")
        col_widths = border_row.count("-")
        if col_widths > 0:
            estimated_cols = col_widths // 2
        else:
            estimated_cols = max((len(r) for r in rows), default=0)

        block = TableBlock(
            headers=headers,
            cells=data,
            row_count=len(data),
            col_count=estimated_cols,
        )
        return block

    @staticmethod
    def export_json(table: TableBlock) -> str:
        """Export table as JSON string. List of dicts keyed by headers."""
        if table.headers:
            records: List[Dict[str, str]] = []
            for row_idx, row in enumerate(table.cells):
                rec: Dict[str, str] = {}
                for c_idx, header in enumerate(table.headers):
                    val = row[c_idx] if c_idx < len(row) else ""
                    rec[header] = val
                records.append(rec)
            return json.dumps(records, ensure_ascii=False, indent=2)
        else:
            return json.dumps(table.cells, ensure_ascii=False, indent=2)

    @staticmethod
    def export_csv(table: TableBlock) -> str:
        """Export table as CSV string with proper quoting."""
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        if table.headers:
            writer.writerow(table.headers)
        for row in table.cells:
            writer.writerow([c or "" for c in row])
        return buf.getvalue()

    @staticmethod
    def export_markdown(table: TableBlock) -> str:
        """Export table as Markdown pipe-table string."""
        all_rows = table.cells
        if table.headers:
            header_row = table.headers
            sep_row = ["-" * max(len(h), 2) for h in header_row]
            all_rows = [header_row, sep_row] + all_rows
        else:
            header_row = [f"Col{i+1}" for i in range(len(all_rows[0]))] if all_rows else []
            sep_row = ["-" * 4] * len(header_row)
            all_rows = [header_row, sep_row] + all_rows

        out_lines: List[str] = []
        for row in all_rows:
            out_lines.append("| " + " | ".join(row) + " |")
        return "\n".join(out_lines)


def extract_tables(text: str) -> List[TableBlock]:
    """Convenience function: quick table extraction."""
    return TableExtractor().extract(text)
