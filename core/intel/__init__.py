"""
intel/__init__.py — Document Intelligence Engine
==================================================
Transforms raw documents into structured, machine-readable knowledge objects.

Architecture:
    Raw document → Parser → Layout analysis → Section extraction → Structured Doc

All components are pluggable via dependency injection (ServiceContainer).
Backward compatible: extends core.pipeline without modifying existing code.
"""

from core.intel.models import (
    # ── Structured Document Model ──
    StructuredDocument,
    Page,
    Section,
    Paragraph,
    TableBlock,
    TableCell,
    FigureBlock,
    EquationBlock,
    ReferenceBlock,
    # ── Classification ──
    DocumentCategory,
    PDFType,
    ClassificationResult,
    # ── Quality Assessment ──
    QualityReport,
    QualityMetric,
    # ── Language Detection ──
    LanguageResult,
)
from core.intel.parser_base import BaseDocumentParser, parse_with_intel
from core.intel.ocr_base import OCREngineProvider, OCRProviderRegistry, get_default_ocr_engine
from core.intel.layout_analysis import LayoutAnalyzer, layout_analyze
from core.intel.section_extractor import SectionExtractor, extract_sections
from core.intel.classifier import DocumentClassifier, classify_document
from core.intel.language_detector import LanguageDetector, detect_language
from core.intel.text_normalizer import TextNormalizer, normalize_text
from core.intel.table_extractor import TableExtractor, extract_tables
from core.intel.figure_detector import FigureDetector, detect_figures
from core.intel.equation_extractor import EquationExtractor, extract_equations
from core.intel.intelligence_manager import DocumentIntelligenceManager, get_intelligence_manager

__all__ = [
    # Models
    "StructuredDocument", "Page", "Section", "Paragraph",
    "TableBlock", "TableCell", "FigureBlock", "EquationBlock", "ReferenceBlock",
    "DocumentCategory", "PDFType", "ClassificationResult",
    "QualityReport", "QualityMetric",
    "LanguageResult",
    # Parser base
    "BaseDocumentParser", "parse_with_intel",
    # OCR
    "OCREngineProvider", "OCRProviderRegistry", "get_default_ocr_engine",
    # Layout
    "LayoutAnalyzer", "layout_analyze",
    # Sections
    "SectionExtractor", "extract_sections",
    # Classifier
    "DocumentClassifier", "classify_document",
    # Language
    "LanguageDetector", "detect_language",
    # Normalizer
    "TextNormalizer", "normalize_text",
    # Tables
    "TableExtractor", "extract_tables",
    # Figures
    "FigureDetector", "detect_figures",
    # Equations
    "EquationExtractor", "extract_equations",
    # Orchestrator
    "DocumentIntelligenceManager", "get_intelligence_manager",
]
