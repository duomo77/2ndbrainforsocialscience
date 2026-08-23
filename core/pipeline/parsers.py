"""
pipeline/parsers.py — Document Parser Implementations
=======================================================
Parser implementations for each supported document type.
Each parser is independent — new parsers can be added without modifying existing code.

Backward compatible: delegates to existing core.parsers for PDF/TXT/CSV/Excel.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from core.pipeline.interfaces import DocumentParser
from core.pipeline.models import ParseResult, DocumentType


class TextParser(DocumentParser):
    """Parser for plain text and Markdown files."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        encoding = options.get("encoding", "utf-8")
        try:
            text = file_path.read_text(encoding=encoding)
            return ParseResult(
                success=True,
                text=text,
                parser_used="text_parser",
                metadata={"encoding": encoding},
            )
        except UnicodeDecodeError:
            text = file_path.read_text(encoding=encoding, errors="replace")
            return ParseResult(
                success=True,
                text=text,
                parser_used="text_parser",
                metadata={"encoding": encoding, "had_decode_errors": True},
            )

    def supported_types(self) -> List[str]:
        return ["txt", "markdown", "rst"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {
            "filename": file_path.name,
            "file_size": file_path.stat().st_size,
        }


class PDFParser(DocumentParser):
    """Parser for PDF files — delegates to existing core.parsers."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from core.parsers import parse_pdf
            text, metadata = parse_pdf(str(file_path))
            return ParseResult(
                success=True,
                text=text,
                metadata=metadata or {},
                parser_used="pdf_parser",
            )
        except Exception as e:
            return ParseResult(
                success=False,
                parser_used="pdf_parser",
                errors=[str(e)],
            )

    def supported_types(self) -> List[str]:
        return ["pdf"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            from core.pdf_parser import get_pdf_metadata
            return get_pdf_metadata(str(file_path))
        except Exception:
            return {}


class CSVExcelParser(DocumentParser):
    """Parser for CSV, TSV, and Excel files — delegates to existing core.parsers."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from core.parsers import parse_dataset
            text, metadata = parse_dataset(str(file_path))
            return ParseResult(
                success=True,
                text=text,
                metadata=metadata or {},
                parser_used="csv_excel_parser",
            )
        except Exception as e:
            return ParseResult(
                success=False,
                parser_used="csv_excel_parser",
                errors=[str(e)],
            )

    def supported_types(self) -> List[str]:
        return ["csv", "excel"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {"filename": file_path.name}


class HTMLParser(DocumentParser):
    """Parser for HTML files — extracts readable text."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from html.parser import HTMLParser as BaseHTMLParser

            class _TextExtractor(BaseHTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text: List[str] = []
                    self.skip_tags = {"script", "style", "meta", "link", "noscript"}

                def handle_data(self, data):
                    if self.lasttag not in self.skip_tags:
                        self.text.append(data)

            extractor = _TextExtractor()
            extractor.feed(file_path.read_text(encoding="utf-8", errors="replace"))
            text = " ".join(extractor.text).strip()

            return ParseResult(
                success=True,
                text=text,
                parser_used="html_parser",
                metadata={"title": self._extract_title(file_path)},
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="html_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["html"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {"title": self._extract_title(file_path)}

    def _extract_title(self, file_path: Path) -> str:
        try:
            import re
            content = file_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
            return match.group(1).strip() if match else ""
        except Exception:
            return ""


class DOCXParser(DocumentParser):
    """Parser for DOCX files using python-docx."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)

            # Extract metadata
            props = doc.core_properties
            metadata = {
                "title": props.title or "",
                "author": props.author or "",
                "created": str(props.created) if props.created else "",
                "modified": str(props.modified) if props.modified else "",
                "paragraph_count": len(paragraphs),
            }

            return ParseResult(
                success=True,
                text=text,
                metadata=metadata,
                parser_used="docx_parser",
            )
        except ImportError:
            return ParseResult(
                success=False,
                parser_used="docx_parser",
                errors=["python-docx not installed. Run: pip install python-docx"],
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="docx_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["docx"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(str(file_path))
            return {
                "title": doc.core_properties.title or "",
                "author": doc.core_properties.author or "",
            }
        except Exception:
            return {}


class PPTXParser(DocumentParser):
    """Parser for PPTX files using python-pptx."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from pptx import Presentation
            prs = Presentation(str(file_path))
            slides_text = []
            for i, slide in enumerate(prs.slides):
                slide_texts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())
                if slide_texts:
                    slides_text.append(f"--- Slide {i + 1} ---\n" + "\n".join(slide_texts))

            text = "\n\n".join(slides_text)

            return ParseResult(
                success=True,
                text=text,
                parser_used="pptx_parser",
                metadata={"slide_count": len(prs.slides)},
            )
        except ImportError:
            return ParseResult(
                success=False,
                parser_used="pptx_parser",
                errors=["python-pptx not installed. Run: pip install python-pptx"],
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="pptx_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["pptx"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            from pptx import Presentation
            prs = Presentation(str(file_path))
            return {
                "slide_count": len(prs.slides),
                "slide_width": prs.slide_width,
                "slide_height": prs.slide_height,
            }
        except Exception:
            return {}


class EPUBParser(DocumentParser):
    """Parser for EPUB e-book files."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            from ebooklib import epub
            book = epub.read_epub(str(file_path))
            chapters = []
            for item in book.get_items_of_type(9):  # ITEM_DOCUMENT = 9
                from html.parser import HTMLParser

                class _TextExtractor(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text: List[str] = []

                    def handle_data(self, data):
                        self.text.append(data)

                extractor = _TextExtractor()
                extractor.feed(item.get_content().decode("utf-8", errors="replace"))
                chapters.append(" ".join(extractor.text))

            text = "\n\n".join(chapters)
            title = book.get_metadata("DC", "title")
            title_str = title[0][0] if title else ""

            return ParseResult(
                success=True,
                text=text,
                parser_used="epub_parser",
                metadata={"title": title_str, "chapter_count": len(chapters)},
            )
        except ImportError:
            return ParseResult(
                success=False,
                parser_used="epub_parser",
                errors=["ebooklib not installed. Run: pip install ebooklib"],
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="epub_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["epub"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {}


class SRTParser(DocumentParser):
    """Parser for SRT subtitle files."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            entries, meta = self._parse_srt(text)

            return ParseResult(
                success=True,
                text=text,
                metadata={**meta, "entry_count": len(entries)},
                chunks=entries[:50],  # Limit chunk list size
                parser_used="srt_parser",
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="srt_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["srt"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            _, meta = self._parse_srt(text)
            return meta
        except Exception:
            return {}

    @staticmethod
    def _parse_srt(text: str) -> tuple[list[str], dict]:
        """Parse SRT content into timed entries and metadata."""
        entries = []
        speakers = set()

        for block in text.strip().split("\n\n"):
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue

            # Try to detect speaker pattern (e.g., "Speaker Name: text" or "[Name]: text")
            for line in lines[2:]:
                speaker_match = re.match(r'^([A-Z][A-Za-z\s]+?):\s', line)
                if speaker_match:
                    speakers.add(speaker_match.group(1).strip())

            entries.append(block.strip())

        # Estimate duration from last timestamp
        timestamps = re.findall(r'(\d{1,2}:\d{2}:\d{2},\d{3}) --> (\d{1,2}:\d{2}:\d{2},\d{3})', text)
        duration = ""
        if timestamps:
            duration = f"{timestamps[0][0]} --> {timestamps[-1][1]}"

        return entries, {
            "format": "SRT",
            "speakers": sorted(speakers)[:10],
            "duration": duration,
            "word_count": len(text.split()),
        }


class VTTParser(DocumentParser):
    """Parser for WebVTT subtitle files."""

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")

            # Strip VTT header
            if text.startswith("WEBVTT"):
                text = text[len("WEBVTT"):].lstrip("\ufeff").lstrip("\n")

            entries, meta = self._parse_vtt(text)

            return ParseResult(
                success=True,
                text=text,
                metadata={**meta, "entry_count": len(entries)},
                chunks=entries[:50],
                parser_used="vtt_parser",
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="vtt_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return ["vtt"]

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if text.startswith("WEBVTT"):
                text = text[len("WEBVTT"):].lstrip("\ufeff").lstrip("\n")
            _, meta = self._parse_vtt(text)
            return meta
        except Exception:
            return {}

    @staticmethod
    def _parse_vtt(text: str) -> tuple[list[str], dict]:
        """Parse VTT content into timed entries and metadata."""
        entries = []
        speakers = set()

        for block in text.strip().split("\n\n"):
            lines = block.strip().splitlines()
            if len(lines) < 2:
                continue

            for line in lines:
                speaker_match = re.match(r'^([A-Z][A-Za-z\s]+?):\s', line)
                if speaker_match:
                    speakers.add(speaker_match.group(1).strip())

            entries.append(block.strip())

        timestamps = re.findall(r'(\d{1,2}:)?(\d{1,2}):(\d{2}\.\d{3}) --> (\d{1,2}:)?(\d{1,2}):(\d{2}\.\d{3})', text)
        duration = ""
        if timestamps:
            duration = f"{timestamps[0][0] or ''}{timestamps[0][1]}:{timestamps[0][2]} --> {timestamps[-1][3] or ''}{timestamps[-1][4]}:{timestamps[-1][5]}"

        return entries, {
            "format": "WebVTT",
            "speakers": sorted(speakers)[:10],
            "duration": duration,
            "word_count": len(text.split()),
        }


class CodeParser(DocumentParser):
    """Parser for source code files (.py, .r, .do, .jl, .m, .stan, etc.)."""

    LANGUAGE_EXTENSIONS = {
        ".py": "Python",
        ".r": "R",
        ".do": "Stata",
        ".jl": "Julia",
        ".m": "MATLAB",
        ".stan": "Stan",
        ".sas": "SAS",
        ".scala": "Scala",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
    }

    def parse(self, file_path: Path, **options) -> ParseResult:
        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")

            ext = file_path.suffix.lower()  # Keep the dot: ".py"
            language = CodeParser.LANGUAGE_EXTENSIONS.get(ext, ext.lstrip(".") or "Unknown")

            meta = self._analyze_code(code, language)
            return ParseResult(
                success=True,
                text=code,
                metadata={**meta, "language": language},
                parser_used="code_parser",
            )
        except Exception as e:
            return ParseResult(success=False, parser_used="code_parser", errors=[str(e)])

    def supported_types(self) -> List[str]:
        return list(CodeParser.LANGUAGE_EXTENSIONS.keys())

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            ext = file_path.suffix.lower()  # Keep the dot: ".py"
            language = CodeParser.LANGUAGE_EXTENSIONS.get(ext, ext.lstrip(".") or "Unknown")
            meta = self._analyze_code(code, language)
            meta["language"] = language
            return meta
        except Exception:
            return {}

    @staticmethod
    def _analyze_code(code: str, language: str) -> Dict[str, Any]:
        """Analyze source code for structure summary."""
        lines = code.split("\n")
        non_empty_lines = [l for l in lines if l.strip()]
        blank_lines = sum(1 for l in lines if not l.strip())
        indent_levels = [len(l) - len(l.lstrip()) for l in non_empty_lines if l.strip()]
        max_indent = max(indent_levels) if indent_levels else 0

        # Count function/class definitions by language
        func_patterns = {
            "Python": r'^\s*def\s+\w+',
            "R": r'^\s*\w+\s*<-\s*function',
            "Stata": r'\b(bysort|capture|global|local)\b',
            "Julia": r'^\s*(function|macro)\s+\w+',
            "MATLAB": r'^\s*function\b',
            "Stan": r'\b(parameters|model|generated quantities)\b',
        }
        func_count = 0
        pattern = func_patterns.get(language, r'\b(function|def|func)\b')
        matches = re.findall(pattern, code, re.MULTILINE)
        func_count = len(matches)

        return {
            "file_name": "",
            "lines": len(lines),
            "non_blank_lines": len(non_empty_lines),
            "blank_lines": blank_lines,
            "max_indentation": max_indent,
            "estimated_functions": func_count,
            "char_count": len(code),
            "is_binary_like": any(b > 126 for b in code.encode('utf-8', errors='ignore') if isinstance(b, int)),
        }


# ── Parser Registry ─────────────────────────────────────────────────────────

class ParserRegistry:
    """Registry mapping document types to parser instances.

    New parsers can be registered without modifying existing code.
    """

    def __init__(self):
        self._parsers: Dict[DocumentType, DocumentParser] = {}

    def register(self, doc_type: DocumentType, parser: DocumentParser) -> None:
        """Register a parser for a document type."""
        self._parsers[doc_type] = parser

    def get(self, doc_type: DocumentType) -> DocumentParser:
        """Get parser for a document type. Returns TextParser fallback for unknown types."""
        return self._parsers.get(doc_type, TextParser())

    def supported_types(self) -> List[DocumentType]:
        return list(self._parsers.keys())


def create_default_registry() -> ParserRegistry:
    """Create a parser registry pre-populated with default parsers."""
    registry = ParserRegistry()
    registry.register(DocumentType.PDF, PDFParser())
    registry.register(DocumentType.TXT, TextParser())
    registry.register(DocumentType.MARKDOWN, TextParser())
    registry.register(DocumentType.HTML, HTMLParser())
    registry.register(DocumentType.DOCX, DOCXParser())
    registry.register(DocumentType.PPTX, PPTXParser())
    registry.register(DocumentType.EPUB, EPUBParser())
    registry.register(DocumentType.CSV, CSVExcelParser())
    registry.register(DocumentType.EXCEL, CSVExcelParser())
    # Transcript formats
    registry.register(DocumentType.TRANSCRIPT_SRT, SRTParser())
    registry.register(DocumentType.TRANSCRIPT_VTT, VTTParser())
    # Code files — uses single CodeParser for all supported extensions
    code_parser = CodeParser()
    for ext_type in (DocumentType.CODE_PYTHON, DocumentType.CODE_R,
                     DocumentType.CODE_STATA, DocumentType.CODE_JULIA,
                     DocumentType.CODE_MATALAB, DocumentType.CODE_STAN):
        registry.register(ext_type, code_parser)
    return registry