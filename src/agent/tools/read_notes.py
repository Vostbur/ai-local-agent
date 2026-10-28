"""Чтение заметок из директории Markdown-файлов."""

from __future__ import annotations

from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import find_match, iter_md_files, load_note


def read_notes(
    query: str = "",
    notes_dir: Path | None = None,
    max_results: int = 50,
) -> list[dict]:
    """Прочитать заметки из директории и отфильтровать по запросу.

    Args:
        query: Строка поиска (по title или имени файла).
        notes_dir: Директория с Markdown-заметками.
            Если не указана — используется ``Path("data/notes")``.
        max_results: Максимальное число возвращаемых заметок. По умолчанию 50.

    Returns:
        Список словарей с полями path, title, preview.
    """
    if notes_dir is None:
        notes_dir = Path("data/notes")

    if not notes_dir.exists():
        return []

    results: list[dict] = []
    stripped_query = query.strip()

    for path in iter_md_files(notes_dir):
        note = load_note(path)
        if note is None:
            continue

        title = note["title"]
        body = note["body"]

        if stripped_query:
            if (
                find_match(title, stripped_query) is None
                and find_match(path.name, stripped_query) is None
            ):
                continue

        results.append(
            {
                "path": str(path),
                "title": title,
                "preview": body[:200].replace("\n", " ").strip(),
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
            "max_results": {
                "type": "integer",
                "description": "Maximum number of notes to return. Default 50.",
                "default": 50,
            },
        },
        "required": [],
    },
    func=read_notes,
)