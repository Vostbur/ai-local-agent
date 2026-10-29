"""PDF text extractor using PyMuPDF."""

from __future__ import annotations

import logging
import pathlib

import fitz

from src.agent.extractors.base import ExtractedDocument, Segment

FileDataError = getattr(fitz, "FileDataError", RuntimeError)

logger = logging.getLogger("agent")


class PdfExtractor:
    """Extracts text from PDF files using PyMuPDF."""

    def supported_suffixes(self) -> set[str]:
        return {".pdf"}

    def extract(self, path: pathlib.Path) -> ExtractedDocument | None:
        try:
            doc = fitz.open(path)
        except (FileDataError, FileNotFoundError, RuntimeError) as exc:
            logger.warning("Failed to open PDF %s: %s", path, exc)
            return None

        try:
            total = len(doc)
            segments: list[Segment] = []

            for i, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    segments.append(Segment(text=text, section=f"Страница {i}"))

            metadata = {"pages": total, "suffix": ".pdf"}

            return ExtractedDocument(path=path, segments=segments, metadata=metadata)
        finally:
            doc.close()
