"""
exceptions.py — Centralized Exception System  [QUARANTINED]
===========================================================
Status (audit F-09, 2026-08-23): this hierarchy is NOT raised, caught, or
imported anywhere in production. The live error contract is `Ok/Err`
(core/contracts.py, used by literature/) plus signal-based worker errors.
Kept for reference; do NOT add new raise sites here. If a future module
needs typed errors, adopt Ok/Err first; delete this module once the
decision is ratified (Phase 4→6 refactor).

Categories:
    - Configuration errors
    - Provider/API errors
    - Parsing/OCR errors
    - Validation errors
    - Graph/Storage errors
    - RAG/Embedding errors
    - Security errors
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class ROSException(Exception):
    """Base exception for all ROS-specific errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code (e.g., 'CFG_001')
        details: Additional context dictionary
        recoverable: Whether the error can be recovered from automatically
    """

    def __init__(
        self,
        message: str,
        code: str = "ROS_000",
        details: Optional[dict] = None,
        recoverable: bool = False,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        self.recoverable = recoverable
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict:
        """Serialize exception for logging/API responses."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
            "type": self.__class__.__name__,
        }


# ── Configuration Errors ─────────────────────────────────────────────────────

class ConfigurationError(ROSException):
    """Raised when configuration is invalid or missing."""
    def __init__(self, message: str, code: str = "CFG_001", **kwargs) -> None:
        super().__init__(message, code=code, **kwargs)


class MissingAPIKeyError(ConfigurationError):
    """Raised when API key is missing or empty."""
    def __init__(self, provider: str = "unknown") -> None:
        super().__init__(
            f"API key is required for provider '{provider}'",
            code="CFG_002",
            details={"provider": provider},
        )


class InvalidModelError(ConfigurationError):
    """Raised when model name is invalid or unsupported."""
    def __init__(self, model: str, supported: Optional[list] = None) -> None:
        msg = f"Invalid model: '{model}'"
        if supported:
            msg += f". Supported: {', '.join(supported)}"
        super().__init__(msg, code="CFG_003", details={"model": model, "supported": supported})


class InvalidVaultPathError(ConfigurationError):
    """Raised when Obsidian vault path is invalid."""
    def __init__(self, path: str) -> None:
        super().__init__(
            f"Invalid vault path: '{path}'",
            code="CFG_004",
            details={"path": path},
        )


# ── Provider / API Errors ────────────────────────────────────────────────────

class ProviderError(ROSException):
    """Base exception for LLM provider errors."""
    def __init__(self, message: str, provider: str = "unknown", code: str = "PRV_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        merged_details = {"provider": provider, **(details or {})}
        super().__init__(message, code=code, details=merged_details, recoverable=recoverable)


class APIKeyInvalidError(ProviderError):
    """Raised when API key is rejected by the provider."""
    def __init__(self, provider: str = "unknown") -> None:
        super().__init__(
            f"Invalid API key for provider '{provider}'",
            provider=provider,
            code="PRV_002",
        )


class APIRateLimitError(ProviderError):
    """Raised when API rate limit is exceeded."""
    def __init__(self, provider: str = "unknown", retry_after: Optional[int] = None) -> None:
        msg = f"Rate limit exceeded for provider '{provider}'"
        if retry_after:
            msg += f". Retry after {retry_after}s"
        super().__init__(msg, provider=provider, code="PRV_003", details={"retry_after": retry_after}, recoverable=True)


class APITimeoutError(ProviderError):
    """Raised when API request times out."""
    def __init__(self, provider: str = "unknown", timeout: int = 60) -> None:
        super().__init__(
            f"Request timed out after {timeout}s for provider '{provider}'",
            provider=provider,
            code="PRV_004",
            details={"timeout": timeout},
            recoverable=True,
        )


class APIResponseError(ProviderError):
    """Raised when API returns an unexpected response."""
    def __init__(self, provider: str = "unknown", status_code: int = 0, body: str = "") -> None:
        super().__init__(
            f"API error ({status_code}) from '{provider}': {body[:200]}",
            provider=provider,
            code="PRV_005",
            details={"status_code": status_code, "body_preview": body[:500]},
        )


# ── Parsing / OCR Errors ─────────────────────────────────────────────────────

class ParsingError(ROSException):
    """Base exception for document parsing errors."""
    def __init__(self, message: str, file_path: str = "", code: str = "PAR_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        merged_details = {"file_path": file_path, **(details or {})}
        super().__init__(message, code=code, details=merged_details, recoverable=recoverable)


class UnsupportedFileTypeError(ParsingError):
    """Raised when file type is not supported."""
    def __init__(self, file_path: str, extension: str = "") -> None:
        super().__init__(
            f"Unsupported file type: {extension or Path(file_path).suffix}",
            file_path=file_path,
            code="PAR_002",
            details={"extension": extension},
        )


class PDFExtractionError(ParsingError):
    """Raised when PDF text extraction fails."""
    def __init__(self, file_path: str, reason: str = "") -> None:
        super().__init__(
            f"PDF extraction failed: {reason}" if reason else "PDF extraction failed",
            file_path=file_path,
            code="PAR_003",
            details={"reason": reason},
        )


class EmptyContentError(ParsingError):
    """Raised when parsed content is empty."""
    def __init__(self, file_path: str = "") -> None:
        super().__init__(
            "Parsed content is empty",
            file_path=file_path,
            code="PAR_004",
        )


# ── Validation Errors ────────────────────────────────────────────────────────

class ValidationError(ROSException):
    """Base exception for data validation errors."""
    def __init__(self, message: str, field: str = "", code: str = "VAL_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        merged_details = {"field": field, **(details or {})}
        super().__init__(message, code=code, details=merged_details, recoverable=recoverable)


class ThreatDetectedError(ValidationError):
    """Raised when security threat is detected in input."""
    def __init__(self, threat_type: str = "", severity: str = "UNKNOWN") -> None:
        super().__init__(
            f"Security threat detected: {threat_type} (severity: {severity})",
            code="VAL_002",
            details={"threat_type": threat_type, "severity": severity},
        )


# ── Graph / Storage Errors ───────────────────────────────────────────────────

class GraphError(ROSException):
    """Base exception for knowledge graph errors."""
    def __init__(self, message: str, code: str = "GRP_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class GraphIntegrityError(GraphError):
    """Raised when graph integrity check fails (e.g., dangling edge)."""
    def __init__(self, node_id: str = "", edge_id: str = "") -> None:
        super().__init__(
            f"Graph integrity violation: edge '{edge_id}' references missing node '{node_id}'",
            code="GRP_002",
            details={"node_id": node_id, "edge_id": edge_id},
        )


class StorageError(ROSException):
    """Base exception for storage/persistence errors."""
    def __init__(self, message: str, path: str = "", code: str = "STO_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        merged_details = {"path": path, **(details or {})}
        super().__init__(message, code=code, details=merged_details, recoverable=recoverable)


# ── RAG / Embedding Errors ───────────────────────────────────────────────────

class RAGError(ROSException):
    """Base exception for RAG pipeline errors."""
    def __init__(self, message: str, code: str = "RAG_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class RetrievalError(RAGError):
    """Raised when RAG retrieval fails."""
    def __init__(self, layer: str = "", reason: str = "") -> None:
        super().__init__(
            f"Retrieval failed at layer '{layer}': {reason}",
            code="RAG_002",
            details={"layer": layer, "reason": reason},
        )


class EmbeddingError(ROSException):
    """Base exception for embedding pipeline errors."""
    def __init__(self, message: str, model: str = "", code: str = "EMB_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        merged_details = {"model": model, **(details or {})}
        super().__init__(message, code=code, details=merged_details, recoverable=recoverable)


# ── Security Errors ──────────────────────────────────────────────────────────

class SecurityError(ROSException):
    """Base exception for security-related errors."""
    def __init__(self, message: str, code: str = "SEC_001", details: Optional[dict] = None, recoverable: bool = False) -> None:
        super().__init__(message, code=code, details=details, recoverable=recoverable)


class PromptInjectionError(SecurityError):
    """Raised when prompt injection is detected."""
    def __init__(self, pattern: str = "") -> None:
        super().__init__(
            f"Prompt injection detected matching pattern: {pattern}",
            code="SEC_002",
            details={"pattern": pattern},
        )