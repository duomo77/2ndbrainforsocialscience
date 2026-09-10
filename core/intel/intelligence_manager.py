"""
intel/intelligence_manager.py — Document Intelligence Manager
================================================================
Central coordinator for all document intelligence operations.

Responsibilities:
    1. Coordinate parsing (select best parser per file type)
    2. Coordinate OCR (delegate to registered OCR engine)
    3. Coordinate layout / section / table / figure / equation extraction
    4. Validate extraction results
    5. Expose a clean unified API

Uses dependency injection via ServiceContainer for pluggable components.
"""
from __future__ import annotations

import hashlib
import logging
import time
import copy
from pathlib import Path
from typing import Any, Dict, Optional

from core.interfaces import get_service_container, ServiceContainer
from core.intel.models import (  # noqa: F401 (re-export)
    StructuredDocument, QualityReport, QualityMetric,
    DocumentCategory, PDFType, ClassificationResult, LanguageResult,
)

logger = logging.getLogger(__name__)

class DocumentIntelligenceManager:
    """Central coordinator for document intelligence operations."""

    def __init__(self, container: Optional[ServiceContainer] = None):
        self._container = container or get_service_container()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_cache_age_seconds: int = 3600
        # Pluggable services (lazy-resolved on first use)
        self._ocr_engine: Any = None
        self._classifier: Any = None
        self._lang_detector: Any = None
        self._text_normalizer: Any = None

    def _ensure_services(self):
        """Lazy-initialize pluggable services from container or module imports."""
        svc_map = [
            ("_ocr_engine", "core.intel.ocr_base", "get_default_ocr_engine", True),
            ("_classifier", "core.intel.classifier", "classify_document", False),
            ("_lang_detector", "core.intel.language_detector", "detect_language", False),
            ("_text_normalizer", "core.intel.text_normalizer", "normalize_text", False),
        ]
        for attr, mod, name, invoke in svc_map:
            if getattr(self, attr) is not None:
                continue
            try:
                m = __import__(mod, fromlist=[name])
                value = getattr(m, name)
                setattr(self, attr, value() if invoke else value)
            except Exception:
                logger.warning(f"{attr} not available")
                setattr(self, attr, False)

    def process(self, file_path: Path | str, options: Optional[Dict[str, Any]] = None) -> StructuredDocument:
        """Main entry point: full document intelligence pipeline."""
        opts = options or {}
        t0 = time.monotonic()
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Validate file exists
        path = Path(file_path).resolve()
        if not path.is_file():
            return StructuredDocument(original_filename=path.name,
                                      quality=QualityReport(errors=[f"File not found: {path}"]))

        chash = self._content_hash(path)
        cached = self._get_cached(f"doc:{chash}")
        if cached:
            cached.processing_time_ms = round((time.monotonic() - t0) * 1000, 1)
            return cached  # type: ignore[return-value]

        self._ensure_services()

        # 2-3. Extract native/parser text before deciding whether OCR is needed.
        raw_text, parser_used, parser_meta, parse_errors = self._extract_raw(path, opts)
        errors.extend(parse_errors)

        # 4. Classify document using the healthiest native text sample available.
        sample = raw_text[:max(1000, len(raw_text) // 10)] if raw_text else ""
        cls_result = self._classify(path, sample)
        if cls_result.category == DocumentCategory.UNKNOWN:
            warnings.append(f"Could not classify document: {path.name}")

        # 5. Run OCR only when extraction/classification indicates it is needed.
        pdf_type = cls_result.pdf_type
        ocr_result = None
        if self._should_run_ocr(path, pdf_type, raw_text, opts):
            ocr_result = self._run_ocr(path, pdf_type, opts)
            if ocr_result:
                ocr_text = getattr(ocr_result, "text", "") or ""
                if ocr_text:
                    if pdf_type == PDFType.HYBRID and raw_text:
                        raw_text = f"{raw_text}\n\n--- OCR Supplement ---\n\n{ocr_text}"
                    else:
                        raw_text = ocr_text
                if pdf_type == PDFType.HYBRID:
                    warnings.append("OCR supplemented hybrid PDF")
                else:
                    label = pdf_type.value if pdf_type else path.suffix.lower().lstrip(".")
                    warnings.append(f"OCR used for {label} input")

        if not raw_text:
            errors.append(f"Parser produced no output for {path.suffix}")
            return self._build_doc(path, "", [], {}, [], [], [], [], errors, warnings, t0, opts)

        # 7. Normalize extracted text
        normalized = raw_text
        if self._text_normalizer:
            try:
                normalized = self._text_normalizer(raw_text, **opts)
            except Exception:
                warnings.append("Text normalization failed")

        # 8. Detect language
        lang = LanguageResult()
        if self._lang_detector:
            try:
                lang = self._lang_detector(normalized, file_path=path)
            except Exception:
                warnings.append("Language detection failed")

        # Re-classify with normalized text for richer academic/category signals.
        sample = normalized[:max(1000, len(normalized) // 10)]
        cls_result = self._classify(path, sample)

        # 9-13. Layout analysis and semantic extraction
        sections, tables, figures, equations = self._enrich(normalized, path, errors, warnings)

        # 14-17. Build, validate, cache, return StructuredDocument
        return self._build_doc(path, normalized, sections, meta={}, tables=tables,
                               figures=figures, equations=equations, errors=errors,
                               warnings=warnings, t0=t0, opts=opts, lang=lang,
                               cls=cls_result, ocr=ocr_result, parser_used=parser_used)

    # -- internal helpers -------------------------------------------------------

    def _content_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                buf = f.read(65536)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()[:16]

    def _extract_raw(self, path: Path, opts: dict) -> tuple[str, str, dict, list[str]]:
        """Use ParserRegistry to parse; fall back to plain text reading."""
        try:
            from core.pipeline.parsers import create_default_registry
            from core.pipeline.models import EXTENSION_TO_DOC_TYPE, DocumentType
            registry = create_default_registry()
            doc_type = EXTENSION_TO_DOC_TYPE.get(path.suffix.lower(), DocumentType.TXT)
            parser = registry.get(doc_type)
            result = parser.parse(path, **opts)
            text = getattr(result, "text", "")
            parser_used = getattr(result, "parser_used", "") or type(parser).__name__
            metadata = getattr(result, "metadata", {}) or {}
            parse_errors = list(getattr(result, "errors", []) or [])
            return text, parser_used, metadata, parse_errors
        except Exception:
            # Ultimate fallback: read as plain text
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    return path.read_text(encoding=enc), "fallback", {"encoding": enc}, []
                except (UnicodeDecodeError, OSError):
                    continue
            return "", "none", {}, ["Unable to parse or read document"]

    def _classify(self, path: Path, text_sample: str) -> ClassificationResult:
        if self._classifier:
            try:
                return self._classifier(path, text_sample)
            except Exception:
                pass
        return ClassificationResult()

    def _should_run_ocr(
        self,
        path: Path,
        pdf_type: Optional[PDFType],
        raw_text: str,
        opts: dict,
    ) -> bool:
        if opts.get("disable_ocr"):
            return False
        if not self._ocr_engine:
            return False
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            return True
        if path.suffix.lower() != ".pdf":
            return False
        if pdf_type in (PDFType.SCANNED, PDFType.IMAGE_ONLY, PDFType.HYBRID):
            return True
        return not raw_text.strip()

    def _run_ocr(self, path: Path, pdf_type: Optional[PDFType], opts: dict) -> Optional[Any]:
        if not self._ocr_engine:
            return None
        try:
            return self._ocr_engine.extract_text(
                path,
                pdf_type=pdf_type.value if pdf_type else None,
                force=opts.get("force_ocr", False),
            )
        except Exception:
            return None

    def _enrich(self, text: str, path: Path, errors: list, warnings: list) -> tuple[list, list, list, list]:
        """Layout analysis + section/table/figure/equation extraction."""
        sections, tables, figures, equations = [], [], [], []
        try:
            from core.intel.layout_analysis import layout_analyze
            from core.intel.section_extractor import extract_sections
            from core.intel.table_extractor import extract_tables
            from core.intel.figure_detector import detect_figures
            from core.intel.equation_extractor import extract_equations

            layout_info = layout_analyze(text, str(path))
            headings = layout_info.get("headings", [])
            sections = extract_sections(text, headings=headings or None)
            tables = extract_tables(text)
            figures = detect_figures(text, file_path=path)
            equations = extract_equations(text)
        except Exception as e:
            warnings.append(f"Enrichment pipeline failed: {e}")
        return sections, tables, figures, equations

    def _build_doc(self, path: Path, text: str, sections: list, meta: dict,
                   tables: list, figures: list, equations: list,
                   errors: list, warnings: list, t0: float,
                   opts: dict, lang=None, cls=None, ocr=None, parser_used=""):
        """Assemble StructuredDocument, validate, and cache acceptable results."""
        # Compute quality metrics
        content_score = 1.0 if text.strip() else 0.0
        structured_score = 1.0 if (sections or tables or figures or equations) else 0.0
        overall = (0.7 * content_score) + (0.3 * structured_score)
        q = QualityReport(
            overall_score=round(min(max(overall, 0.0), 1.0), 3),
            parser_confidence=opts.get("parser_confidence", 1.0),
            completeness_ratio=round(content_score, 3),
            warnings=list(warnings),
            errors=list(errors),
        )
        q.add_metric("content_presence", content_score, confidence=1.0)
        q.add_metric("structured_extraction", structured_score, confidence=0.8)

        doc = StructuredDocument(
            id=f"doc-{hashlib.md5(str(path).encode()).hexdigest()[:8]}",
            source_path=path, original_filename=path.name,
            category=cls.category if cls else DocumentCategory.UNKNOWN,
            pdf_type=cls.pdf_type if cls else None,
            total_pages=self._infer_total_pages(text, sections, meta, ocr),
            sections=sections, tables=tables, figures=figures, equations=equations,
            quality=q, raw_text=text, parser_used=parser_used,
        )
        if lang:
            doc.primary_language = lang.primary_language
            doc.secondary_languages = lang.secondary_languages
            doc.writing_direction = lang.writing_direction
        if ocr:
            q.ocr_confidence = getattr(ocr, "confidence", 0.0)
            doc.ocr_engine = getattr(self._ocr_engine, "name", "unknown")
        doc.processing_time_ms = round((time.monotonic() - t0) * 1000, 1)

        # Cache if validation passes
        if self.validate_extraction(doc):
            self._set_cache(f"doc:{self._content_hash(path)}", doc)
        return doc

    def _get_cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["_ts"] > self._max_cache_age_seconds:
            del self._cache[key]
            return None
        return copy.deepcopy(entry["_data"])

    def _set_cache(self, key: str, data: Any) -> None:
        self._cache[key] = {"_data": copy.deepcopy(data), "_ts": time.time()}

    @staticmethod
    def _infer_total_pages(text: str, sections: list, meta: dict, ocr: Any = None) -> int:
        for source in (meta, getattr(ocr, "metadata", {}) if ocr else {}):
            for key in ("page_count", "pages", "num_pages"):
                try:
                    count = int(source.get(key, 0))
                except (TypeError, ValueError):
                    count = 0
                if count > 0:
                    return count
        ocr_pages = int(getattr(ocr, "page_count", 0) or 0) if ocr else 0
        if ocr_pages > 0:
            return ocr_pages
        section_pages = [
            p
            for sec in sections
            for p in (getattr(sec, "page_start", -1), getattr(sec, "page_end", -1))
            if isinstance(p, int) and p > 0
        ]
        if section_pages:
            return max(section_pages)
        return 1 if text.strip() else 0

    def clear_cache(self) -> int:
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v["_ts"] > self._max_cache_age_seconds]
        for k in expired:
            del self._cache[k]
        return len(expired)

    def validate_extraction(self, doc: StructuredDocument) -> bool:
        """Validate that extraction produced acceptable results."""
        if doc.quality.errors:
            return False
        score_mets = [m for m in doc.quality.metrics
                      if any(k in m.name for k in ("page", "completeness", "content"))]
        avg = (sum(m.score for m in score_mets) / max(len(score_mets), 1)) if score_mets else 0.0
        return avg >= 0.3 or doc.quality.overall_score >= 0.3

    def get_status(self) -> Dict[str, Any]:
        """Return operational status of all subsystems."""
        def avail(svc): return svc.name if hasattr(svc, "name") else "loaded" if svc else "not available"
        return {
            "cache_size": len(self._cache),
            "cache_max_age_s": self._max_cache_age_seconds,
            "ocr_engine": avail(self._ocr_engine),
            "classifier": "available" if self._classifier else "not available",
            "language_detector": "available" if self._lang_detector else "not available",
            "text_normalizer": "available" if self._text_normalizer else "not available",
        }

_default_manager: Optional[DocumentIntelligenceManager] = None

def get_intelligence_manager() -> DocumentIntelligenceManager:
    """Get or create the singleton manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = DocumentIntelligenceManager()
    return _default_manager
