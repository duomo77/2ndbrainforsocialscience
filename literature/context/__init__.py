"""
literature.context — Scientific Knowledge Expansion (EPIC 09)
=============================================================
Expands an imported paper into its surrounding scientific context:
related, influential, review, systematic-review, meta-analysis,
replication, contradictory and newer follow-up work — with evidence
strength scoring and full retrieval provenance.
"""

from literature.context.models import (
    CATEGORY_DISPLAY,
    CATEGORY_PRIORITY,
    SCIENTIFIC_CONTEXT_ENGINE_VERSION,
    SCIENTIFIC_CONTEXT_SCHEMA_VERSION,
    ContextCategory,
    ContextPaper,
    EvidenceAssessment,
    EvidenceLevel,
    ProviderProvenance,
    ScientificContext,
)
from literature.context.classifier import (
    ClassificationResult,
    ClassifierConfig,
    ContextClassifier,
    title_overlap,
    tokenize_title,
)
from literature.context.evidence import EvidenceStrengthScorer
from literature.context.engine import (
    ContextExpansionConfig,
    ScientificContextEngine,
    extract_doi_from_text,
    seed_from_fields,
    slugify_title,
)
from literature.context.markdown import render_scientific_context, write_outputs
from literature.context.graph import (
    CATEGORY_RELATIONSHIP,
    build_graph_mutation,
    ingest_scientific_context,
)
from literature.context.importer import (
    attach_scientific_context,
    expand_document_context,
    seed_from_document,
)

__all__ = [
    "CATEGORY_DISPLAY",
    "CATEGORY_PRIORITY",
    "SCIENTIFIC_CONTEXT_ENGINE_VERSION",
    "SCIENTIFIC_CONTEXT_SCHEMA_VERSION",
    "ContextCategory",
    "ContextPaper",
    "EvidenceAssessment",
    "EvidenceLevel",
    "ProviderProvenance",
    "ScientificContext",
    "ClassificationResult",
    "ClassifierConfig",
    "ContextClassifier",
    "title_overlap",
    "tokenize_title",
    "EvidenceStrengthScorer",
    "ContextExpansionConfig",
    "ScientificContextEngine",
    "extract_doi_from_text",
    "seed_from_fields",
    "slugify_title",
    "render_scientific_context",
    "write_outputs",
    "CATEGORY_RELATIONSHIP",
    "build_graph_mutation",
    "ingest_scientific_context",
    "attach_scientific_context",
    "expand_document_context",
    "seed_from_document",
]
