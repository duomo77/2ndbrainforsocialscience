"""
text_utils.py — Text Processing Utilities
==========================================
Truncation, cleaning, normalization, and text analysis helpers.
"""

from __future__ import annotations

import re


def rank_concept_nodes(nodes: list, content: str, limit: int) -> list:
    """Rank concept nodes by relevance to content, capped (audit C-14).

    Deterministic: word-overlap score first (desc), then name (asc) as a
    stable tiebreak. Prevents unbounded context flooding of the analysis
    prompt by the concept registry + vault scan.

    Args:
        nodes: Raw concept names (may contain duplicates)
        content: Analysis content used for relevance scoring
        limit: Maximum number of concepts to return

    Returns:
        Deduplicated, relevance-ranked list of at most ``limit`` names
    """
    content_words = set(re.findall(r"[\w가-힣]{3,}", (content or "").lower()))

    def sort_key(name: str):
        name_words = set(re.findall(r"[\w가-힣]{3,}", name.lower()))
        overlap = len(name_words & content_words)
        return (-overlap, name.casefold())

    unique = sorted({str(n).strip() for n in nodes if str(n).strip()})
    unique.sort(key=sort_key)
    return unique[: max(0, int(limit))]


def truncate_middle(text: str, max_chars: int, separator: str = "\n...\n") -> str:
    """Truncate text by keeping first half and last half, inserting separator.

    Useful for preserving both introduction and conclusion when truncating papers.

    Args:
        text: Input text
        max_chars: Maximum characters to preserve
        separator: String to insert between first and last halves

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text

    half = (max_chars - len(separator)) // 2
    if half <= 0:
        return text[:max_chars]

    return text[:half] + separator + text[-half:]


def truncate_end(text: str, max_chars: int, ellipsis: str = "...") -> str:
    """Truncate text by taking the beginning and appending ellipsis.

    Args:
        text: Input text
        max_chars: Maximum characters
        ellipsis: String to append

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(ellipsis)] + ellipsis


def clean_whitespace(text: str) -> str:
    """Normalize whitespace: collapse multiple spaces/newlines, strip.

    Args:
        text: Input text

    Returns:
        Cleaned text
    """
    # Collapse multiple newlines to at most 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces (not newlines) to single space
    text = re.sub(r"[^\S\n]+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def extract_sentences(text: str, max_sentences: int = 3) -> str:
    """Extract the first N sentences from text.

    Args:
        text: Input text
        max_sentences: Number of sentences to extract

    Returns:
        First N sentences
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences])


def word_count(text: str) -> int:
    """Count words in text (approximate, whitespace-based)."""
    return len(text.split())


def char_count(text: str) -> int:
    """Count characters excluding whitespace."""
    return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))


def estimated_tokens(text: str, chars_per_token: float = 3.5) -> int:
    """Estimate token count from character count.

    Args:
        text: Input text
        chars_per_token: Approximate characters per token

    Returns:
        Estimated token count
    """
    return max(1, int(len(text) / chars_per_token))


def unique_preserve_order(items: list) -> list:
    """Remove duplicates from a list while preserving order.

    Args:
        items: Input list

    Returns:
        Deduplicated list in original order
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def is_empty_content(text: str) -> bool:
    """Check if text is effectively empty (only whitespace)."""
    return not text or not text.strip()