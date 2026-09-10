"""
markdown_utils.py — Markdown Parsing Utilities
================================================
Extract frontmatter, wikilinks, headings, and other Markdown structures.
"""

from __future__ import annotations

import re
from typing import List, Tuple

import yaml


_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def extract_frontmatter(text: str) -> Tuple[dict, str]:
    """Extract YAML frontmatter from Markdown text.

    Args:
        text: Markdown text with optional YAML frontmatter

    Returns:
        Tuple of (frontmatter_dict, body_text)
    """
    match = _FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text

    parsed = yaml.safe_load(match.group(1)) or {}
    if not isinstance(parsed, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return parsed, text[match.end():]


def extract_frontmatter_tags(text: str) -> List[str]:
    """Extract frontmatter tags as a list.

    Args:
        text: Markdown text

    Returns:
        List of tag strings
    """
    frontmatter, _ = extract_frontmatter(text)
    tags = frontmatter.get("tags", frontmatter.get("Tags", []))
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if t]
    return []


def parse_wikilinks(text: str) -> List[Tuple[str, str]]:
    """Extract [[WikiLink|Display]] references from Markdown text.

    Args:
        text: Markdown text

    Returns:
        List of (target, display) tuples
    """
    pattern = r"\[\[([^\]|\n]+?)(?:\|([^\]|\n]*?))?\]\]"
    matches = re.finditer(pattern, text)
    result = []
    for match in matches:
        target = match.group(1).strip()
        display = (match.group(2) or target).strip()
        result.append((target, display))
    return result


def extract_wikilink_targets(text: str) -> List[str]:
    """Central wikilink-target extraction (audit F-16 unification).

    Returns link targets with aliases (``[[T|alias]]``) and heading
    anchors (``[[T#section]]``) stripped. All consumers (worker,
    knowledge graph, obsidian sync, RAG, graph-edge extraction) must use
    this helper instead of private regexes.
    """
    targets: List[str] = []
    for target, _display in parse_wikilinks(text or ""):
        name = target.split("#", 1)[0].strip()
        if name:
            targets.append(name)
    return targets


def count_wikilinks(text: str) -> int:
    """Number of wikilinks in the text (alias/heading variants count once)."""
    return len(parse_wikilinks(text or ""))


def extract_headings(text: str) -> List[Tuple[int, str]]:
    """Extract Markdown headings with their levels.

    Args:
        text: Markdown text

    Returns:
        List of (level, heading_text) tuples
    """
    pattern = r"^(#{1,6})\s+(.+)$"
    headings = []
    for line in text.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            headings.append((level, heading))
    return headings


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """Extract fenced code blocks from Markdown.

    Args:
        text: Markdown text

    Returns:
        List of (language, code) tuples
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.finditer(pattern, text, re.DOTALL)
    return [(match.group(1) or "", match.group(2).strip()) for match in matches]


def strip_markdown_formatting(text: str) -> str:
    """Remove basic Markdown formatting to get plain text.

    Args:
        text: Markdown text

    Returns:
        Plain text
    """
    # Remove bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove links (keep text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
    return text.strip()


def inject_frontmatter(text: str, updates: dict) -> str:
    """Add or update frontmatter fields in Markdown text.

    Args:
        text: Markdown text (may already have frontmatter)
        updates: Dictionary of fields to add/update

    Returns:
        Markdown text with updated frontmatter
    """
    frontmatter, body = extract_frontmatter(text)
    frontmatter.update(updates)

    rendered = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip()
    return f"---\n{rendered}\n---\n\n{body.lstrip()}"
