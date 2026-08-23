"""
interfaces.py — Core System Interfaces
=======================================
Abstract base classes defining contracts for all swappable components.
These are purely additive — no existing code is modified.

Interfaces:
    - OCREngine: Document text extraction
    - DocumentParser: Multi-format document parsing
    - EmbeddingProvider: Text → vector conversion
    - SearchProvider: Semantic/keyword search over vault
    - StorageProvider: Persistent storage backend
    - GraphProvider: Knowledge graph operations
    - ResearchAgent: Autonomous research task execution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Base Provider Interface ──────────────────────────────────────────────────

class BaseProvider(ABC):
    """Root interface for all providers in the system."""

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the provider with configuration. Return True on success."""
        ...

    @abstractmethod
    def health_check(self) -> Tuple[bool, str]:
        """Check provider health. Returns (is_healthy, status_message)."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources and shut down the provider."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider version string."""
        ...

# ── OCR Engine Interface ─────────────────────────────────────────────────────

@dataclass
class OCRResult:
    """Result from OCR processing."""
    text: str
    page_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    processing_time_ms: float = 0.0

class OCREngine(BaseProvider):
    """Interface for OCR (Optical Character Recognition) engines."""

    @abstractmethod
    def extract_text(self, file_path: Path, **options) -> OCRResult:
        """Extract text from a document file.

        Args:
            file_path: Path to the document
            **options: Engine-specific options (dpi, language, pages, etc.)

        Returns:
            OCRResult with extracted text and metadata
        """
        ...

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract document metadata (author, title, page count, etc.).

        Args:
            file_path: Path to the document

        Returns:
            Dictionary of metadata
        """
        ...

    @abstractmethod
    def supported_formats(self) -> List[str]:
        """List of supported file extensions."""
        ...

# ── Document Parser Interface ────────────────────────────────────────────────

@dataclass
class ParseResult:
    """Result from document parsing."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    input_type: str = "unknown"
    chunks: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0

class DocumentParser(BaseProvider):
    """Interface for document parsing engines."""

    @abstractmethod
    def parse(self, file_path: Path, **options) -> ParseResult:
        """Parse a document file into structured text and metadata.

        Args:
            file_path: Path to the document
            **options: Parser-specific options

        Returns:
            ParseResult with extracted content
        """
        ...

    @abstractmethod
    def detect_type(self, file_path: Path) -> str:
        """Detect the input type of a file (paper, transcript, dataset, etc.)."""
        ...

    @abstractmethod
    def supported_formats(self) -> List[str]:
        """List of supported file extensions."""
        ...

# ── Embedding Provider Interface ─────────────────────────────────────────────

@dataclass
class EmbeddingResult:
    """Result from embedding generation."""
    embeddings: List[List[float]]
    model_name: str
    dimension: int
    token_count: int
    processing_time_ms: float = 0.0

class EmbeddingProvider(BaseProvider):
    """Interface for text embedding providers."""

    @abstractmethod
    def embed(self, texts: List[str], **options) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            **options: Provider-specific options

        Returns:
            EmbeddingResult with vectors and metadata
        """
        ...

    @abstractmethod
    def embed_query(self, query: str, **options) -> List[float]:
        """Generate embedding for a single query string.

        Args:
            query: Search query string
            **options: Provider-specific options

        Returns:
            Single embedding vector
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output dimension of embeddings."""
        ...

    @abstractmethod
    def supported_models(self) -> List[str]:
        """List of supported embedding models."""
        ...

# ── Search Provider Interface ────────────────────────────────────────────────

@dataclass
class SearchResult:
    """Single search result."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResponse:
    """Response from a search query."""
    query: str
    results: List[SearchResult]
    total_count: int
    search_time_ms: float = 0.0
    search_type: str = "semantic"

class SearchProvider(BaseProvider):
    """Interface for search providers (semantic, keyword, hybrid)."""

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        **options,
    ) -> SearchResponse:
        """Execute a search query.

        Args:
            query: Search query string
            top_k: Number of results to return
            filters: Optional metadata filters
            **options: Provider-specific options

        Returns:
            SearchResponse with ranked results
        """
        ...

    @abstractmethod
    def index(self, texts: List[str], metadata: List[Dict[str, Any]], **options) -> int:
        """Index documents for search. Returns count of indexed items."""
        ...

    @abstractmethod
    def delete(self, ids: List[str]) -> int:
        """Delete documents from the index. Returns count of deleted items."""
        ...

    @property
    @abstractmethod
    def index_size(self) -> int:
        """Number of documents in the index."""
        ...

# ── Storage Provider Interface ───────────────────────────────────────────────

class StorageProvider(BaseProvider):
    """Interface for persistent storage backends."""

    @abstractmethod
    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Retrieve a value by key."""
        ...

    @abstractmethod
    def put(self, key: str, value: Any, namespace: str = "default") -> bool:
        """Store a value by key. Returns True on success."""
        ...

    @abstractmethod
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a value by key. Returns True if deleted."""
        ...

    @abstractmethod
    def exists(self, key: str, namespace: str = "default") -> bool:
        """Check if a key exists."""
        ...

    @abstractmethod
    def list_keys(self, namespace: str = "default", prefix: str = "") -> List[str]:
        """List keys in a namespace, optionally filtered by prefix."""
        ...

    @abstractmethod
    def clear(self, namespace: str = "default") -> int:
        """Clear all entries in a namespace. Returns count of deleted items."""
        ...

# ── Graph Provider Interface ─────────────────────────────────────────────────

@dataclass
class GraphNode:
    """Node in a knowledge graph."""
    id: str
    type: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GraphEdge:
    """Edge connecting two nodes in a knowledge graph."""
    id: str
    source_id: str
    target_id: str
    type: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

class GraphProvider(BaseProvider):
    """Interface for knowledge graph providers."""

    @abstractmethod
    def add_node(self, node: GraphNode) -> bool:
        """Add or update a node. Returns True if successful."""
        ...

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> bool:
        """Add or update an edge. Returns True if successful."""
        ...

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        ...

    @abstractmethod
    def get_neighbors(self, node_id: str, edge_type: Optional[str] = None) -> List[Tuple[GraphNode, GraphEdge]]:
        """Get neighbors of a node, optionally filtered by edge type."""
        ...

    @abstractmethod
    def query(
        self,
        node_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[GraphNode]:
        """Query nodes by type and/or properties."""
        ...

    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges."""
        ...

    @property
    @abstractmethod
    def node_count(self) -> int:
        """Total number of nodes."""
        ...

    @property
    @abstractmethod
    def edge_count(self) -> int:
        """Total number of edges."""
        ...

# ── Research Agent Interface ─────────────────────────────────────────────────

@dataclass
class AgentTask:
    """Task specification for a research agent."""
    task_id: str
    task_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentResult:
    """Result from a research agent execution."""
    task_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

class ResearchAgent(BaseProvider):
    """Interface for autonomous research agents."""

    @abstractmethod
    def execute(self, task: AgentTask) -> AgentResult:
        """Execute a research task.

        Args:
            task: Task specification

        Returns:
            AgentResult with output or error
        """
        ...

    @abstractmethod
    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle a specific task type."""
        ...

    @abstractmethod
    def supported_task_types(self) -> List[str]:
        """List of task types this agent supports."""
        ...

# ── Dependency Injection Container ───────────────────────────────────────────

class ServiceContainer:
    """
    Lightweight dependency injection container.

    Registers and resolves service implementations by interface type.
    Does NOT replace existing singletons — it coexists with them.

    Example:
        container = ServiceContainer()
        container.register(OCREngine, PyMuPDFOCREngine())
        engine = container.resolve(OCREngine)
    """

    def __init__(self):
        self._services: Dict[type, Any] = {}
        self._factories: Dict[type, callable] = {}

    def register(self, interface: type, implementation: Any) -> None:
        """Register a service implementation for an interface."""
        self._services[interface] = implementation

    def register_factory(self, interface: type, factory: callable) -> None:
        """Register a factory function that creates the implementation on demand."""
        self._factories[interface] = factory

    def resolve(self, interface: type) -> Optional[Any]:
        """Resolve a service by its interface type.

        Returns None if not registered (graceful degradation).
        """
        # Check direct registration
        if interface in self._services:
            return self._services[interface]

        # Check factory
        if interface in self._factories:
            impl = self._factories[interface]()
            self._services[interface] = impl
            return impl

        return None

    def has(self, interface: type) -> bool:
        """Check if a service is registered."""
        return interface in self._services or interface in self._factories

    def clear(self) -> None:
        """Remove all registered services."""
        self._services.clear()
        self._factories.clear()

# Module-level singleton container
_container: Optional[ServiceContainer] = None

def get_service_container() -> ServiceContainer:
    """Get or create the singleton service container."""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container