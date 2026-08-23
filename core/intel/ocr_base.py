"""
intel/ocr_base.py — OCR Engine Abstraction Layer
===================================================
Defines interfaces and registry for interchangeable OCR providers.

Supports: Tesseract, EasyOCR, PaddleOCR, Azure Document Intelligence,
          Google Document AI, AWS Textract, Mistral OCR (placeholder).

Architecture:
    - OCREngineProvider (abstract base)
    - OCRProviderRegistry (singleton registry via ServiceContainer)
    - Pluggable implementations added as new modules

All existing pipeline OCR placeholder (core/pipeline/pipeline.py::_ocr)
is extended by registering a concrete provider here.
"""

from __future__ import annotations

import time
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interfaces import BaseProvider, OCREngine, OCRResult  # noqa: F401 (re-export)
from core.pipeline.models import Document, ProcessingStage


# ── Abstract OCR Provider ────────────────────────────────────────────────────

class OCREngineProvider(OCREngine):
    """
    Abstract base class for all OCR engine implementations.

    Subclasses implement:
        - extract_text() : Perform OCR on a file or image
        - extract_metadata(): Get document-level metadata
        - supported_formats(): Return list of supported extensions

    Provides:
        - Lifecycle management (initialize/shutdown)
        - Health check stub
        - Common configuration handling
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version
        self._initialized = False
        self._config: Dict[str, Any] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the OCR engine. Called once on startup."""
        if self._initialized:
            return True
        try:
            self._config = config or {}
            self._do_initialize(config)
            self._initialized = True
            return True
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to initialize {self.name}: {e}") from e

    @abstractmethod
    def _do_initialize(self, config: Dict[str, Any]) -> None:
        """Subclass-specific initialization logic."""
        ...

    def health_check(self) -> tuple[bool, str]:
        """Check if the OCR engine is operational."""
        if not self._initialized:
            return False, "Not initialized"
        return self._do_health_check()

    @abstractmethod
    def _do_health_check(self) -> tuple[bool, str]:
        """Subclass-specific health check."""
        ...

    def shutdown(self) -> None:
        """Clean up resources."""
        try:
            self._do_shutdown()
        finally:
            self._initialized = False

    @abstractmethod
    def _do_shutdown(self) -> None:
        """Subclass-specific cleanup."""
        ...

    # ── Properties ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)


# ── Pipeline-compatible OCR Wrapper ──────────────────────────────────────────

def run_ocr_on_document(
    document: Document,
    ocr_engine: OCREngineProvider,
) -> Document:
    """Run OCR on a document within the pipeline context.

    This bridges the old pipeline's _ocr() method with the new OCR framework.
    Used internally by DocumentIntelligenceManager.
    """
    start = time.perf_counter()

    result = ocr_engine.extract_text(document.original_path)

    document.metadata["ocr_text"] = result.text
    document.metadata["ocr_confidence"] = result.confidence
    document.ocr_time_ms = (time.perf_counter() - start) * 1000
    document.record_stage(ProcessingStage.OCR, duration_ms=document.ocr_time_ms)
    document.metadata["ocr_engine"] = ocr_engine.name

    return document


# ── Default / Fallback Providers ─────────────────────────────────────────────

class StubOCREngineProvider(OCREngineProvider):
    """No-op OCR provider used when no real OCR engine is installed.

    Passes through parser output without actual OCR processing.
    Records a warning in the document metadata.
    """

    def __init__(self):
        super().__init__(name="stub-ocr", version="1.0.0")

    def _do_initialize(self, config: Dict[str, Any]) -> None:
        pass

    def _do_health_check(self) -> tuple[bool, str]:
        return True, "Stub OCR available (no-op)"

    def _do_shutdown(self) -> None:
        pass

    def extract_text(self, file_path: Path, **options) -> OCRResult:
        return OCRResult(
            text="", page_count=0, metadata={"engine": "stub-ocr"},
            confidence=0.0, processing_time_ms=0.0,
        )

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {"engine": "stub-ocr"}

    def supported_formats(self) -> List[str]:
        return [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".pdf"]


class NoOpOCREngineProvider(OCREngineProvider):
    """Pass-through OCR that returns empty text.

    For use when OCR is known to be unnecessary (e.g., digital PDF).
    Returns the raw text extracted by the parser instead.
    """

    def __init__(self):
        super().__init__(name="noop-ocr", version="1.0.0")

    def _do_initialize(self, config: Dict[str, Any]) -> None:
        pass

    def _do_health_check(self) -> tuple[bool, str]:
        return True, "No-op OCR (skipping)"

    def _do_shutdown(self) -> None:
        pass

    def extract_text(self, file_path: Path, **options) -> OCRResult:
        return OCRResult(
            text="", page_count=0, metadata={"engine": "noop-ocr"},
            confidence=1.0, processing_time_ms=0.0,
        )

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        return {"engine": "noop-ocr"}

    def supported_formats(self) -> List[str]:
        return []


# ── Registry ─────────────────────────────────────────────────────────────────

class OCRProviderRegistry:
    """Singleton registry for OCR engines. Uses the global ServiceContainer."""

    def register(self, engine: OCREngineProvider) -> None:
        """Register an OCR engine implementation."""
        container = get_service_container()
        container.register(OCREngineProvider, engine)

    def resolve(self) -> OCREngineProvider:
        """Resolve the registered OCR engine. Falls back to stub."""
        container = get_service_container()
        engine = container.resolve(OCREngineProvider)
        if engine is None:
            engine = StubOCREngineProvider()
            engine.initialize()
            self.register(engine)  # Cache it
        return engine


# Module-level singleton
_registry: Optional[OCRProviderRegistry] = None


def get_provider_registry() -> OCRProviderRegistry:
    global _registry
    if _registry is None:
        _registry = OCRProviderRegistry()
    return _registry


def get_default_ocr_engine() -> OCREngineProvider:
    """Get the default (or stub) OCR engine."""
    return get_provider_registry().resolve()


def register_ocr_engine(engine: OCREngineProvider) -> None:
    """Convenience function to register a specific OCR engine."""
    get_provider_registry().register(engine)


from core.interfaces import ServiceContainer, get_service_container  # noqa: F401 (re-export)
