"""Удаление заметки: перемещение в data/trash/notes/ (не физическое удаление)."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import ensure_note_file, resolve_note_path


def delete_note(path: str, notes_dir: Path, trash_dir: Path) -> dict:
    """Удалить заметку, переместив её в корзину.

    Структура корзины повторяет структуру заметок:
    ``trash_dir/notes/<категория>/<timestamp>_<имя файла>``.

    Args:
        path: Путь заметки относительно notes_dir.
        notes_dir: Директория с заметками.
        trash_dir: Корневая директория корзины.

    Returns:
        Словарь ``{"path": ..., "moved_to": абсолютный путь в корзине}``.

    Raises:
        ValueError: Если путь вне notes_dir.
        FileNotFoundError: Если заметка не найдена.
    """
    candidate = resolve_note_path(path, notes_dir)
    ensure_note_file(candidate, path)

    rel = candidate.relative_to(notes_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    trash_subdir = trash_dir / "notes" / rel.parent
    trash_subdir.mkdir(parents=True, exist_ok=True)

    target = trash_subdir / f"{timestamp}_{rel.name}"
    suffix = 1
    while target.exists():
        target = trash_subdir / f"{timestamp}_{rel.stem}_{suffix}{rel.suffix}"
        suffix += 1

    shutil.move(str(candidate), str(target))

    return {"path": rel.as_posix(), "moved_to": str(target)}


DELETE_NOTE_TOOL: ToolDefinition = ToolDefinition(
    name="delete_note",
    description=(
        "Delete a note by moving it to the trash folder (data/trash/notes/). "
        "The file is NOT erased permanently and can be restored manually. "
        "Use when the user asks: 'удали заметку', 'сотри заметку', 'убери заметку', "
        "'delete the note'. Requires the note path from list_notes/read_notes/search_notes. "
        "Returns path and moved_to."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "FILE PATH of the note relative to data/notes/, e.g. "
                    "'работа/вторая.md'. This is NOT the note title — do NOT "
                    "pass the title here."
                ),
            },
        },
        "required": ["path"],
    },
    func=delete_note,
    needs_notes_dir=True,
    needs_trash_dir=True,
)