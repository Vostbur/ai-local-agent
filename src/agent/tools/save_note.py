"""Сохранение заметки в Markdown-файл."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.agent.registry import ToolDefinition


def save_note(title: str, content: str, notes_dir: Path) -> Path:
    """Сохранить заметку в Markdown-файл.

    Args:
        title: Заголовок заметки.
        content: Содержимое заметки.
        notes_dir: Директория для сохранения заметок.

    Returns:
        Путь к созданному файлу.

    Raises:
        ValueError: Если заголовок пустой.
    """
    if not title.strip():
        raise ValueError("title must not be empty")

    notes_dir.mkdir(parents=True, exist_ok=True)

    slug = title.lower()
    slug = slug.replace(" ", "_")
    slug = re.sub(r'[<>:"/\\|?*?]', "", slug)
    slug = re.sub(r"[\u0000-\u001f\u007f-\u009f]", "", slug)
    slug = "".join(
        ch
        for ch in slug
        if unicodedata.category(ch).startswith("L")
        or ch in ("_", "-")
        or ch.isdigit()
    )
    slug = slug[:100]
    if not slug:
        slug = "note"

    candidate = notes_dir / f"{slug}.md"
    suffix = 1
    while candidate.exists():
        candidate = notes_dir / f"{slug}_{suffix}.md"
        suffix += 1

    candidate.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")

    return candidate


SAVE_NOTE_TOOL: ToolDefinition = ToolDefinition(
    name="save_note",
    description="Save a note to a Markdown file. Creates a new file; never overwrites existing notes.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the note.",
            },
            "content": {
                "type": "string",
                "description": "The content of the note.",
            },
        },
        "required": ["title", "content"],
    },
    func=save_note,
)
