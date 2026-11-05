"""Экстрактор текста из файлов DOCX."""
from __future__ import annotations

import logging
from pathlib import Path

from docx import Document as DocxDocument

from src.agent.extractors.base import ExtractedDocument, Segment, TextExtractor

logger = logging.getLogger("agent")

# Стили, которые считаем заголовками разделов. Обычные стили (например,
# "Normal") в section НЕ попадают: иначе read_document выдавал бы
# простыню из «## Normal», а эмбеддинги и BM25 — мусорный префикс
# «Normal. » у каждого чанка (T42).
_HEADING_PREFIXES = ("Heading", "Заголовок")
_HEADING_EXACT = {"Title", "Subtitle"}


def _section_for(style_name: str | None) -> str | None:
    """Имя стиля параграфа → section: только заголовочные стили, иначе None."""
    if not style_name:
        return None
    if style_name.startswith(_HEADING_PREFIXES) or style_name in _HEADING_EXACT:
        return style_name
    return None


class DocxExtractor(TextExtractor):
    """Извлечение текста из `.docx` через python-docx.

    Ограничения первой версии: извлекаются только абзацы
    (``doc.paragraphs``); таблицы, колонтитулы и сноски пропускаются.
    """

    SUFFIXES = {".docx"}

    def supported_suffixes(self) -> set[str]:
        """Суффиксы по протоколу ``TextExtractor`` (T42)."""
        return set(self.SUFFIXES)

    def extract(self, path: Path) -> ExtractedDocument | None:
        """Разобрать DOCX в сегменты.

        Возвращает ``None``, если файл не открылся (битый DOCX, неверный
        формат): в отличие от первой версии, ошибка логируется
        через ``logger.warning`` (T42).
        """
        try:
            doc = DocxDocument(path)
        except Exception as exc:
            logger.warning("Failed to open DOCX %s: %s", path, exc)
            return None

        segments: list[Segment] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = para.style.name if para.style is not None else None
            segments.append(
                Segment(text=text, section=_section_for(style_name))
            )

        return ExtractedDocument(
            path=path,
            segments=segments,
            metadata={"format": "docx", "paragraphs": len(doc.paragraphs)},
        )