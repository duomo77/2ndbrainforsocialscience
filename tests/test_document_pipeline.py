"""
Tests for the Document Processing Pipeline.
Tests cover: validation, identification, parsing, cleaning, pipeline orchestration,
error recovery, document manager, and edge cases.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from core.pipeline.models import (
    Document,
    DocumentType,
    ProcessingStatus,
    ProcessingStage,
    ValidationResult,
    IdentificationResult,
    ParseResult,
)
from core.pipeline.validator import DocumentValidatorImpl
from core.pipeline.identifier import DocumentIdentifierImpl
from core.pipeline.cleaner import DocumentCleanerImpl, clean_text
from core.pipeline.doc_manager import DocumentManager
from core.pipeline.pipeline import DocumentPipeline, process_document
from core.pipeline.file_storage import FileStorage
from core.pipeline.parsers import (
    create_default_registry,
    CodeParser,
    SRTParser,
    VTTParser,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_txt_file(tmp_dir):
    """Create a sample text file."""
    path = tmp_dir / "sample.txt"
    path.write_text("Hello, world!\nThis is a test document.\n")
    return path


@pytest.fixture
def sample_md_file(tmp_dir):
    """Create a sample markdown file."""
    path = tmp_dir / "sample.md"
    path.write_text("# Title\n\nThis is **markdown** content.\n\n## Section\n\nMore text here.")
    return path


@pytest.fixture
def sample_csv_file(tmp_dir):
    """Create a sample CSV file."""
    path = tmp_dir / "sample.csv"
    path.write_text("name,age,city\nAlice,30,Seoul\nBob,25,Busan\n")
    return path


@pytest.fixture
def sample_html_file(tmp_dir):
    """Create a sample HTML file."""
    path = tmp_dir / "sample.html"
    path.write_text("""<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body><h1>Hello</h1><p>This is a test.</p></body>
</html>""")
    return path


@pytest.fixture
def validator():
    return DocumentValidatorImpl()


@pytest.fixture
def identifier():
    return DocumentIdentifierImpl()


@pytest.fixture
def cleaner():
    return DocumentCleanerImpl()


# ── Validation Tests ────────────────────────────────────────────────────────

class TestDocumentValidator:
    """Tests for document validation."""

    def test_valid_txt_file(self, validator, sample_txt_file):
        result = validator.validate(sample_txt_file)
        assert result.is_valid is True
        assert result.extension == ".txt"
        assert len(result.errors) == 0

    def test_valid_md_file(self, validator, sample_md_file):
        result = validator.validate(sample_md_file)
        assert result.is_valid is True
        assert result.extension == ".md"

    def test_unsupported_extension(self, validator, tmp_dir):
        path = tmp_dir / "test.xyz"
        path.write_text("content")
        result = validator.validate(path)
        assert result.is_valid is False
        assert any("Unsupported" in e for e in result.errors)

    def test_nonexistent_file(self, validator):
        from pathlib import Path
        result = validator.validate(Path("/nonexistent/file.pdf"))
        assert result.is_valid is False

    def test_empty_file_detection(self, validator, tmp_dir):
        path = tmp_dir / "empty.txt"
        path.write_text("")
        result = validator.validate(path)
        assert result.is_valid is False

    def test_content_hash_generation(self, validator, sample_txt_file):
        result = validator.validate(sample_txt_file)
        assert result.content_hash != ""
        assert len(result.content_hash) == 64  # SHA-256

    def test_supported_extensions(self, validator):
        exts = validator.supported_extensions()
        assert ".pdf" in exts
        assert ".txt" in exts
        assert ".md" in exts
        assert ".html" in exts


# ── Identification Tests ────────────────────────────────────────────────────

class TestDocumentIdentifier:
    """Tests for document identification."""

    def test_identify_txt(self, identifier, sample_txt_file):
        result = identifier.identify(sample_txt_file)
        assert result.doc_type == DocumentType.TXT

    def test_identify_md(self, identifier, sample_md_file):
        result = identifier.identify(sample_md_file)
        assert result.doc_type == DocumentType.MARKDOWN

    def test_identify_csv(self, identifier, sample_csv_file):
        result = identifier.identify(sample_csv_file)
        assert result.doc_type == DocumentType.CSV

    def test_identify_html(self, identifier, sample_html_file):
        result = identifier.identify(sample_html_file)
        assert result.doc_type == DocumentType.HTML

    def test_language_detection_english(self, identifier):
        text = "The quick brown fox jumps over the lazy dog. This is a test."
        lang = identifier.detect_language(text)
        assert lang == "en"

    def test_language_detection_korean(self, identifier):
        text = "안녕하세요 이것은 한국어 텍스트입니다 반갑습니다"
        lang = identifier.detect_language(text)
        assert lang == "ko"

    def test_empty_language_detection(self, identifier):
        lang = identifier.detect_language("")
        assert lang == "unknown"

    def test_needs_ocr_for_image(self, tmp_dir, identifier):
        """Image files should return True for needs_ocr."""
        # Create a minimal valid PNG file (1x1 pixel transparent)
        path = tmp_dir / "test.png"
        import struct, zlib
        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xffffffff
        ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
        raw = zlib.compress(b"\x00\x00\x00\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw) & 0xffffffff
        idat_chunk = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
        iend_crc = zlib.crc32(b"IEND") & 0xffffffff
        iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        path.write_bytes(header + ihdr_chunk + idat_chunk + iend_chunk)

        result = identifier.identify(path)
        assert result.needs_ocr is True

    def test_needs_ocr_for_text(self, identifier, sample_txt_file):
        result = identifier.identify(sample_txt_file)
        assert result.needs_ocr is False

    def test_encoding_detection(self, identifier, sample_txt_file):
        enc = identifier.detect_encoding(sample_txt_file)
        assert enc in ("utf-8", "utf-8-sig", "latin-1")


# ── Cleaning Tests ──────────────────────────────────────────────────────────

class TestDocumentCleaner:
    """Tests for text cleaning and normalization."""

    def test_clean_null_bytes(self, cleaner):
        text = "Hello\x00World"
        result = cleaner.clean(text)
        assert "\x00" not in result

    def test_clean_whitespace(self, cleaner):
        text = "Hello\n\n\n\nWorld"
        result = cleaner.clean(text)
        assert "\n\n\n\n" not in result

    def test_normalize_quotes(self, cleaner):
        text = "\u201cHello\u201d \u2018world\u2019"
        result = cleaner.clean(text)
        assert '"' in result

    def test_normalize_unicode(self, cleaner):
        text = "caf\u00e9"  # e-acute as composed
        result = cleaner.normalize(text)
        assert "café" in result or "caf\u00e9" in result

    def test_clean_empty_text(self, cleaner):
        result = cleaner.clean("")
        assert result == ""

    def test_clean_html_text(self, cleaner):
        text = "Hello &amp; World &lt;test&gt;"
        result = cleaner.clean(text, doc_type="html")
        assert "&amp;" not in result


# ── Document Manager Tests ──────────────────────────────────────────────────

class TestDocumentManager:
    """Tests for DocumentManager service."""

    def test_register_document(self, sample_txt_file):
        manager = DocumentManager()
        doc = manager.register(sample_txt_file)

        assert doc.id.startswith("doc-")
        assert doc.original_path.resolve() == sample_txt_file.resolve()
        assert doc.status == ProcessingStatus.PENDING
        assert doc.doc_type == DocumentType.TXT

    def test_get_document(self, sample_txt_file):
        manager = DocumentManager()
        doc = manager.register(sample_txt_file)
        retrieved = manager.get(doc.id)

        assert retrieved is not None
        assert retrieved.id == doc.id

    def test_cancel_document(self, sample_txt_file):
        manager = DocumentManager()
        doc = manager.register(sample_txt_file)
        result = manager.cancel(doc.id)

        assert result is True
        assert doc.status == ProcessingStatus.CANCELLED

    def test_query_by_status(self, sample_txt_file, sample_md_file):
        manager = DocumentManager()
        doc1 = manager.register(sample_txt_file)
        doc2 = manager.register(sample_md_file)

        doc1.status = ProcessingStatus.COMPLETED
        doc2.status = ProcessingStatus.FAILED

        completed = manager.query(status=ProcessingStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].id == doc1.id

    def test_list_all(self, sample_txt_file, sample_md_file):
        manager = DocumentManager()
        manager.register(sample_txt_file)
        manager.register(sample_md_file)

        all_docs = manager.list_all()
        assert len(all_docs) == 2

    def test_get_stats(self, sample_txt_file):
        manager = DocumentManager()
        manager.register(sample_txt_file)

        stats = manager.get_stats()
        assert stats["total"] == 1
        assert "storage" in stats


# ── Pipeline Integration Tests ──────────────────────────────────────────────

class TestDocumentPipeline:
    """Integration tests for the complete pipeline."""

    def test_process_txt_file(self, sample_txt_file):
        pipeline = DocumentPipeline()
        doc = pipeline.process(sample_txt_file)

        assert doc is not None
        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.doc_type == DocumentType.TXT

    def test_process_md_file(self, sample_md_file):
        pipeline = DocumentPipeline()
        doc = pipeline.process(sample_md_file)

        assert doc.status == ProcessingStatus.COMPLETED

    def test_stage_history_recorded(self, sample_txt_file):
        pipeline = DocumentPipeline()
        doc = pipeline.process(sample_txt_file)

        assert len(doc.stage_history) > 0
        stages = [s["stage"] for s in doc.stage_history]
        assert ProcessingStage.VALIDATING.value in stages
        assert ProcessingStage.PARSING.value in stages
        assert ProcessingStage.STORING.value in stages

    def test_processing_duration(self, sample_txt_file):
        pipeline = DocumentPipeline()
        doc = pipeline.process(sample_txt_file)

        assert doc.processing_duration_ms > 0

    def test_nonexistent_file(self, tmp_dir):
        pipeline = DocumentPipeline()
        path = tmp_dir / "nonexistent.txt"
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.FAILED

    def test_unsupported_file(self, tmp_dir):
        pipeline = DocumentPipeline()
        path = tmp_dir / "test.xyz"
        path.write_text("content")
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.FAILED


# ── File Storage Tests ──────────────────────────────────────────────────────

class TestFileStorage:
    """Tests for file storage service."""

    def test_store_processed(self, tmp_dir):
        storage = FileStorage(base_path=tmp_dir / "documents")
        doc = Document(
            id="test-doc-001",
            original_path=Path("/fake/test.txt"),
        )
        path = storage.store_processed(doc, "Hello World")
        assert path.exists()

    def test_store_metadata(self, tmp_dir):
        storage = FileStorage(base_path=tmp_dir / "documents")
        doc = Document(
            id="test-doc-002",
            original_path=Path("/fake/test.txt"),
        )
        path = storage.store_metadata(doc, {"key": "value"})
        assert path.exists()
        assert path.suffix == ".json"

    def test_cleanup(self, tmp_dir):
        storage = FileStorage(base_path=tmp_dir / "documents")
        doc = Document(
            id="test-doc-003",
            original_path=Path("/fake/test.txt"),
        )
        storage.cleanup(doc)  # Should not raise


# ── Error Recovery Tests ────────────────────────────────────────────────────

class TestErrorRecovery:
    """Tests for error recovery in pipeline."""

    def test_pipeline_handles_parser_failure(self, tmp_dir):
        """Pipeline should complete even if a stage fails (with can_skip=True)."""
        path = tmp_dir / "test.txt"
        path.write_text("test content")

        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        # Should complete or fail gracefully, not raise
        assert doc.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED)

    def test_validation_failure_is_fatal(self, tmp_dir):
        """Validation failure should mark document as failed."""
        path = tmp_dir / "nonexistent.txt"
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.FAILED


# ── Backward Compatibility Tests ────────────────────────────────────────────

class TestBackwardCompatibility:
    """Verify existing parsers still work."""

    def test_existing_parsers_unchanged(self):
        """Existing core.parsers module should still be importable."""
        from core.parsers import parse_pdf, parse_text, detect_input_type
        assert callable(parse_pdf)
        assert callable(parse_text)
        assert callable(detect_input_type)

    # Removed (2026-08-23 audit, Phase 1): test_existing_pdf_parser_unchanged
    # imported core.pdf_parser, a module that has never existed in this
    # repository (verified by repo-wide grep). The real parser surface is
    # covered by test_existing_parsers_unchanged above.


# ── SRT/VTT Transcript Parser Tests ──────────────────────────────────────────

class TestSRTParser:
    """Tests for SRT transcript parsing."""

    def test_parse_srt(self, tmp_dir):
        path = tmp_dir / "subtitles.srt"
        path.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nHello world, this is a test.\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond subtitle entry here.",
            encoding="utf-8",
        )
        from core.pipeline.parsers import SRTParser
        parser = SRTParser()
        result = parser.parse(path)

        assert result.success is True
        assert result.parser_used == "srt_parser"
        assert "entry_count" in result.metadata
        assert result.metadata["entry_count"] == 2
        assert len(result.chunks) == 2

    def test_srt_detects_speakers(self, tmp_dir):
        path = tmp_dir / "talk.srt"
        path.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nAlice: Welcome to the talk.\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\nBob: Thanks Alice.\n",
            encoding="utf-8",
        )
        from core.pipeline.parsers import SRTParser
        parser = SRTParser()
        meta = parser.extract_metadata(path)
        assert "speakers" in meta
        assert "Alice" in meta["speakers"] or "Bob" in meta["speakers"]


class TestVTTParser:
    """Tests for WebVTT transcript parsing."""

    def test_parse_vtt(self, tmp_dir):
        path = tmp_dir / "captions.vtt"
        path.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\n"
            "Hello world from VTT.\n\n"
            "00:00:05.000 --> 00:00:08.000\n"
            "Second caption here.\n",
            encoding="utf-8",
        )
        from core.pipeline.parsers import VTTParser
        parser = VTTParser()
        result = parser.parse(path)

        assert result.success is True
        assert result.parser_used == "vtt_parser"
        assert "entry_count" in result.metadata
        assert result.metadata["entry_count"] >= 1


# ── Code Parser Tests ─────────────────────────────────────────────────────────

class TestCodeParser:
    """Tests for source code file parsing."""

    def test_parse_python_file(self, tmp_dir):
        path = tmp_dir / "script.py"
        path.write_text(
            "def hello():\n"
            "    print('Hello')\n\n"
            "def main():\n"
            "    hello()\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
        from core.pipeline.parsers import CodeParser
        parser = CodeParser()
        result = parser.parse(path)

        assert result.success is True
        assert result.parser_used == "code_parser"
        assert result.metadata["language"] == "Python"
        assert result.metadata["lines"] > 0
        assert result.metadata["estimated_functions"] >= 2

    def test_parse_r_file(self, tmp_dir):
        path = tmp_dir / "analysis.r"
        path.write_text("my_model <- lm(y ~ x, data = df)\nsummary(my_model)\n")
        from core.pipeline.parsers import CodeParser
        parser = CodeParser()
        result = parser.parse(path)
        assert result.success is True
        assert result.metadata["language"] == "R"

    def test_parse_stata_file(self, tmp_dir):
        path = tmp_dir / "model.do"
        path.write_text("reg y x1 x2, robust\nestimates store m1\n")
        from core.pipeline.parsers import CodeParser
        parser = CodeParser()
        result = parser.parse(path)
        assert result.success is True
        assert result.metadata["language"] == "Stata"

    def test_code_analyzes_structure(self, tmp_dir):
        path = tmp_dir / "complex.jl"
        path.write_text(
            "# Function definitions and analysis\n"
            "function calculate(x::Vector)\n"
            "    sum = 0\n"
            "    for i in 1:length(x)\n"
            "        sum += x[i]\n"
            "    end\n"
            "    return sum\n"
            "end\n"
        )
        from core.pipeline.parsers import CodeParser
        parser = CodeParser()
        result = parser.parse(path)
        assert result.metadata["non_blank_lines"] >= 6
        assert result.metadata["estimated_functions"] >= 1
        assert result.metadata["max_indentation"] >= 4


# ── Validator Extension Tests ─────────────────────────────────────────────────

class TestValidatorExtensions:
    """Tests for enhanced validator features."""

    def test_symlink_warning(self, tmp_dir):
        """Symlinked files should get a warning but pass validation if target exists."""
        from core.pipeline.validator import DocumentValidatorImpl
        validator = DocumentValidatorImpl()

        # Create a real file
        real_file = tmp_dir / "real.txt"
        real_file.write_text("Hello")

        # Create a symlink
        link_file = tmp_dir / "link.txt"
        try:
            link_file.symlink_to(real_file)
            result = validator.validate(link_file)
            assert result.is_valid is True
            assert any("symbolic link" in w.lower() for w in result.warnings)
        except (OSError, NotImplementedError):
            pytest.skip("Symbolic links not supported on this platform")

    def test_broken_symlink_rejected(self, tmp_dir):
        """Broken symlinks should be rejected by the validator."""
        from core.pipeline.validator import DocumentValidatorImpl
        validator = DocumentValidatorImpl()

        link_file = tmp_dir / "broken_link.txt"
        target = tmp_dir / "nonexistent_target.txt"
        try:
            link_file.symlink_to(target)
            result = validator.validate(link_file)
            assert result.is_valid is False
            assert any("broken" in e.lower() for e in result.errors)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Symbolic links not available on this system: {exc}")

    def test_size_limits_for_transcript(self):
        """Transcript types should have defined size limits."""
        from core.pipeline.validator import DocumentValidatorImpl
        limits = DocumentValidatorImpl.SIZE_LIMITS
        assert "transcript_srt" in limits
        assert "transcript_vtt" in limits
        assert limits["transcript_srt"] > 0
        assert limits["transcript_vtt"] > 0

    def test_size_limits_for_code(self):
        """Code types should have defined size limits."""
        from core.pipeline.validator import DocumentValidatorImpl
        limits = DocumentValidatorImpl.SIZE_LIMITS
        assert "code_python" in limits
        assert "code_julia" in limits
        assert limits["code_python"] > 0


# ── Identifier Extensions Tests ────────────────────────────────────────────────

class TestIdentifierExtensions:
    """Tests for identifier language detection improvements."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.identifier = DocumentIdentifierImpl()

    def test_language_detection_spanish(self):
        text = "El rápido coyote marrón salta sobre el perro perezoso."
        lang = self.identifier.detect_language(text)
        assert lang == "es"

    def test_language_detection_french(self):
        text = "Le renard brun rapide saute par-dessus le chien paresseux."
        lang = self.identifier.detect_language(text)
        assert lang == "fr"

    def test_language_detection_german(self):
        # Use text with more common German words for reliable detection
        text = "Der schnelle braune Fuchs springt über den faulen Hund und läuft weg. Der Hund bellt laut."
        lang = self.identifier.detect_language(text)
        assert lang == "de"

    def test_language_detection_short_english(self):
        text = "The quick brown fox jumps over the lazy dog now and then."
        lang = self.identifier.detect_language(text)
        assert lang == "en"

    def test_identify_srt_as_txt(self, tmp_dir):
        """SRT files should be identified as text-based (no OCR needed)."""
        path = tmp_dir / "test.srt"
        path.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello.\n", encoding="utf-8")
        result = self.identifier.identify(path)
        assert result.doc_type == DocumentType.TRANSCRIPT_SRT
        assert result.needs_ocr is False

    def test_identify_vtt_as_txt(self, tmp_dir):
        """VTT files should be identified as text-based (no OCR needed)."""
        path = tmp_dir / "test.vtt"
        path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello.\n")
        result = self.identifier.identify(path)
        assert result.doc_type == DocumentType.TRANSCRIPT_VTT
        assert result.needs_ocr is False

    def test_identify_python_code(self, tmp_dir):
        """Python files should be correctly identified."""
        path = tmp_dir / "test.py"
        path.write_text("import os\nprint('hello')\n")
        result = self.identifier.identify(path)
        assert result.doc_type == DocumentType.CODE_PYTHON
        assert result.needs_ocr is False


# ── Parser Registry Tests ─────────────────────────────────────────────────────

class TestParserRegistry:
    """Tests for the updated parser registry."""

    def test_registry_has_transcript_parsers(self):
        registry = create_default_registry()
        assert DocumentType.TRANSCRIPT_SRT in registry.supported_types()
        assert DocumentType.TRANSCRIPT_VTT in registry.supported_types()

    def test_registry_has_code_parsers(self):
        registry = create_default_registry()
        for ct in (DocumentType.CODE_PYTHON, DocumentType.CODE_R,
                   DocumentType.CODE_STATA, DocumentType.CODE_JULIA):
            assert ct in registry.supported_types()

    def test_all_standard_parsers_registered(self):
        registry = create_default_registry()
        for dt in (DocumentType.PDF, DocumentType.TXT, DocumentType.CSV,
                   DocumentType.HTML, DocumentType.DOCX):
            assert dt in registry.supported_types(), f"{dt.value} not registered"


# ── Pipeline Integration with New File Types ─────────────────────────────────

class TestPipelineNewFileTypes:
    """End-to-end pipeline tests for newly supported file types."""

    def test_process_srt_through_pipeline(self, tmp_dir):
        path = tmp_dir / "subtitles.srt"
        path.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nWelcome to the seminar.\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nToday we discuss methodology.\n",
            encoding="utf-8",
        )
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.doc_type == DocumentType.TRANSCRIPT_SRT

    def test_process_vtt_through_pipeline(self, tmp_dir):
        path = tmp_dir / "captions.vtt"
        path.write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello everyone.\n",
            encoding="utf-8",
        )
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.doc_type == DocumentType.TRANSCRIPT_VTT

    def test_process_python_file_through_pipeline(self, tmp_dir):
        path = tmp_dir / "analysis.py"
        path.write_text(
            "import pandas as pd\n\ndef load_data(path):\n"
            "    return pd.read_csv(path)\n",
            encoding="utf-8",
        )
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.doc_type == DocumentType.CODE_PYTHON
        assert "python" in doc.metadata.get("language", "").lower()

    def test_process_r_file_through_pipeline(self, tmp_dir):
        path = tmp_dir / "model.r"
        path.write_text("library(ggplot2)\nggplot(data, aes(x, y)) + geom_point()\n")
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        assert doc.status == ProcessingStatus.COMPLETED
        assert doc.doc_type == DocumentType.CODE_R

    def test_stage_history_includes_cleaning_for_new_types(self, tmp_dir):
        """Cleaning and normalization stages should run even for new file types."""
        path = tmp_dir / "subtitles.srt"
        path.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nTest content.\n",
            encoding="utf-8",
        )
        pipeline = DocumentPipeline()
        doc = pipeline.process(path)

        stages = [s["stage"] for s in doc.stage_history]
        assert ProcessingStage.CLEANING.value in stages
        assert ProcessingStage.NORMALIZING.value in stages