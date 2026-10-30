"""Обновление заметки: заголовок и/или содержимое (без переименования файла)."""

from __future__ import annotations

from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import load_note, resolve_note_path


def update_note(
    path: str,
    notes_dir: Path,
    title: str | None = None,
    content: str | None = None,
) -> dict:
    """Обновить заголовок и/или тело существующей заметки.

    Файл не переименовывается и не перемещается: меняется только содержимое.
    ``content`` ПОЛНОСТЬЮ заменяет старое тело.

    Args:
        path: Путь заметки относительно notes_dir (например, 'работа/вторая.md').
        notes_dir: Директория с заметками.
        title: Новый заголовок (заменяет первую строку '# ...'). Опционален.
        content: Новое тело заметки в Markdown. Опционален.

    Returns:
        Словарь ``{"path": ..., "title": ..., "size_chars": ...}``.

    Raises:
        ValueError: Если не передано ни одного изменения, заголовок пуст,
            путь вне notes_dir или файл не Markdown.
        FileNotFoundError: Если заметка не найдена.
    """
    if title is None and content is None:
        raise ValueError("Nothing to update: provide title and/or content")
    if title is not None and not title.strip():
        raise ValueError("title must not be empty")

    candidate = resolve_note_path(path, notes_dir)
    if not candidate.is_file():
        raise FileNotFoundError(f"Note not found: {path!r}")
    if candidate.suffix != ".md":
        raise ValueError(f"Not a Markdown note: {path!r}")

    note = load_note(candidate)
    if note is None:
        raise ValueError(f"Failed to read note: {path!r}")

    new_title = title.strip() if title is not None else note["title"]
    new_body = content if content is not None else note["body"]

    # Убираем дубль заголовка: '# {new_title}' добавляется при записи.
    stripped = new_body.lstrip()
    if stripped.startswith("# "):
        _first, _, rest = stripped.partition("\n")
        new_body = rest.lstrip("\n")

    candidate.write_text(f"# {new_title}\n\n{new_body}\n", encoding="utf-8")

    return {
        "path": candidate.relative_to(notes_dir).as_posix(),
        "title": new_title,
        "size_chars": len(new_body),
    }


UPDATE_NOTE_TOOL: ToolDefinition = ToolDefinition(
    name="update_note",
    description=(
        "Update the title and/or body of an EXISTING note. "
        "Use when the user asks: 'измени заметку', 'обнови заметку', "
        "'замени текст заметки', 'поменяй заголовок заметки', 'update the note'. "
        "Requires the note path — get it first from list_notes, read_notes or search_notes. "
        "The content parameter REPLACES the whole body — do NOT use it to append text "
        "if you don't know the current body. "
        "Does NOT rename the file and does NOT move it between categories — "
        "use move_note for that. Returns path, title, size_chars."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Path to the note relative to data/notes/, e.g. 'работа/вторая.md'. "
                    "Take it from list_notes/read_notes/search_notes results."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "New title (replaces the '# ...' heading). "
                    "Omit if the title should stay the same."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "New FULL body of the note in Markdown (replaces the old body). "
                    "Omit if the body should stay the same."
                ),
            },
        },
        "required": ["path"],
    },
    func=update_note,
    needs_notes_dir=True,
)