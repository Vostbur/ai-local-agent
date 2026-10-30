"""Сохранение Markdown-заметок с защитой от перезаписи."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import validate_category

_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def _make_slug(title: str) -> str:
    """Безопасное имя файла из заголовка заметки.

    Учитывает ограничения Windows: убирает запрещённые символы,
    обрезает длину, экранирует зарезервированные имена.
    """
    slug = title.lower()
    slug = slug.replace(" ", "_")
    slug = re.sub(r'[<>:"/|?*]', "", slug)
    slug = re.sub(r"[\u0000-\u001f\u007f-\u009f]", "", slug)
    slug = "".join(
        ch
        for ch in slug
        if unicodedata.category(ch).startswith("L") or ch in ("_", "-") or ch.isdigit()
    )
    slug = slug[:100]
    # Belt-and-braces: обрезать trailing точки/пробелы на случай,
    # если фильтр выше изменится. Сейчас они и так отсекаются.
    slug = slug.rstrip(" .")
    if not slug:
        slug = "note"
    if slug in _WINDOWS_RESERVED:
        slug = f"_{slug}"
    return slug


def save_note(
    title: str,
    content: str,
    notes_dir: Path,
    category: str | None = None,
) -> dict:
    """Сохранить заметку в Markdown-файл.

    Args:
        title: Заголовок заметки.
        content: Содержимое заметки.
        notes_dir: Директория для сохранения заметок.
        category: Опциональная категория (подпапка в notes_dir).

    Returns:
        Словарь ``{"path": относительный путь, "title": заголовок,
        "category": категория или None}``.

    Raises:
        ValueError: Если заголовок пустой или категория невалидна.
    """
    if not title.strip():
        raise ValueError("title must not be empty")

    category_clean = validate_category(category)

    if category_clean:
        target_dir = notes_dir / category_clean
    else:
        target_dir = notes_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    slug = _make_slug(title)

    candidate = target_dir / f"{slug}.md"
    suffix = 1
    while candidate.exists():
        candidate = target_dir / f"{slug}_{suffix}.md"
        suffix += 1

    candidate.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")

    rel_path = candidate.relative_to(notes_dir).as_posix()

    return {
        "path": rel_path,
        "title": title,
        "category": category_clean,
    }


SAVE_NOTE_TOOL: ToolDefinition = ToolDefinition(
    name="save_note",
    description=(
        "Save a note to a Markdown file in data/notes/. Use when the user asks to: "
        "сохранить заметку, записать заметку, создать заметку, занести в заметки, "
        "save a note, write a note, create a note. "
        "Optionally place the note in a category (subfolder). "
        "Creates a new file; never overwrites existing ones."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Note title, used as filename. Example: 'Список покупок'. "
                    "If the user did not specify an explicit title, "
                    "do NOT invent one — ask the user for clarification instead."
                ),
            },
            "content": {
                "type": "string",
                "description": "Note body in Markdown. If the user did not provide content, use an empty string.",
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional category (subfolder) for the note. Example: 'Работа', 'Идеи'. "
                    "If the user did not mention a category, do NOT invent one — leave empty or omit."
                ),
            },
        },
        "required": ["title", "content"],
    },
    func=save_note,
    needs_notes_dir=True,
)