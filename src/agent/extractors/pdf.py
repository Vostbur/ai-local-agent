"""Извлечение текста из PDF через PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf

from src.agent.extractors.base import ExtractedDocument, Segment

logger = logging.getLogger("agent")


class PdfExtractor:
    """Экстрактор PDF: по сегменту на страницу с текстовым слоем."""

    def supported_suffixes(self) -> set[str]:
        return {".pdf"}

    def extract(self, path: Path) -> ExtractedDocument | None:
        """Прочитать PDF: страница → сегмент с section «Страница N».

        Страницы без текстового слоя (сканы, графика) пропускаются.
        Если текста нет во всём PDF — вернуть ExtractedDocument
        с пустым segments и metadata["pages"], а не None.
        None — только если файл не открылся.
        """
        doc = None
        try:
            doc = pymupdf.open(path)
        except (
            pymupdf.FileDataError,
            FileNotFoundError,
            RuntimeError,
        ) as exc:
            logger.warning("Failed to open PDF %s: %s", path, exc)
            return None

        try:
            total = len(doc)
            segments: list[Segment] = []

            for i, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    segments.append(
                        Segment(text=text, section=f"Страница {i}")
                    )

            metadata = {"pages": total, "suffix": ".pdf"}
            return ExtractedDocument(
                path=path, segments=segments, metadata=metadata
            )
        except Exception as exc:
            logger.warning("Failed to extract PDF %s: %s", path, exc)
            return None
        finally:
            if doc is not None:
                doc.close()