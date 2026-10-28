"""Общие хелперы поиска и чтения заметок."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("agent")


def find_match_with_kind(
    text: str,
    query: str,
    *,
    min_stem_len: int = 5,
) -> Optional[Tuple[int, int, str]]:
    if not text or not query.strip():
        return None

    text_l = text.lower()
    query_l = query.lower()

    if query_l in text_l:
        start = text_l.index(query_l)
        return (start, start + len(query_l), "exact")

    if len(query_l) >= min_stem_len:
        stem = query_l[:-2]
        if len(stem) >= min_stem_len - 1 and stem in text_l:
            start = text_l.index(stem)
            return (start, start + len(stem), "stem")

    return None


def find_match(
    text: str,
    query: str,
    *,
    min_stem_len: int = 5,
) -> Optional[Tuple[int, int]]:
    res = find_match_with_kind(text, query, min_stem_len=min_stem_len)
    return res[:2] if res is not None else None


def iter_md_files(notes_dir: Path) -> list[Path]:
    """Отсортированный список *.md файлов в notes_dir (верхний уровень)."""
    return sorted(
        p for p in notes_dir.iterdir() if p.suffix == ".md" and p.is_file()
    )


def load_note(path: Path) -> Optional[dict]:
    """Прочитать заметку.

    Возвращает ``{"title": ..., "body": ...}`` или ``None`` при ошибке чтения.
    Title берётся из первой строки, если она начинается с ``#``;
    иначе используется имя файла без расширения.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Failed to read %s", path)
        return None

    lines = text.splitlines()

    if lines and lines[0].startswith("#"):
        title = lines[0][1:].strip()
        body = "\n".join(lines[1:])
    else:
        title = path.stem
        body = text

    return {"title": title, "body": body}