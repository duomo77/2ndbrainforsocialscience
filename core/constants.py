"""
constants.py — Centralized Constants
=====================================
All magic values, default settings, and named constants used across the
Research Operating System are defined here. No more scattered magic numbers.

Categories:
    - File types and extensions
    - Sizes and limits
    - Model names and presets
    - Directory names
    - Embedding dimensions
    - OCR settings
    - Timeouts and thresholds
"""

from typing import Dict, Final, List, Set, Tuple

# ── File Types and Extensions ────────────────────────────────────────────────

SUPPORTED_PDF_EXTENSIONS: Final[Set[str]] = {".pdf"}
SUPPORTED_TEXT_EXTENSIONS: Final[Set[str]] = {".txt", ".md", ".rst", ".tex"}
SUPPORTED_TRANSCRIPT_EXTENSIONS: Final[Set[str]] = {".srt", ".vtt"}
SUPPORTED_DATASET_EXTENSIONS: Final[Set[str]] = {".csv", ".tsv", ".xlsx", ".xls"}
SUPPORTED_AUDIO_EXTENSIONS: Final[Set[str]] = {".mp3", ".wav", ".m4a", ".flac"}
SUPPORTED_CODE_EXTENSIONS: Final[Set[str]] = {".py", ".jl", ".do", ".r", ".stan"}

ALL_SUPPORTED_EXTENSIONS: Final[Set[str]] = (
    SUPPORTED_PDF_EXTENSIONS
    | SUPPORTED_TEXT_EXTENSIONS
    | SUPPORTED_TRANSCRIPT_EXTENSIONS
    | SUPPORTED_DATASET_EXTENSIONS
    | SUPPORTED_AUDIO_EXTENSIONS
)

# ── Size Limits ──────────────────────────────────────────────────────────────

DEFAULT_MAX_CONTENT_CHARS: Final[int] = 65_000
MAX_CONTENT_CHARS_PAPER: Final[int] = 65_000
MAX_CONTENT_CHARS_TRANSCRIPT: Final[int] = 60_000
MAX_CONTENT_CHARS_DATASET: Final[int] = 50_000
MAX_CONTENT_CHARS_EQUATION: Final[int] = 20_000
MAX_CONTENT_CHARS_NOTES: Final[int] = 50_000

MAX_RAG_FILE_BYTES: Final[int] = 512 * 1024  # 512 KB
MAX_RAG_CONTENT_CHARS: Final[int] = 16_000
MAX_RAG_SCAN_MULTIPLIER: Final[int] = 3

MAX_WIKILINKS_PER_NOTE: Final[int] = 150
MAX_TITLE_LENGTH: Final[int] = 500
MAX_CONTENT_LENGTH_TOTAL: Final[int] = 500_000
# B-04: graph node names derived from LLM output are length-capped
MAX_NODE_NAME_LENGTH: Final[int] = 150
# B-14: input files above this size are rejected before parsing (DoS gate)
MAX_INPUT_FILE_BYTES: Final[int] = 50 * 1024 * 1024  # 50 MB
# C-14: cap on existing concept nodes injected into analysis prompts
MAX_EXISTING_NODES_IN_PROMPT: Final[int] = 150

# ── Graph Limits ─────────────────────────────────────────────────────────────

MAX_NODES_PER_VAULT: Final[int] = 50_000
MAX_EDGES_PER_NODE: Final[int] = 500
MAX_GRAPH_DEPTH: Final[int] = 20
CHECKPOINT_INTERVAL: Final[int] = 50
MAX_SNAPSHOTS: Final[int] = 20

# ── Cache Settings ───────────────────────────────────────────────────────────

DEFAULT_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes
DEFAULT_CACHE_SIZE_MB: Final[int] = 50
MAX_CACHE_ENTRIES: Final[int] = 10_000
VAULT_SCAN_CACHE_TTL: Final[int] = 5

# ── RAG Settings ─────────────────────────────────────────────────────────────

RAG_LAYERS: Final[Tuple[str, ...]] = ("L1_GLOBAL", "L2_TOPIC", "L3_RELATED", "L4_ATOMIC")
RAG_DEFAULT_TOP_K: Final[int] = 10
RAG_MAX_RETRIEVAL_CANDIDATES: Final[int] = 50

# ── Embedding Settings ───────────────────────────────────────────────────────

DEFAULT_EMBEDDING_DIMENSION: Final[int] = 384  # all-MiniLM-L6-v2
DEFAULT_CHUNK_SIZE: Final[int] = 512
DEFAULT_CHUNK_OVERLAP: Final[int] = 50
EMBEDDING_COST_PER_1K: Final[float] = 0.0001  # USD estimate

# ── OCR Settings ─────────────────────────────────────────────────────────────

OCR_DPI: Final[int] = 300
OCR_LANGUAGE: Final[str] = "eng"
MAX_PDF_PAGES: Final[int] = 500

# ── LLM Settings ─────────────────────────────────────────────────────────────

DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 4096
MAX_RETRY_ATTEMPTS: Final[int] = 3
DEFAULT_TIMEOUT_SECONDS: Final[int] = 60
CHARS_PER_TOKEN_ESTIMATE: Final[float] = 3.5

# ── Trust & Memory Settings ──────────────────────────────────────────────────

DECAY_HALF_LIFE_DAYS: Final[int] = 90
MIN_TRUST_SCORE: Final[float] = 0.05
RETRIEVAL_BOOST: Final[float] = 0.05

# ── Directory Names ──────────────────────────────────────────────────────────

CONFIG_DIR_NAME: Final[str] = ".ros_config"
MEMORY_DIR_NAME: Final[str] = "memory"
LOGS_DIR_NAME: Final[str] = "logs"
CACHE_DIR_NAME: Final[str] = "cache"
PROVIDERS_CONFIG_FILE: Final[str] = "providers.json"

# ── Model Presets ────────────────────────────────────────────────────────────

MODEL_PRESETS: Final[Dict[str, List[str]]] = {
    "openai": ["gpt-4o", "gpt-4.5", "gpt-3.5-turbo"],
    "azure": ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"],
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "qwen": ["qwen-max", "qwen-plus", "qwen-turbo"],
    "baidu_ernie": ["ernie-bot-4", "ernie-bot", "ernie-bot-turbo"],
    "groq": ["llama-3.3-70b", "mixtral-8x7b", "gemma2-9b-it"],
    "zhipu": ["glm-4", "glm-4-flash"],
    "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    "minimax": ["abab6.5s-chat", "abab6.5-chat"],
    "siliconflow": ["deepseek-v3", "qwen2.5-72b", "glm-4-9b"],
}

# ── Pricing Tiers (USD per 1M tokens, approximate) ───────────────────────────

MODEL_PRICING: Final[Dict[str, Tuple[float, float]]] = {
    "gpt-4o": (15.00, 60.00),
    "deepseek-chat": (0.14, 0.28),
    "qwen-max": (2.80, 11.20),
    "ernie-bot-4": (1.70, 6.80),
}

DEFAULT_PROVIDER: Final[str] = "openai"
DEFAULT_MODEL: Final[str] = "gpt-5.2"

# ── Note Evolution Stages ────────────────────────────────────────────────────

NOTE_STAGES: Final[Tuple[str, ...]] = (
    "FLEETING", "LITERATURE", "PERMANENT", "SYNTHESIS", "HYPOTHESIS", "PROGRAM"
)

# ── Security Thresholds ──────────────────────────────────────────────────────

BLOCK_THRESHOLD: Final[float] = 0.3  # Minimum score to block input
AUDIT_LOG_MAX_ENTRIES: Final[int] = 10_000

# ── Provider Configuration ───────────────────────────────────────────────────

REQUIRED_CONFIG_FIELDS: Final[Dict[str, List[str]]] = {
    "qwen": ["api_key"],
    "deepseek": ["api_key"],
    "baidu_ernie": ["api_key", "secret_key"],
    "openai": ["api_key"],
    "azure": ["api_key", "endpoint"],
}