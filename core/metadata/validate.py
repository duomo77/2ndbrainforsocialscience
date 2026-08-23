"""
metadata/validate.py — Metadata Validation Framework
=======================================================
Validates extracted metadata for completeness, correctness, and consistency.

Generates validation reports with severity levels:
    INFO, WARNING, ERROR, CRITICAL
"""

from __future__ import annotations
import re
from typing import Dict, List

from core.metadata.models import (
    CompleteMetadata, ValidationResult, ValidationSeverity,
    BibliographicMetadata, ResearchMetadata, CitationMetadata, DocumentMeta,
)


class MetadataValidator:
    """Validate metadata completeness and correctness."""

    # Required fields per document category
    REQUIRED_FIELDS = {
        "research_paper": {"title", "authors", "publication_date"},
        "book": {"title", "authors", "publisher", "publication_date"},
        "report": {"title", "authors"},
        "presentation": {"title"},
        "dataset": {"title", "data_source"},
        "unknown": set(),
    }

    DOI_PATTERN = re.compile(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', re.I)
    URL_PATTERN = re.compile(r'https?://')

    def validate(
        self, metadata: CompleteMetadata, doc_type: str = "unknown"
    ) -> ValidationResult:
        """Full validation pipeline. Returns ValidationResult."""
        report = ValidationResult()

        biblio = metadata.bibliographic
        research = metadata.research
        citations = metadata.citations

        self._check_required_fields(biblio, doc_type, report)
        self._validate_bibliographic(biblio, report)
        self._validate_research(research, biblio, report)
        self._validate_citations(citations, report)
        self._check_consistency(biblio, research, citations, metadata.document, report)

        return report

    # ── Internal checks ────────────────────────────────────────────────────

    def _check_required_fields(
        self, biblio: BibliographicMetadata, doc_type: str, report: ValidationResult
    ):
        """Check required fields based on document type."""
        required = self.REQUIRED_FIELDS.get(doc_type, self.REQUIRED_FIELDS["unknown"])
        field_map = {
            "title": biblio.title,
            "authors": biblio.authors,
            "publisher": biblio.publisher,
            "publication_date": biblio.publication_date,
        }

        for req in sorted(required):
            val = field_map.get(req)
            if isinstance(val, list):
                present = len(val) > 0
            elif val is not None:
                present = True
            else:
                present = False
            if not present:
                report.add_issue(
                    ValidationSeverity.ERROR, req,
                    f"Required field '{req}' is missing or empty",
                )

        # Dataset-specific extra check
        if doc_type == "dataset" and biblio.research_field:
            pass  # dataset has different structure

    def _validate_bibliographic(
        self, biblio: BibliographicMetadata, report: ValidationResult
    ):
        """Validate bibliographic metadata fields."""
        # DOI format
        if biblio.doi and not self.is_valid_doi(biblio.doi):
            report.add_issue(ValidationSeverity.ERROR, "doi",
                             f"Invalid DOI format: {biblio.doi}")

        # Date format (best-effort ISO-like check)
        if biblio.publication_date:
            date_pat = re.compile(r'^\d{4}(-\d{1,2}(-\d{1,2})?)?$')
            if not date_pat.match(biblio.publication_date):
                report.add_issue(ValidationSeverity.WARNING, "publication_date",
                                 f"Date may not be ISO-8601: {biblio.publication_date}")

        # Academic papers should have journal/conference/publisher
        if biblio.abstract_text:  # heuristic: paper with abstract
            has_venue = bool(biblio.journal or biblio.conference or biblio.publisher)
            if not has_venue:
                report.add_issue(ValidationSeverity.INFO, "journal_or_conference",
                                 "Paper likely needs a journal, conference, or publisher")

        # URL patterns
        if biblio.url and not self.looks_like_url(biblio.url):
            report.add_issue(ValidationSeverity.WARNING, "url",
                             "URL does not match expected pattern")

    @staticmethod
    def _validate_research(
        research: ResearchMetadata, biblio: BibliographicMetadata,
        report: ValidationResult
    ):
        """Validate research-specific metadata."""
        # Variables sanity
        if research.variables:
            for var_name, var_list in research.variables.items():
                if not var_list:
                    report.add_issue(ValidationSeverity.WARNING, f"variables.{var_name}",
                                     f"Variable list '{var_name}' is empty")

        # Methodology terms (common known methodologies)
        known_methods = {
            "quantitative", "qualitative", "mixed methods", "survey",
            "experiment", "regression", "case study", "meta-analysis",
            "longitudinal", "cross-sectional", "panel", "diff-in-diff",
            "instrumental variables", "propensity score matching",
            "event study", "natural experiment",
        }
        if research.methodology:
            meth_lower = research.methodology.lower()
            # Only warn if completely unrecognised and non-empty
            if meth_lower and not any(m in meth_lower for m in known_methods):
                report.add_issue(ValidationSeverity.INFO, "methodology",
                                 f"Methodology '{research.methodology}' not in common taxonomy")

    def _validate_citations(
        self, citations: CitationMetadata, report: ValidationResult
    ):
        """Validate citation metadata."""
        for i, ref in enumerate(citations.references):
            if not ref.authors and not ref.text:
                report.add_issue(ValidationSeverity.WARNING, f"references[{i}]",
                                 "Reference entry missing both author and text")
            if not ref.title:
                report.add_issue(ValidationSeverity.WARNING, f"references[{i}].title",
                                 "Reference entry missing title")
            if ref.year is None:
                report.add_issue(ValidationSeverity.WARNING, f"references[{i}].year",
                                 "Reference entry missing year")

        # Citation count consistency
        if citations.references and citations.citation_count != len(citations.references):
            report.add_issue(ValidationSeverity.WARNING, "citation_count",
                             f"Citation count ({citations.citation_count}) differs from "
                             f"reference list length ({len(citations.references)})")

    def _check_consistency(
        self, biblio: BibliographicMetadata, research: ResearchMetadata,
        citations: CitationMetadata, document: DocumentMeta,
        report: ValidationResult
    ):
        """Cross-field consistency checks."""
        # Word count vs page count ratio
        if document.word_count > 0 and document.page_count > 0:
            ratio = document.word_count / document.page_count
            if ratio < 50 or ratio > 1500:
                report.add_issue(ValidationSeverity.WARNING, "word_page_ratio",
                                 f"Word/page ratio ({ratio:.0f}) seems unusual")

        # Abstract length sanity
        if biblio.abstract_text:
            length = len(biblio.abstract_text.split())
            if length < 20:
                report.add_issue(ValidationSeverity.WARNING, "abstract",
                                 f"Abstract very short ({length} words)")
            elif length > 10000:
                report.add_issue(ValidationSeverity.WARNING, "abstract",
                                 f"Abstract unusually long ({length} words)")

        # DOI + ISSN coexistence for journals
        if biblio.doi and biblio.issn:
            report.add_issue(ValidationSeverity.INFO, "doi_issn",
                             "Both DOI and ISSN present — ensure they refer to same item")

    # ── Static helpers ─────────────────────────────────────────────────────

    @staticmethod
    def is_valid_doi(doi: str) -> bool:
        """Check if DOI matches valid format."""
        return bool(MetadataValidator.DOI_PATTERN.match(doi.strip()))

    @staticmethod
    def looks_like_url(url: str) -> bool:
        """Check if string matches URL pattern."""
        return bool(MetadataValidator.URL_PATTERN.match(url.strip()))

    @staticmethod
    def parse_authors(raw: str) -> List[str]:
        """Extract individual author names from a raw comma-separated string."""
        if not raw:
            return []
        # Split by common separators: "and", ",", ";"
        parts = re.split(r'\band\b|[,;]', raw)
        authors = [p.strip() for p in parts if p.strip()]
        # Clean up each author name
        cleaned = []
        for a in authors:
            a = re.sub(r'\s+', ' ', a).strip()
            if a:
                cleaned.append(a)
        return cleaned

    @staticmethod
    def _normalize_for_comparison(name: str) -> str:
        """Lowercase, strip trailing suffixes used for dedup comparison."""
        s = name.strip().lower()
        s = re.sub(r'\s*(ph\.?d|md|jr\.?|sr\.?|ii|iii|iv|v)\s*$', '', s)
        s = re.sub(r'[^a-z\s]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def check_duplicate_authors(self, authors: List[str]) -> List[str]:
        """Detect ambiguous/duplicate author entries."""
        seen: Dict[str, str] = {}   # normalized → original
        duplicates: List[str] = []
        for author in authors:
            norm = self._normalize_for_comparison(author)
            if norm and norm in seen:
                if seen[norm] not in duplicates:
                    duplicates.append(seen[norm])
                if author not in duplicates:
                    duplicates.append(author)
            else:
                seen.setdefault(norm, author)
        return duplicates


def validate_metadata(
    metadata: CompleteMetadata, doc_type: str = "unknown"
) -> ValidationResult:
    """Convenience function: quick validation."""
    return MetadataValidator().validate(metadata, doc_type)
