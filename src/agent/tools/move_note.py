"""Перемещение заметки между категориями (подпапками notes_dir)."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import resolve_note_file, validate_category


def move_note(path: str, category: str | None, notes_dir: Path) -> dict:
    """Переместить заметку в категорию (подпапку) или в корень.

    При конфликте имён в целевой категории добавляется суффикс ``_1``, ``_2``...

    Args:
        path: Путь заметки относительно notes_dir.
        category: Целевая категория. ``None`` или ``""`` — корень (без категории).
        notes_dir: Директория с заметками.

    Returns:
        Словарь ``{"path": новый путь, "category": ..., "moved": bool}``.
        ``moved=False``, если заметка уже в целевой категории.

    Raises:
        ValueError: Если путь вне notes_dir или категория невалидна.
        FileNotFoundError: Если заметка не найдена.
    """
    candidate = resolve_note_file(path, notes_dir)

    category_clean = validate_category(category)
    target_dir = notes_dir / category_clean if category_clean else notes_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    old_rel = candidate.relative_to(notes_dir).as_posix()

    if candidate.parent.resolve() == target_dir.resolve():
        return {"path": old_rel, "category": category_clean, "moved": False}

    target = target_dir / candidate.name
    suffix = 1
    while target.exists():
        target = target_dir / f"{candidate.stem}_{suffix}{candidate.suffix}"
        suffix += 1

    shutil.move(str(candidate), str(target))

    return {
        "path": target.relative_to(notes_dir).as_posix(),
        "category": category_clean,
        "moved": True,
    }


MOVE_NOTE_TOOL: ToolDefinition = ToolDefinition(
    name="move_note",
    description=(
        "Move a note to another category (folder in data/notes/) or to the root. "
        "Use when the user asks: 'перемести заметку в категорию', "
        "'перенеси заметку в папку', 'переложи заметку', 'move the note'. "
        "Requires the note path. Pass empty or omit category to move the note "
        "out of any category. Returns path (new), category, moved."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "FILE PATH of the note relative to data/notes/, e.g. "
                    "'работа/вторая.md'. This is NOT the note title — prefer "
                    "the exact path from list_notes/read_notes/search_notes "
                    "results. Fallback: if you don't know the path, pass the "
                    "note title and the tool will try to resolve the note "
                    "by title."
                ),
            },
            "category": {
                "type": "string",
                "description": (
                    "Target category (folder) name. "
                    "Empty or missing means root (no category)."
                ),
            },
        },
        "required": ["path"],
    },
    func=move_note,
    needs_notes_dir=True,
)