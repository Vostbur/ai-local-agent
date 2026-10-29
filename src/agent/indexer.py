from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.agent.extractors import EXTRACTORS, extract_text
from src.agent.extractors.base import ExtractedDocument


@dataclass
class IndexResult:
    root: Path
    files_found: int
    files_processed: int
    files_skipped: int
    segments_total: int
    files_with_zero_segments: int

    def summary(self) -> str:
        return (
            f"Документы: {self.root}\n"
            f"Файлов найдено: {self.files_found}\n"
            f"Обработано: {self.files_processed}\n"
            f"Пропущено (ошибка чтения): {self.files_skipped}\n"
            f"Сегментов всего: {self.segments_total}\n"
            f"Файлов с нулём сегментов: {self.files_with_zero_segments}"
        )


def iter_document_files(root: Path) -> list[Path]:
    suffixes = set(EXTRACTORS.keys())
    if not suffixes:
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def index_documents(
    root: Path,
    logger: logging.Logger,
    on_progress: Callable[[int, int, Path, ExtractedDocument | None], None] | None = None,
) -> IndexResult:
    if not root.exists():
        logger.error("documents root does not exist: %s", root)
        return IndexResult(root, 0, 0, 0, 0, 0)

    files = iter_document_files(root)
    total = len(files)

    processed = 0
    skipped = 0
    segments = 0
    zero = 0

    for i, path in enumerate(files, start=1):
        doc = extract_text(path)
        if doc is None:
            skipped += 1
        else:
            processed += 1
            segments += len(doc.segments)
            if len(doc.segments) == 0:
                zero += 1
        if on_progress is not None:
            on_progress(i, total, path, doc)

    return IndexResult(
        root=root,
        files_found=total,
        files_processed=processed,
        files_skipped=skipped,
        segments_total=segments,
        files_with_zero_segments=zero,
    )
