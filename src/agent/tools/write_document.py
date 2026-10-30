"""Обёртка над save_note для создания документов в data/generated/."""

from __future__ import annotations

from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools.save_note import save_note


def write_document(title: str, content: str, output_dir: Path) -> dict:
    """Создать новый Markdown-документ в указанной директории.

    Args:
        title: Заголовок документа, используется как имя файла и как # заголовок.
        content: Содержимое документа в формате Markdown.
        output_dir: Директория для сохранения документов.

    Returns:
        Словарь с путём, заголовком и размером содержимого.
    """
    stripped = content.lstrip()
    if stripped.startswith("# "):
        first_line, _, rest = stripped.partition("\n")
        # Если первая строка — заголовок (не важно, совпадает с title или нет),
        # save_note добавит '# {title}' сам. Убираем дубль.
        content = rest.lstrip("\n")
    path = save_note(title, content, output_dir)
    return {"path": str(path), "title": title, "size_chars": len(content)}


WRITE_DOCUMENT_TOOL: ToolDefinition = ToolDefinition(
    name="write_document",
    description=(
        "Write a new Markdown document to the generated/ directory. "
        "Never overwrites existing files — adds _1, _2 suffix on conflict. "
        "Use when the user asks to create, generate, or write a new document, "
        "especially after reading a template with read_document. "
        "Returns path, title, size_chars."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Document title, used as filename and as # heading. "
                    "If the user did not specify an explicit title, "
                    "do NOT invent one — ask for clarification."
                ),
            },
            "content": {
                "type": "string",
                "description": "Document body in Markdown.",
            },
        },
        "required": ["title", "content"],
    },
    func=write_document,
)
