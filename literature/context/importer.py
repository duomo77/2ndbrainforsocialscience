"""
importer.py — Document Import Integration (EPIC 09)
===================================================
Connects scientific context expansion to the document import pipeline
(``core.pipeline``) without altering existing pipeline behaviour:

  * ``seed_from_document``      — derive a SeedPaper from a processed
                                  pipeline Document (title / DOI / authors
                                  heuristics over parsed metadata)
  * ``attach_scientific_context`` — post-import hook: expand, persist the
                                  SCIENTIFIC_CONTEXT.md outputs and record
                                  their paths on ``document.metadata``
  * ``expand_document_context`` — one-shot import + expansion entry point

All imports of the document pipeline are lazy so the literature package
stays importable (and testable) without the pipeline's dependencies.
Expansion failures are recorded as document warnings, never fatal.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

from literature.context.engine import (  # noqa: F401 (re-export)
    ContextExpansionConfig,
    ScientificContextEngine,
    extract_doi_from_text,
    seed_from_fields,
)
from literature.context.models import ScientificContext
from literature.search.models import SeedPaper

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def seed_from_document(document: Any) -> SeedPaper:
    """Build a SeedPaper from a ``core.pipeline.models.Document``.

    Tolerates missing metadata: falls back from explicit metadata keys to
    heuristics over the parsed text (first line → title, DOI regex, year
    regex). Returns an empty seed only when nothing usable exists.
    """
    metadata = getattr(document, "metadata", {}) or {}

    text = (
        metadata.get("normalized_text")
        or metadata.get("cleaned_text")
        or metadata.get("parsed_text")
        or ""
    )

    title = str(metadata.get("title") or "").strip()
    if not title:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) >= 8:
                title = stripped[:300]
                break

    doi = metadata.get("doi") or extract_doi_from_text(text[:5000])

    authors = metadata.get("authors") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in re.split(r"\s*(?:,|and|;)\s*", authors) if part.strip()]
    authors = tuple(str(author) for author in authors if str(author).strip())

    year = metadata.get("year")
    if not isinstance(year, int):
        match = _YEAR_PATTERN.search(f"{title}\n{text[:1500]}")
        year = int(match.group(0)) if match else None

    abstract = str(metadata.get("abstract") or "").strip()

    return seed_from_fields(
        title=title,
        doi=doi or "",
        authors=authors,
        year=year,
        abstract=abstract,
        venue=str(metadata.get("venue") or metadata.get("journal") or ""),
    )


def attach_scientific_context(
    document: Any,
    engine: Optional[ScientificContextEngine] = None,
    output_dir: Optional[Path] = None,
    write: bool = True,
) -> Any:
    """Expand a processed document into its scientific context.

    Stores the outcome on ``document.metadata['scientific_context']`` and
    returns the document. Never raises: expansion problems become document
    warnings so the import itself always succeeds (backward compatible).
    """
    seed = seed_from_document(document)
    if seed.is_empty():
        _record_warning(document, "scientific context skipped: no title or DOI found")
        return document

    if engine is None:
        engine = _load_default_engine()

    result = engine.expand(seed)
    if not result.ok:
        _record_warning(document, f"scientific context expansion failed: {result.error}")
        return document

    context: ScientificContext = result.value
    record = {
        "status": "ok",
        "paper_count": context.total_papers,
        "evidence_level": context.evidence.level.value,
        "evidence_score": context.evidence.score,
        "category_counts": context.summary_counts(),
        "providers": [prov.to_dict() for prov in context.provider_provenance],
    }

    if write:
        try:
            from literature.context.markdown import write_outputs

            md_path, json_path = write_outputs(context, output_dir)
            record["markdown_path"] = str(md_path)
            record["json_path"] = str(json_path)
        except Exception as exc:
            _record_warning(document, f"scientific context outputs not written: {exc}")

    document.metadata["scientific_context"] = record
    return document


def expand_document_context(
    file_path: Path | str,
    engine: Optional[ScientificContextEngine] = None,
    output_dir: Optional[Path] = None,
) -> Tuple[Any, Optional[ScientificContext]]:
    """Import a document through the pipeline, then expand its context.

    Returns ``(document, context_or_none)``. The pipeline runs exactly as
    before; expansion is a post-import step layered on top.
    """
    from core.pipeline.models import ProcessingStatus
    from core.pipeline.pipeline import DocumentPipeline

    document = DocumentPipeline().process(file_path)
    if document.status != ProcessingStatus.COMPLETED:
        return document, None

    seed = seed_from_document(document)
    if seed.is_empty():
        _record_warning(document, "scientific context skipped: no title or DOI found")
        return document, None

    active_engine = engine or _load_default_engine()
    result = active_engine.expand(seed)
    if not result.ok:
        _record_warning(document, f"scientific context expansion failed: {result.error}")
        return document, None

    context = result.value
    record = {
        "status": "ok",
        "paper_count": context.total_papers,
        "evidence_level": context.evidence.level.value,
        "category_counts": context.summary_counts(),
    }
    try:
        from literature.context.markdown import write_outputs

        md_path, json_path = write_outputs(context, output_dir)
        record["markdown_path"] = str(md_path)
        record["json_path"] = str(json_path)
    except Exception as exc:
        _record_warning(document, f"scientific context outputs not written: {exc}")
    document.metadata["scientific_context"] = record
    return document, context


# ── internals ────────────────────────────────────────────────────────────────


def _load_default_engine() -> ScientificContextEngine:
    try:
        from core.engine_loader import get_scientific_context_engine

        engine = get_scientific_context_engine()
        if engine is not None:
            return engine
    except Exception:
        pass
    return ScientificContextEngine()


def _record_warning(document: Any, message: str) -> None:
    recorder = getattr(document, "record_warning", None)
    if callable(recorder):
        recorder(message)
        return
    warnings: List[str] = getattr(document, "warnings", [])
    warnings.append(message)
