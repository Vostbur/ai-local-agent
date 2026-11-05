"""Экстрактор текста из HTML-файлов."""
from __future__ import annotations

import logging
from pathlib import Path

from bs4 import BeautifulSoup

from src.agent.extractors.base import ExtractedDocument, Segment, TextExtractor

logger = logging.getLogger("agent")

# Заголовки, задающие section; остальной текст идёт под текущий заголовок.
_HEADING_TAGS = ("h1", "h2", "h3")
_BLOCK_TAGS = ["h1", "h2", "h3", "p", "li"]


class HtmlExtractor(TextExtractor):
    """Извлечение текста из `.html` / `.htm` через BeautifulSoup.

    Секции: последний встреченный заголовок h1–h3 (его текст); текст до
    первого заголовка идёт с ``section=None``. Это устраняет шум
    ``section="body"`` в эмбеддингах/BM25 и «## body» в `read_document`
    (T43, аналог T42 для DOCX).

    Ограничения первой версии: `<script>`/`<style>` удаляются; таблицы
    и заголовки h4–h6 не извлекаются; вложенные `<p>`/`<li>` дают
    отдельные блоки (возможны повторы текста).
    """

    SUFFIXES = {".html", ".htm"}

    def supported_suffixes(self) -> set[str]:
        """Суффиксы по протоколу ``TextExtractor`` (T43)."""
        return set(self.SUFFIXES)

    def extract(self, path: Path) -> ExtractedDocument | None:
        """Разобрать HTML в сегменты; ``None`` + warning при ошибке."""
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read HTML %s: %s", path, exc)
            return None

        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:
            logger.warning("Failed to parse HTML %s: %s", path, exc)
            return None

        for tag in soup(["script", "style"]):
            tag.extract()

        title = ""
        if soup.title is not None and soup.title.string:
            title = soup.title.string.strip()

        segments: list[Segment] = []
        current_section: str | None = None
        for tag in soup.find_all(_BLOCK_TAGS):
            block_text = tag.get_text(separator=" ", strip=True)
            if not block_text:
                continue
            if tag.name in _HEADING_TAGS:
                current_section = block_text
            segments.append(Segment(text=block_text, section=current_section))

        return ExtractedDocument(
            path=path,
            segments=segments,
            metadata={"format": "html", "title": title},
        )