"""Text extraction registry."""

from __future__ import annotations

import logging
from pathlib import Path

from .base import ExtractedDocument, TextExtractor
from .markdown import MarkdownExtractor
from .txt import TxtExtractor

logger = logging.getLogger(__name__)

EXTRACTORS: dict[str, TextExtractor] = {}


def register(suffixes: set[str], extractor: TextExtractor) -> None:
    for suffix in suffixes:
        normalized = suffix.lower().removeprefix(".")
        normalized = f".{normalized}"
        if normalized in EXTRACTORS:
            raise ValueError(f"Suffix {normalized!r} is already registered")
        EXTRACTORS[normalized] = extractor


def extract_text(path: Path) -> ExtractedDocument | None:
    suffix = path.suffix.lower()
    extractor = EXTRACTORS.get(suffix)
    if extractor is None:
        logger.warning("No extractor found for suffix %r", suffix)
        return None
    try:
        return extractor.extract(path)
    except Exception:
        logger.exception("Error extracting %s", path)
        return None


register(MarkdownExtractor().supported_suffixes(), MarkdownExtractor())
register(TxtExtractor.supported_suffixes, TxtExtractor())
