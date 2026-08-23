"""
literature.search — Pluggable academic literature retrieval (EPIC 09)
=====================================================================
Providers for OpenAlex, Semantic Scholar, Crossref, PubMed, ArXiv and SSRN,
plus the registry that makes additional sources a drop-in extension.
"""

from literature.search.base import LiteratureProvider
from literature.search.models import (
    LiteratureSource,
    RetrievedPaper,
    RetrievalChannel,
    SeedPaper,
    normalize_doi,
    normalize_title,
    to_metadata_source,
)
from literature.search.transport import HttpTransport, TransportConfig, TransportError
from literature.search.openalex_provider import OpenAlexProvider
from literature.search.semantic_scholar_provider import SemanticScholarProvider
from literature.search.crossref_provider import CrossrefProvider
from literature.search.pubmed_provider import PubMedProvider
from literature.search.arxiv_provider import ArXivProvider
from literature.search.ssrn_provider import SSRNProvider
from literature.search.registry import (
    DEFAULT_PROVIDER_ORDER,
    LiteratureProviderRegistry,
    default_registry,
)

__all__ = [
    "LiteratureProvider",
    "LiteratureSource",
    "RetrievedPaper",
    "RetrievalChannel",
    "SeedPaper",
    "normalize_doi",
    "normalize_title",
    "to_metadata_source",
    "HttpTransport",
    "TransportConfig",
    "TransportError",
    "OpenAlexProvider",
    "SemanticScholarProvider",
    "CrossrefProvider",
    "PubMedProvider",
    "ArXivProvider",
    "SSRNProvider",
    "DEFAULT_PROVIDER_ORDER",
    "LiteratureProviderRegistry",
    "default_registry",
]
