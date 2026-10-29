"""Text chunking for extracted documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agent.extractors.base import ExtractedDocument


@dataclass
class Chunk:
    """A piece of text extracted from a document.

    Attributes:
        text: The chunk text content.
        path: Original file path.
        section: Optional section header.
        chunk_index: Global index within the document.
    """

    text: str
    path: Path
    section: str | None
    chunk_index: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split *text* into overlapping chunks.

    Chunks are boundary-aware: the end of each chunk is pulled back
    to the nearest sentence/paragraph separator when possible.
    """

    if len(text) <= chunk_size:
        return [text]

    result: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            # Try to find a good break point within the last 200 chars
            search_start = max(start + chunk_size - 200, start)
            separators = [". ", "! ", "? ", "\n\n", "\n", " "]

            for sep in separators:
                pos = text.rfind(sep, search_start, end)
                if pos != -1:
                    end = pos + len(sep)
                    break

        piece = text[start:end].strip()
        if piece:
            result.append(piece)

        if end >= len(text):
            break

        start = end - overlap

    return result


def chunk_document(
    doc: ExtractedDocument, chunk_size: int, overlap: int
) -> list[Chunk]:
    """Split *doc* into overlapping :class:`Chunk` instances.

    The chunk index is global across all segments of the document.
    """

    chunks: list[Chunk] = []
    index = 0

    for segment in doc.segments:
        pieces = split_text(segment.text, chunk_size, overlap)
        for piece in pieces:
            chunks.append(
                Chunk(
                    text=piece,
                    path=doc.path,
                    section=segment.section,
                    chunk_index=index,
                )
            )
            index += 1

    return chunks
