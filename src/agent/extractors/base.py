"""Base types for text extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Segment:
    """A contiguous piece of text extracted from a document.

    Attributes:
        text: The extracted text content.
        section: Optional section header or label (e.g. chapter title).
    """

    text: str
    section: str | None = None


@dataclass
class ExtractedDocument:
    """Result of extracting text from a file.

    Attributes:
        path: The original file path.
        segments: Ordered list of text segments.
        metadata: Arbitrary key-value metadata collected during extraction.
    """

    path: Path
    segments: list[Segment]
    metadata: dict


class TextExtractor(Protocol):
    """Protocol for objects that can extract text from files.

    Implementors declare which file suffixes they support and
    provide an ``extract`` method that returns an ExtractedDocument
    or ``None`` when the file is not supported.
    """

    def supported_suffixes(self) -> set[str]:
        """Return the set of file suffixes this extractor handles."""
        ...

    def extract(self, path: Path) -> ExtractedDocument | None:
        """Extract text from *path*.

        Returns an :class:`ExtractedDocument` on success, or ``None``
        if the file is not supported.
        """
        ...
