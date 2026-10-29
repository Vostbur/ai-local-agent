"""Markdown document extractor."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .base import ExtractedDocument, Segment

logger = logging.getLogger("agent")

HEADER_RE = re.compile(r"^#{1,6}\s+(.+)$")
FENCED_CODE_RE = re.compile(r"^(`{3,}|~{3,}).*$\n(.*?)^\1[ \t]*$", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^\)]+\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^\)]+\)")
INLINE_MARKUP_RE = re.compile(r"[\*_]{1,2}|~~")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


class MarkdownExtractor:
    """Extract structured text segments from Markdown files."""

    def supported_suffixes(self) -> set[str]:
        return {".md", ".markdown"}

    def extract(self, path: Path) -> ExtractedDocument | None:
        try:
            try:
                raw = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                raw = path.read_text(encoding="cp1251")
        except Exception:
            logger.warning("Failed to read %s", path, exc_info=True)
            return None

        lines = raw.splitlines()
        segments: list[Segment] = []
        current_section: str | None = None
        current_body: list[str] = []
        has_header = False

        for line in lines:
            m = HEADER_RE.match(line)
            if m:
                # Flush previous segment
                if current_section is not None or current_body:
                    body = self._clean_body("\n".join(current_body))
                    if body:
                        segments.append(Segment(text=body, section=current_section))
                    current_body.clear()

                current_section = m.group(1).strip()
                has_header = True
            else:
                current_body.append(line)

        # Flush last segment
        if current_section is not None or current_body:
            body = self._clean_body("\n".join(current_body))
            if body:
                segments.append(Segment(text=body, section=current_section))

        return ExtractedDocument(path=path, segments=segments, metadata={})

    def _clean_body(self, body: str) -> str:
        # 1. Remove fenced code blocks
        text = FENCED_CODE_RE.sub("", body)
        # 2. Remove inline code
        text = INLINE_CODE_RE.sub("", text)
        # 3. Remove images (strip entirely, no alt)
        text = IMAGE_RE.sub("", text)
        # 4. Expand links: [text](url) -> text
        text = LINK_RE.sub(r"\1", text)
        # 5. Strip inline markup characters
        text = INLINE_MARKUP_RE.sub("", text)
        # 6. Strip HTML tags
        text = HTML_TAG_RE.sub("", text)
        # 7. Normalize whitespace
        text = MULTI_SPACE_RE.sub(" ", text)
        text = MULTI_NEWLINE_RE.sub("\n\n", text)
        text = text.strip()
        return text
