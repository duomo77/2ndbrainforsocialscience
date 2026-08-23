"""
intel/parser_base.py — Base Document Parser
==============================================
Abstract base class for document parsers that integrates with the
existing pipeline and adds semantic layer extraction.

Wraps existing core.pipeline.parsers implementations and augments them with:
    - Layout analysis, Section extraction, Table/Figure/Equation detection
    - Quality assessment, Caching integration

Usage:
    class EnhancedPDFParser(BaseDocumentParser):
        def _do_parse(self, file_path, **options):
            from core.pipeline.parsers import PDFParser
            result = PDFParser().parse(file_path)
            return result.text, dict(result.metadata)

    result = parse_with_intel("/path/to/doc.pdf")
"""

from __future__ import annotations

import hashlib
import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.intel.models import (  # noqa: F401 (re-export)
    StructuredDocument, Page, Section, Paragraph, TableBlock,
    FigureBlock, EquationBlock, QualityReport, QualityMetric,
)

logger = logging.getLogger(__name__)

class BaseDocumentParser(ABC):
    """Abstract base for semantic-aware document parsing."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def parse_with_intel(self, file_path: Path | str, **options) -> StructuredDocument:
        """Full pipeline: parse → layout → sections → tables → figures → equations."""
        path = Path(file_path).resolve()
        raw_text, metadata = self._do_parse(path, **options)
        t0 = time.monotonic()

        doc = StructuredDocument(original_filename=path.name, source_path=path, quality=QualityReport())
        doc.parser_used = f"{self.name}/{self._version}"

        # --- Collect element positions from parsed pages ---
        elems_by_page: Dict[int, list[Paragraph]] = {}
        sec_boundaries: list[int] = []
        for pg in getattr(self, "pages", []):
            pn = getattr(pg, "page_number", -1)
            if pn < 0:
                continue
            paras = [p for p in getattr(pg, "paragraphs", [])]
            elems_by_page[pn] = paras
            sec_boundaries.extend([getattr(pg, "page_start", -1), getattr(pg, "page_end", -1)])
        max_pg = max(sec_boundaries + [pg.page_number for pg in getattr(self, "pages", [])], default=0)
        max_pg = max(max_pg, len(getattr(self, "pages", [])))

        # --- Pipeline stages (each wrapped independently) ---
        sections, tables, figures, equations = [], [], [], []
        try:
            from core.intel.layout_analysis import layout_analyze as la
            layout_info = la(raw_text, str(path))
        except Exception:
            logger.warning("layout analysis failed"); layout_info = {}
        try:
            from core.intel.section_extractor import extract_sections as es
            headings = layout_info.get("headings", [])
            sections = es(raw_text, headings=headings or None)
        except Exception:
            logger.warning("section extraction failed")
        try:
            from core.intel.table_extractor import extract_tables as et
            tables = et(raw_text)
        except Exception:
            logger.warning("table extraction failed")
        try:
            from core.intel.figure_detector import detect_figures as df
            figures = df(raw_text, file_path=path)
        except Exception:
            logger.warning("figure detection failed")
        try:
            from core.intel.equation_extractor import extract_equations as ee
            equations = ee(raw_text)
        except Exception:
            logger.warning("equation extraction failed")
        self.pages = []
        for pi in range(max_pg):
            pn = pi + 1
            paras = elems_by_page.get(pn, [])
            self.pages.append(Page(page_number=pn, text="", paragraphs=paras,
                                   reading_order=[getattr(e, "id", "") for e in paras]))
        # --- Attach blocks to pages and sections ---
        for blk_set, blks in [(self.pages, tables), (self.pages, figures), (self.pages, equations)]:
            for b in blks:
                self._attach_block(blk_set, b)
                for s in sections:
                    ps, pe = max(s.page_start, 0), max(s.page_end, 0)
                    if ps <= getattr(b, "page_number", -1) <= pe:
                        an = type(b).__name__.lower() + "s"
                        cur = getattr(s, an, [])
                        if b not in cur:
                            setattr(s, an, cur + [b])
        # --- Compute quality metrics ---
        vp = sum(1 for p in self.pages if len(p.paragraphs) > 0)
        pcs = min(len(self.pages) / max(max_pg, 1), 1.0)
        comp = min(vp / max(len(self.pages), 1), 1.0)
        cv = min(vp / max(max_pg, 1), 1.0)
        q = doc.quality
        q.parser_confidence = options.pop("parser_confidence", 1.0)
        q.layout_confidence = layout_info.get("score", 0.8)
        q.completeness_ratio = round(comp, 3)
        q.overall_score = round(min((pcs + comp + cv) / 3, 1.0), 3)

        # --- Populate output ---
        doc.total_pages = max_pg
        doc.sections, doc.pages = sections, self.pages
        doc.tables, doc.figures, doc.equations = tables, figures, equations
        doc.raw_text, doc.quality = raw_text, q
        doc.parser_used = f"{self.name}/{self._version}"
        doc.processing_time_ms = round((time.monotonic() - t0) * 1000, 1)
        return doc

    def _attach_block(self, pages: list[Page], block: Any) -> None:
        pn = getattr(block, "page_number", -1)
        if pn < 0:
            return
        for pg in pages:
            if pg.page_number == pn:
                an = type(block).__name__.lower() + "s"
                c = getattr(pg, an, None)
                if c is not None and block not in c:
                    c.append(block)
                break

    def _compute_hash(self, file_path: Path) -> str:
        """Content hash of a file for caching purposes."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                buf = f.read(65536)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()[:16]

    @abstractmethod
    def _do_parse(self, file_path: Path, **options) -> Tuple[str, Dict[str, Any]]:
        """Extract raw text and metadata. Returns (text, metadata_dict)."""
        ...

    def supported_formats(self) -> List[str]:
        """Override to declare supported extensions."""
        return []

    def detect_type(self, file_path: Path) -> str:
        """Override to detect input type."""
        return "unknown"

def parse_with_intel(file_path: Path | str) -> StructuredDocument:
    """Auto-detect best parser and run the full intel pipeline."""
    path = Path(file_path).resolve()
    ext = path.suffix.lower()
    parsers: Dict[str, Any] = {}
    for mod, name in [
        ("core.intel.parser_pdf", "PDFParser"),
        ("core.intel.parser_text", "TextParser"),
        ("core.intel.parser_docx", "DOCXParser"),
    ]:
        try:
            m = __import__(mod, fromlist=[name])
            parsers[name] = getattr(m, name)
        except ImportError:
            parsers[name] = None
    cls = parsers.get({"pdf": "PDFParser", "docx": "DOCXParser"}.get(ext)) or \
          parsers.get({"txt": "TextParser", "md": "TextParser", "rst": "TextParser",
                       "html": "TextParser", "htm": "TextParser", "csv": "TextParser", "tsv": "TextParser"}.get(ext))
    if cls is None:
        did = hashlib.md5(str(path).encode()).hexdigest()[:8]
        return StructuredDocument(id=f"doc-{did}", original_filename=path.name,
                                  quality=QualityReport(errors=[f"Unsupported format: {ext}"]))
    return cls()(path).parse_with_intel(path)
