"""
registry.py — Literature Provider Registry (EPIC 09)
====================================================
Pluggable provider collection. New academic sources are added by
implementing ``LiteratureProvider`` and registering an instance —
no engine changes required.

``default_registry()`` wires the six shipped sources (OpenAlex,
Semantic Scholar, Crossref, PubMed, ArXiv, SSRN) with shared
configuration (API keys, politeness mailto, result caps).
"""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Mapping, Optional

from literature.search.arxiv_provider import ArXivProvider
from literature.search.base import LiteratureProvider
from literature.search.crossref_provider import CrossrefProvider
from literature.search.openalex_provider import OpenAlexProvider
from literature.search.pubmed_provider import PubMedProvider
from literature.search.semantic_scholar_provider import SemanticScholarProvider
from literature.search.ssrn_provider import SSRNProvider
from literature.search.transport import HttpTransport, TransportConfig

# Order matters: earlier providers are preferred for anchor resolution.
DEFAULT_PROVIDER_ORDER = (
    "openalex",
    "semantic_scholar",
    "crossref",
    "pubmed",
    "arxiv",
    "ssrn",
)


class LiteratureProviderRegistry:
    """Name-keyed, ordered collection of literature providers."""

    def __init__(self, providers: Iterable[LiteratureProvider] = ()) -> None:
        self._providers: Dict[str, LiteratureProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: LiteratureProvider, replace: bool = False) -> None:
        if provider.name in self._providers and not replace:
            raise ValueError(f"provider '{provider.name}' is already registered")
        self._providers[provider.name] = provider

    def unregister(self, name: str) -> Optional[LiteratureProvider]:
        return self._providers.pop(name, None)

    def get(self, name: str) -> Optional[LiteratureProvider]:
        return self._providers.get(name)

    def names(self) -> List[str]:
        return list(self._providers.keys())

    def providers(self) -> List[LiteratureProvider]:
        return list(self._providers.values())

    def available(self) -> List[LiteratureProvider]:
        return [provider for provider in self._providers.values() if provider.is_configured()]

    def __iter__(self) -> Iterator[LiteratureProvider]:
        return iter(self.providers())

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        return name in self._providers


def default_registry(
    api_keys: Optional[Mapping[str, str]] = None,
    mailto: str = "",
    max_results: int = 25,
    enabled: Optional[Iterable[str]] = None,
    transport_factory=None,
) -> LiteratureProviderRegistry:
    """Build the standard six-provider registry.

    Parameters
    ----------
    api_keys:
        Optional mapping ``provider name → api key`` (Semantic Scholar and
        PubMed accept keys; the others work keyless).
    mailto:
        Contact email for the OpenAlex / Crossref polite pools.
    max_results:
        Per-call result cap applied to every provider.
    enabled:
        Optional whitelist of provider names (defaults to all shipped).
    transport_factory:
        Optional zero-arg callable returning an ``HttpTransport``; tests use
        this to inject fakes. ArXiv keeps its own courtesy-paced transport
        unless one is supplied.
    """
    keys = dict(api_keys or {})
    enabled_names = set(enabled) if enabled is not None else set(DEFAULT_PROVIDER_ORDER)

    def _transport() -> Optional[HttpTransport]:
        return transport_factory() if transport_factory else None

    shared = dict(max_results=max_results)
    candidates: List[LiteratureProvider] = [
        OpenAlexProvider(transport=_transport(), mailto=mailto, **shared),
        SemanticScholarProvider(
            transport=_transport(), api_key=keys.get("semantic_scholar", ""), **shared
        ),
        CrossrefProvider(transport=_transport(), mailto=mailto, **shared),
        PubMedProvider(transport=_transport(), api_key=keys.get("pubmed", ""), **shared),
        ArXivProvider(
            transport=_transport() or HttpTransport(TransportConfig(min_interval=3.0)), **shared
        ),
        SSRNProvider(transport=_transport(), mailto=mailto, **shared),
    ]

    registry = LiteratureProviderRegistry()
    for provider in candidates:
        if provider.name in enabled_names:
            registry.register(provider)
    return registry
