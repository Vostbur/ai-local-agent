"""Text file extractor."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.agent.extractors.base import ExtractedDocument, Segment

logger = logging.getLogger(__name__)


class TxtExtractor:
    supported_suffixes = {".txt"}

    def extract(self, path: Path) -> ExtractedDocument | None:
        try:
            raw = None
            for encoding in ("utf-8-sig", "cp1251"):
                try:
                    raw = path.read_text(encoding=encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if raw is None:
                logger.exception("Failed to read %s with any supported encoding", path)
                return None

            text = re.sub(r"\s+", " ", raw).strip()

            if not text:
                return ExtractedDocument(path=path, segments=[], metadata={})

            return ExtractedDocument(
                path=path,
                segments=[Segment(text=text, section=None)],
                metadata={},
            )
        except Exception:
            logger.exception("Error extracting %s", path)
            return None
