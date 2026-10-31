"""Экстрактор текста из HTML-файлов."""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from agent.extractors.base import ExtractedDocument, Segment, TextExtractor

class HtmlExtractor(TextExtractor):
    SUFFIXES = {".html", ".htm"}

    def extract(self, path: Path) -> ExtractedDocument | None:
        try:
            text = path.read_text(encoding="utf-8")
            soup = BeautifulSoup(text, "html.parser")
            
            # Удаляем скрипты и стили
            for script in soup(["script", "style"]):
                script.extract()
                
            # Берем заголовок
            title = soup.title.string.strip() if soup.title else ""

            # Извлекаем текст по блокам
            segments = []
            for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                block_text = tag.get_text(separator=" ", strip=True)
                if block_text:
                    section = tag.name if tag.name.startswith("h") else "body"
                    segments.append(Segment(text=block_text, section=section))

            return ExtractedDocument(
                path=path,
                segments=segments,
                metadata={"format": "html", "title": title},
            )
        except Exception:
            return None