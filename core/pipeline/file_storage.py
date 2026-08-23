"""
pipeline/file_storage.py — Document File Storage Service
==========================================================
Organizes processed documents: raw/, processed/, metadata/, cache/, temporary/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.pipeline.interfaces import DocumentStorage
from core.pipeline.models import Document
from core.utils.file_utils import atomic_write, ensure_dir
from core.utils.json_utils import safe_load_json


class FileStorage(DocumentStorage):
    """File-based document storage implementation.

    Structure:
        documents/
        ├── raw/            Original uploaded files
        ├── processed/      Extracted text files
        ├── metadata/       JSON metadata files
        ├── cache/          Cached intermediate results
        └── temporary/      Temporary processing files
    """

    def __init__(self, base_path: Path | str = "documents"):
        self.base_path = Path(base_path)
        self.raw_dir = self.base_path / "raw"
        self.processed_dir = self.base_path / "processed"
        self.metadata_dir = self.base_path / "metadata"
        self.cache_dir = self.base_path / "cache"
        self.temp_dir = self.base_path / "temporary"

        # Ensure all directories exist
        for d in [self.raw_dir, self.processed_dir, self.metadata_dir, self.cache_dir, self.temp_dir]:
            ensure_dir(d)

    def store_raw(self, document: Document, content: bytes) -> Path:
        """Store the original uploaded file."""
        ext = document.original_path.suffix
        target = self.raw_dir / f"{document.id}{ext}"
        target.write_bytes(content)
        document.raw_path = target
        return target

    def store_processed(self, document: Document, content: str) -> Path:
        """Store the processed text output."""
        target = self.processed_dir / f"{document.id}.txt"
        atomic_write(target, content)
        document.processed_path = target
        return target

    def store_metadata(self, document: Document, metadata: Dict[str, Any]) -> Path:
        """Store document metadata as JSON."""
        target = self.metadata_dir / f"{document.id}.json"
        atomic_write(target, json.dumps(metadata, ensure_ascii=False, indent=2))
        document.metadata_path = target
        return target

    def get_raw_path(self, document: Document) -> Path:
        return document.raw_path or self.raw_dir / f"{document.id}{document.original_path.suffix}"

    def get_processed_path(self, document: Document) -> Path:
        return document.processed_path or self.processed_dir / f"{document.id}.txt"

    def get_metadata_path(self, document: Document) -> Path:
        return document.metadata_path or self.metadata_dir / f"{document.id}.json"

    def load_metadata(self, document: Document) -> Dict[str, Any]:
        """Load document metadata from storage."""
        path = self.get_metadata_path(document)
        return safe_load_json(path, default={})

    def cleanup(self, document: Document) -> None:
        """Remove temporary files, keep raw/processed/metadata."""
        # Clean temporary files
        for f in self.temp_dir.glob(f"{document.id}*"):
            try:
                f.unlink()
            except OSError:
                pass

    def clear_cache(self) -> int:
        """Clear all cached files. Returns count of removed files."""
        count = 0
        for f in self.cache_dir.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
                    count += 1
            except OSError:
                pass
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "raw_count": len(list(self.raw_dir.glob("*"))),
            "processed_count": len(list(self.processed_dir.glob("*"))),
            "metadata_count": len(list(self.metadata_dir.glob("*"))),
            "cache_count": len(list(self.cache_dir.glob("*"))),
            "temp_count": len(list(self.temp_dir.glob("*"))),
            "raw_size_bytes": sum(f.stat().st_size for f in self.raw_dir.glob("*") if f.is_file()),
            "processed_size_bytes": sum(f.stat().st_size for f in self.processed_dir.glob("*") if f.is_file()),
        }