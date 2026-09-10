"""
intel/classifier.py — Automatic Document Classifier
=====================================================
Automatically determines document category and PDF rendering type.

Detects:
    Category: research_paper, book, report, presentation, spreadsheet,
              technical_document, legal, medical, code, transcript, etc.
    PDF Type: digital, scanned, hybrid, text_only, image_only

Classification is based on:
    - File extension
    - Text content analysis (headings, structure, keywords)
    - Page count / layout hints
    - Language detection
    - Presence of tables, figures, equations
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.intel.models import (
    DocumentCategory,
    PDFType,
    ClassificationResult,
)


class DocumentClassifier:
    """Classifies documents by category and PDF rendering type."""

    # ── Extension → category mapping ────────────────────────────────────────

    EXTENSION_HINTS: Dict[str, DocumentCategory] = {
        # Primary formats
        ".pdf":  DocumentCategory.RESEARCH_PAPER,
        ".docx": DocumentCategory.TECHNICAL_DOCUMENT,
        ".doc":  DocumentCategory.TECHNICAL_DOCUMENT,
        ".pptx": DocumentCategory.PRESENTATION,
        ".ppt":  DocumentCategory.PRESENTATION,
        ".xlsx": DocumentCategory.SPREADSHEET,
        ".xls":  DocumentCategory.SPREADSHEET,
        # Plain text & markup
        ".txt":  DocumentCategory.UNKNOWN,
        ".md":   DocumentCategory.TECHNICAL_DOCUMENT,
        ".rst":  DocumentCategory.TECHNICAL_DOCUMENT,
        ".rtf":  DocumentCategory.TECHNICAL_DOCUMENT,
        ".html": DocumentCategory.NEWS_ARTICLE,
        ".htm":  DocumentCategory.NEWS_ARTICLE,
        # Academic / publishing
        ".tex":  DocumentCategory.RESEARCH_PAPER,
        ".bib":  DocumentCategory.RESEARCH_PAPER,
        ".epub": DocumentCategory.BOOK,
        # Data formats
        ".csv":  DocumentCategory.SPREADSHEET,
        ".tsv":  DocumentCategory.SPREADSHEET,
        ".json": DocumentCategory.SPREADSHEET,
        ".yaml": DocumentCategory.TECHNICAL_DOCUMENT,
        ".yml":  DocumentCategory.TECHNICAL_DOCUMENT,
        ".xml":  DocumentCategory.TECHNICAL_DOCUMENT,
        # Code
        ".py":   DocumentCategory.CODE,
        ".r":    DocumentCategory.CODE,
        ".do":   DocumentCategory.CODE,
        ".jl":   DocumentCategory.CODE,
        # Transcripts
        ".srt":  DocumentCategory.TRANSCRIPT,
        ".vtt":  DocumentCategory.TRANSCRIPT,
        # Images that may need OCR
        ".tif":  DocumentCategory.UNKNOWN,
        ".tiff": DocumentCategory.UNKNOWN,
        ".png":  DocumentCategory.UNKNOWN,
        ".jpg":  DocumentCategory.UNKNOWN,
        ".jpeg": DocumentCategory.UNKNOWN,
    }

    # ── Academic section keyword patterns ───────────────────────────────────

    SECTION_KEYWORDS: List[Dict[str, Any]] = [
        {"abstract":     r"(?:^|\n)\s*(ABSTRACT|Summary|Overview)\b",                         "score": 10},
        {"introduction": r"(?:^|\n)\s*(Introduction|Intro)\b",                                "score": 8},
        {"background":   r"(?:^|\n)\s*(Background|Literature\s+Review|Related\s+(?:Work|Works))\b", "score": 7},
        {"methodology":  r"(?:^|\n)\s*(Methodology|Methods|Material[sS]s?\s+and\s+Methods)\b",    "score": 8},
        {"data":         r"(?:^|\n)\s*(Data|Dataset|Data\s+Collection|Data\s+Sources?)\b",       "score": 5},
        {"results":      r"(?:^|\n)\s*(Results|Findings|Outcome[sS]|Empirical\s+Results)\b",     "score": 8},
        {"discussion":   r"(?:^|\n)\s*(Discussion|Interpretation|Implications)\b",               "score": 7},
        {"conclusion":   r"(?:^|\n)\s*(Conclusion|Concluding\s+(?:Remarks|Thoughts)|Summary)\b", "score": 6},
        {"acknowledgments": r"(?:^|\n)\s*(Acknowledgments?|Acknowledgements?)\b",                "score": 3},
        {"references":   r"(?:^|\n)\s*(References?|Bibliography|Works\s+Cited)\b",              "score": 5},
        {"appendix":     r"(?:^|\n)\s*(Appendix(?:es)?|Supplementary\s+Material|Additional\s+Material)\b", "score": 4},
        {"figure_caption": r"(?:Figure\s+\d+|Fig\.\s+\d+|Figure\s+Legend)",                     "score": 3},
        {"table_caption": r"(?:Table\s+\d+|Tab\.\s+\d+|Table\s+Caption)",                       "score": 3},
        {"footnote":     r"\[\d+\].*|^\d+[.]\s.*\[(See\s+also|cf\.|c\.?f\.)\b",                "score": 1},
    ]

    # Maximum possible score (sum of all individual scores; used for normalisation).
    MAX_SECTION_SCORE: float = sum(entry["score"] for entry in SECTION_KEYWORDS)

    # ── Content markers per category ────────────────────────────────────────

    _PRESENTATION_MARKERS = [
        r"slide\s*\d+",
        r"\be\b\s*\d+",            # "B1", "A3" style slide refs (less common but seen)
        r"^https?://",             # URLs often appear on slides
        r"©\s+\d{4}",              # Copyright lines
        r"[①②③④⑤⑥⑦⑧⑨⑩]",           # Circled numbers common in slide layouts
    ]

    _CODE_MARKERS = [
        r"^[ \t]*(def |class |import |from |const |let |var |fn |func |pub |struct |enum |trait)",  # noqa: E502
        r"^[ \t]*#[{}\[\]()]",       # Punctuation-heavy first lines
        r"== *code block *==",       # RST literal blocks
    ]

    _SPREADSHEET_MARKERS = [
        r"^\d+[,\.]\d+\s+\d+[,\.]\d+",  # Row of numbers
        r"(?i)\b(column[s]?|row[s]?|cell[s]?|header[s]?)\b",
        r"^\w+\s+\d+\s+\d+\s+\d+$",     # Simple tabular rows
    ]

    _LEGAL_MARKERS = [
        r"(?i)\b(section\s+\d+[-\.]?\s*\w*)\b",
        r"(?i)\bsubsection\s+\d+",
        r"(?i)\bparagraph\s+\d+",
        r"(?i)\bwhereas\b",
        r"(?i)\bhereby\b",
        r"(?i)\bstatute[s]?\b",
        r"(?i)\bcase\s+no\.?\s*\d+",
        r"(?i)\bplaintiff\b.*\bdefendant\b",
    ]

    _MEDICAL_MARKERS = [
        r"(?i)\b(patient|diagnosis|treatment|symptom|clinical|therapy|dosage|prescription)\b",
        r"(?i)\bmedical\s+hierarchy|ICD-\d",
        r"(?i)\b(CT|MRI|X-ray|ultrasound|biopsy)\b",
        r"(?i)\blife expectancy|BMI|pulse rate",
    ]

    _EMAIL_MARKERS = [
        r"^From:\s",
        r"^To:\s",
        r"^Subject:\s",
        r"^Date:\s",
        r"<[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}>",
    ]

    _NEWS_MARKERS = [
        r"(?i)\b(by|reporting|contributing|agency|AP|Reuters|AFP)\b.*\b\d{1,2}[,-]\w{3,8}[,-]\d{2,4}\b",
        r"(?i)\b(HEADLINE|LEAD|Dateline)[:\s]",
        r"(?i)^[A-Z][^.]{10,}\.[^.]{10,}\.[^.]{10,}$",  # ALL-CAPS sentences
    ]

    _BOOK_MARKERS = [
        r"(?i)^part\s+\d+",
        r"(?i)^chapter\s+\d+",
        r"(?i)^volume\s+\d+",
        r"(?i)isbn[:\s]",
        r"(?i)table\s+of\s+contents",
    ]

    def classify(self, file_path: Path | str, text_sample: str = "") -> ClassificationResult:
        """Full classification pipeline. Returns ClassificationResult.

        Parameters
        ----------
        file_path : Path or str
            Path to the document file being classified.
        text_sample : str, optional
            Pre-extracted text content. If empty the classifier will attempt
            to read the raw bytes as UTF-8 to get a sample when the extension
            suggests plain-text content; otherwise it relies solely on the
            extension hint.
        """
        path = Path(file_path).resolve()

        # Start with the extension-based confidence baseline.
        category, ext_confidence = self._classify_by_extension(path)

        reasoning: List[str] = []
        scores: Dict[str, float] = {}
        detected_sections: List[str] = []

        if not text_sample and path.suffix in (".txt", ".md", ".rst", ".html", ".htm"):
            try:
                text_sample = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text_sample = ""

        # Boost category using content analysis when text is available.
        if text_sample:
            content_category, content_score, matches = self._classify_by_content(text_sample)
            if content_score > 0.15:
                # Blend: give more weight to stronger evidence.
                blended = max(ext_confidence, content_score)
                if content_category != DocumentCategory.UNKNOWN:
                    category = content_category
                    ext_confidence = blended
                    detected_sections = list(matches)
            if matches:
                scores["section_density"] = min(content_score, 1.0)
                reasoning.append(
                    f"Content matched sections: {', '.join(sorted(set(matches))[:6])}"
                )

        pdf_type: Optional[PDFType] = None
        # For PDF files attempt to infer rendering type from extracted text length.
        if path.suffix.lower() == ".pdf":
            page_count = self._infer_page_count(text_sample, path)
            pdf_type = self._detect_pdf_type(path, len(text_sample), page_count)
            reasoning.append(f"PDF type inferred as {pdf_type.value}")

        # If no textual evidence was gathered, add an extension-based note.
        if not reasoning:
            suffix = path.suffix
            hint = self.EXTENSION_HINTS.get(suffix, None)
            if hint and hint != DocumentCategory.UNKNOWN:
                reasoning.append(f"Extension .{suffix} maps to {hint.value}")

        result = ClassificationResult(
            category=category,
            pdf_type=pdf_type,
            confidence=round(max(ext_confidence, 0.0), 4),
            scores=scores,
            reasoning=reasoning,
            detected_sections=detected_sections,
        )
        return result

    # ── Internal helpers ────────────────────────────────────────────────────

    def _classify_by_extension(self, path: Path) -> Tuple[DocumentCategory, float]:
        """Map file extension to a likely category with base confidence.

        Returns ``(category, confidence)`` where confidence is at least 0.30
        for known extensions and 0.05 for unrecognized ones.
        """
        ext = path.suffix.lower()
        category = self.EXTENSION_HINTS.get(ext, DocumentCategory.UNKNOWN)
        if category != DocumentCategory.UNKNOWN:
            return category, 0.30
        return category, 0.05

    def _classify_by_content(self, text: str) -> Tuple[DocumentCategory, float, List[str]]:
        """Analyse text for academic / professional structure.

        Scans for section headings, category-specific keywords, and structural
        markers. Returns ``(best_category, normalised_score, list_of_matched_section_names)``.
        """
        combined = "\n" + text + "\n"  # sentinel newlines so ^ anchors work.

        # ── Section heading density ─────────────────────────────────────
        section_scores: Dict[str, float] = {}
        matched_sections: List[str] = []

        for entry in self.SECTION_KEYWORDS:
            label = next(iter(entry))
            regex = entry[label]
            count = len(re.findall(regex, combined, re.IGNORECASE | re.MULTILINE))
            if count > 0:
                section_scores[label] = count * entry["score"]
                matched_sections.extend([label] * count)

        # Normalise section density to [0, 1].
        raw_section_sum = sum(section_scores.values())
        section_density = min(raw_section_sum / self.MAX_SECTION_SCORE, 1.0)

        # ── Category keyword probes ─────────────────────────────────────
        probe_patterns: Dict[str, List[str]] = {
            "research_paper": self.SECTION_KEYWORDS,  # sections themselves are strong signals.
            "presentation":   self._PRESENTATION_MARKERS,
            "spreadsheet":    self._SPREADSHEET_MARKERS,
            "code":           self._CODE_MARKERS,
            "legal":          self._LEGAL_MARKERS,
            "medical":        self._MEDICAL_MARKERS,
            "email":          self._EMAIL_MARKERS,
            "news_article":   self._NEWS_MARKERS,
            "book":           self._BOOK_MARKERS,
        }

        category_scores: Dict[str, float] = {}

        for cat, patterns in probe_patterns.items():
            hits = 0
            for pat in patterns:
                if isinstance(pat, dict):
                    # Section keyword dicts keyed by label.
                    label = next(iter(pat))
                    regex = pat[label]
                    hits += len(re.findall(regex, combined, re.IGNORECASE | re.MULTILINE))
                else:
                    hits += len(re.findall(pat, text, re.IGNORECASE))
            category_scores[cat] = hits

        # If canonical academic structure is present, favour research_paper.
        # This lets Markdown/Obsidian notes that contain paper-like structure
        # classify by research semantics instead of by storage format.
        academic_core = {
            "abstract",
            "introduction",
            "methodology",
            "methods",
            "data",
            "results",
            "discussion",
            "conclusion",
            "references",
        }
        if len(set(matched_sections) & academic_core) >= 2:
            category_scores["research_paper"] = category_scores.get("research_paper", 0) + 10

        # If section density is strong, favour research_paper.
        if section_density > 0.6:
            category_scores["research_paper"] = section_scores.get("research_paper", 0) + 20
        elif section_density > 0.3:
            category_scores["research_paper"] = category_scores.get("research_paper", 0) + 10

        # Pick best match.
        if not category_scores:
            return DocumentCategory.UNKNOWN, 0.0, []

        best_cat = max(category_scores, key=category_scores.get)  # type: ignore[arg-type]
        best_raw = category_scores[best_cat]

        # Translate raw hit-count into a confidence-like score.
        total_probes = sum(len(v) for v in probe_patterns.values())
        confidence = min(best_raw / max(total_probes, 1) * 2, 1.0)

        return DocumentCategory(best_cat), confidence, matched_sections

    def _detect_pdf_type(
        self,
        file_path: Path,
        text_length: int,
        page_count: int,
    ) -> PDFType:
        """Determine whether a PDF is digital, scanned, hybrid, text_only, or image_only.

        The logic relies on how much extractable text exists relative to
        expected page counts.

        Parameters
        ----------
        file_path : Path
            The PDF file (used only to check image extensions).
        text_length : int
            Total number of characters extracted from the document.
        page_count : int
            Inferred or explicit page count.
        """
        # Images are always treated as image-only regardless of text extraction.
        ext = file_path.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            return PDFType.IMAGE_ONLY

        if page_count <= 0:
            return PDFType.TEXT_ONLY

        chars_per_page = text_length / page_count

        if chars_per_page < 1:
            # Virtually no extractable text → scanned pages.
            return PDFType.SCANNED
        elif chars_per_page < 10:
            return PDFType.TEXT_ONLY

        # Between 10 and 2000 chars/page could be hybrid or digital.
        # Heuristic: scanned PDFs tend to produce very noisy, sparse text.
        if 10 < chars_per_page < 50:
            return PDFType.HYBRID
        elif chars_per_page >= 50 and chars_per_page < 500:
            # Substantial text per page — likely digital with occasional images.
            return PDFType.HYBRID if chars_per_page < 150 else PDFType.DIGITAL
        else:
            # Very dense text → clearly digital.
            return PDFType.DIGITAL

    def _count_section_matches(self, text: str) -> Dict[str, int]:
        """Count how many section-type headings appear in *text*.

        Returns a dictionary mapping section-label → occurrence-count.
        This method is provided as a standalone utility for callers that need
        raw section counts rather than a full classification.
        """
        combined = "\n" + text + "\n"
        counts: Dict[str, int] = {}
        for entry in self.SECTION_KEYWORDS:
            label = next(iter(entry))
            regex = entry[label]
            counts[label] = len(re.findall(regex, combined, re.IGNORECASE | re.MULTILINE))
        return counts

    @staticmethod
    def infer_category_from_score(scores: Dict[str, float]) -> Tuple[DocumentCategory, float]:
        """Pick the best-matching category from a scoring dictionary.

        Parameters
        ----------
        scores : dict
            Mapping of category-key → numeric score. Keys can be either
            ``DocumentCategory`` values or their string equivalents.

        Returns
        -------
        (category, confidence)
        """
        if not scores:
            return DocumentCategory.UNKNOWN, 0.0

        max_key = max(scores, key=lambda k: scores[k])  # type: ignore[arg-type]

        # Normalise confidence as fraction of top-score over second-best.
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[1] > 0:
            confidence = sorted_scores[0] / sorted_scores[1]
            confidence = min(confidence / 2.0, 1.0)  # clamp
        else:
            confidence = 1.0 if sorted_scores[0] > 0 else 0.0

        if isinstance(max_key, DocumentCategory):
            category = max_key
        else:
            # Attempt string → enum resolution.
            try:
                category = DocumentCategory(max_key)
            except ValueError:
                category = DocumentCategory.UNKNOWN

        return category, round(confidence, 4)

    # ── Auxiliary ───────────────────────────────────────────────────────────

    @staticmethod
    def _infer_page_count(text_sample: str, path: Path) -> int:
        """Estimate the number of pages from text content.

        Uses simple heuristics when no explicit page metadata is available:
        blank-line blocks (>= 5 consecutive newlines) suggest page breaks.
        Otherwise falls back to a rough word-count estimate (~250 words per page).
        """
        if not text_sample:
            return 1

        # Heuristic 1: large vertical gaps often indicate page boundaries.
        breaks = len(re.findall(r"\n{5,}", text_sample))
        if breaks > 0:
            return breaks + 1

        # Heuristic 2: ~250 words per page (industry average).
        word_count = len(text_sample.split())
        return max(1, round(word_count / 250))


# ── Public convenience function ─────────────────────────────────────────────

def classify_document(file_path: Path | str, text_sample: str = "") -> ClassificationResult:
    """Quick one-call classification with default settings.

    Parameters
    ----------
    file_path : Path or str
        Path to the document file.
    text_sample : str, optional
        Pre-extracted text content for richer scoring.
    """
    return DocumentClassifier().classify(file_path, text_sample)
