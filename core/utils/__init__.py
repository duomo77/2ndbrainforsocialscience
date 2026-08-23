"""
utils/ — Shared Utility Functions
==================================
Reusable, pure utility functions extracted from across the codebase.
No dependencies on other ROS modules — can be imported anywhere.

Sub-modules:
    - file_utils: File operations (atomic write, backup, path safety)
    - hash_utils: Hashing utilities (content hash, stable ID generation)
    - text_utils: Text processing (truncation, cleaning, normalization)
    - json_utils: JSON operations (safe load, atomic write, migration)
    - markdown_utils: Markdown parsing (frontmatter, wikilinks, headings)
    - path_utils: Path manipulation (sanitization, vault resolution)
    - validation_utils: Input validation helpers
"""