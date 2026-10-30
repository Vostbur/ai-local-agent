"""Список заметок: все или по категории."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import iter_md_files, load_note, validate_category


def list_notes(
    notes_dir: Path,
    category: str | None = None,
    max_results: int | None = 50,
) -> list[dict]:
    """Список заметок, опционально из одной категории.

    Args:
        notes_dir: Директория с заметками.
        category: Категория (подпапка). ``None`` или ``""`` — все заметки.
        max_results: Максимум результатов. ``None`` — дефолт 50; ``<= 0`` — пусто.

    Returns:
        Список словарей: path (относительный от notes_dir), title,
        category (None для корня), modified (ISO), size_chars.
    """
    if max_results is None:
        max_results = 50
    if max_results <= 0:
        return []

    category_clean = validate_category(category)
    base = notes_dir / category_clean if category_clean else notes_dir

    if not base.exists():
        return []

    results: list[dict] = []
    for path in iter_md_files(base):
        note = load_note(path)
        if note is None:
            continue

        rel = path.relative_to(notes_dir).as_posix()
        parent_rel = path.parent.relative_to(notes_dir).as_posix()
        cat = None if parent_rel == "." else parent_rel

        results.append(
            {
                "path": rel,
                "title": note["title"],
                "category": cat,
                "modified": datetime.fromtimestamp(
                    path.stat().st_mtime
                ).isoformat(timespec="seconds"),
                "size_chars": len(note["body"]),
            }
        )
        if len(results) >= max_results:
            break

    return results


LIST_NOTES_TOOL: ToolDefinition = ToolDefinition(
    name="list_notes",
    description=(
        "List notes, optionally only from one category (folder in data/notes/). "
        "Use when the user asks: 'покажи все заметки', 'список заметок', "
        "'заметки в категории Работа', 'заметки из папки', 'list my notes'. "
        "Does NOT search inside note text — for content search use search_notes, "
        "for title search use read_notes. "
        "Returns path, title, category, modified, size_chars."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": (
                    "Optional category (folder) name to list notes from. "
                    "Empty or missing means all notes."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of notes to return. Default 50.",
                "default": 50,
            },
        },
        "required": [],
    },
    func=list_notes,
    needs_notes_dir=True,
)