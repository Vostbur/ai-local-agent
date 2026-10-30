"""Список категорий заметок (подпапок notes_dir) с числом заметок."""

from __future__ import annotations

from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import iter_md_files


def list_categories(notes_dir: Path) -> list[dict]:
    """Список категорий заметок.

    Категория — подпапка ``notes_dir`` верхнего уровня. Отдельной строкой
    возвращается число заметок без категории (в корне ``notes_dir``);
    имя такой «категории» — пустая строка.

    Returns:
        Список словарей ``{"name": ..., "note_count": ...}``.
    """
    if not notes_dir.exists():
        return []

    results: list[dict] = []

    root_count = sum(
        1 for p in notes_dir.iterdir() if p.suffix == ".md" and p.is_file()
    )
    results.append({"name": "", "note_count": root_count})

    for subdir in sorted(p for p in notes_dir.iterdir() if p.is_dir()):
        results.append(
            {"name": subdir.name, "note_count": len(iter_md_files(subdir))}
        )

    return results


LIST_CATEGORIES_TOOL: ToolDefinition = ToolDefinition(
    name="list_categories",
    description=(
        "List note categories (folders inside data/notes/) with the number of "
        "notes in each. Use when the user asks: 'какие у меня категории заметок', "
        "'покажи категории', 'список категорий', 'что за папки с заметками', "
        "'list note categories'. Returns name (empty string means notes without "
        "a category) and note_count."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
    func=list_categories,
    needs_notes_dir=True,
)