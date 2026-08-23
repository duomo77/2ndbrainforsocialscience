"""
literature — Academic Literature Discovery & Scientific Context (EPIC 09)
=========================================================================
Public API for the Research Operating System's literature layer:

  * ``literature.search``  — pluggable academic providers (OpenAlex,
    Semantic Scholar, Crossref, PubMed, ArXiv, SSRN) behind one registry
  * ``literature.context`` — scientific knowledge expansion: given one
    paper, retrieve and classify its surrounding literature, score the
    evidence strength and generate SCIENTIFIC_CONTEXT.md
"""

__version__ = "1.0.0"

from literature.search import (
    ArXivProvider,
    CrossrefProvider,
    HttpTransport,
    LiteratureProvider,
    LiteratureProviderRegistry,
    LiteratureSource,
    OpenAlexProvider,
    PubMedProvider,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    SemanticScholarProvider,
    SSRNProvider,
    TransportConfig,
    TransportError,
    default_registry,
)
from literature.context import (
    ContextCategory,
    ContextPaper,
    EvidenceLevel,
    ScientificContext,
    ScientificContextEngine,
    attach_scientific_context,
    expand_document_context,
    render_scientific_context,
    seed_from_document,
    seed_from_fields,
    write_outputs,
)

__all__ = [
    "__version__",
    # search
    "ArXivProvider",
    "CrossrefProvider",
    "HttpTransport",
    "LiteratureProvider",
    "LiteratureProviderRegistry",
    "LiteratureSource",
    "OpenAlexProvider",
    "PubMedProvider",
    "RetrievedPaper",
    "RetrievalChannel",
    "SeedPaper",
    "SemanticScholarProvider",
    "SSRNProvider",
    "TransportConfig",
    "TransportError",
    "default_registry",
    # context
    "ContextCategory",
    "ContextPaper",
    "EvidenceLevel",
    "ScientificContext",
    "ScientificContextEngine",
    "attach_scientific_context",
    "expand_document_context",
    "render_scientific_context",
    "seed_from_document",
    "seed_from_fields",
    "write_outputs",
]
