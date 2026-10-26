"""Чтение заметок из директории Markdown-файлов."""

from __future__ import annotations

import logging
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import find_match

logger = logging.getLogger("agent")


def read_notes(query: str = "", notes_dir: Path = ...) -> list[dict]:
    """Прочитать заметки из директории и отфильтровать по запросу.

    Args:
        query: Строка поиска (по title или имени файла).
        notes_dir: Директория с Markdown-заметками.

    Returns:
        Список словарей с полями path, title, preview.
    """
    if not notes_dir.exists():
        return []

    max_results = 50

    md_files = sorted(
        p for p in notes_dir.iterdir() if p.suffix == ".md" and p.is_file()
    )

    results: list[dict] = []

    for path in md_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            logger.warning("Failed to read %s", path)
            continue

        lines = text.splitlines()

        # title: из первой строки если начинается с #
        if lines and lines[0].startswith("#"):
            title = lines[0][1:].strip()
            body = "\n".join(lines[1:])
        else:
            title = path.stem
            body = text

        # filter by query — ищем по title и имени файла
        stripped_query = query.strip()
        if stripped_query:
            if find_match(title, stripped_query) is None and find_match(path.name, stripped_query) is None:
                continue

        preview = body[:200].replace("\n", " ").strip()

        results.append(
            {
                "path": str(path),
                "title": title,
                "preview": preview,
            }
        )

        if len(results) >= max_results:
            break

    return results


READ_NOTES_TOOL: ToolDefinition = ToolDefinition(
    name="read_notes",
    description=(
        "List notes by matching the query against note TITLES and FILENAMES only (not body). Use this when the user asks: \"есть ли заметка под названием\", \"найди заметку с заголовком\", \"покажи заметки про\", \"is there a note titled\", \"find a note by title\", \"list notes\". For searching INSIDE note bodies use search_notes instead. Returns path, title, preview."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional substring to match against titles and filenames (case-insensitive). Empty or missing means list all notes.",
            },
        },
        "required": [],
    },
    func=read_notes,
)
