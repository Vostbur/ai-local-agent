"""Чтение документа по пути (Markdown, TXT, PDF)."""

from __future__ import annotations

import logging
from pathlib import Path

from src.agent.config import _PROJECT_ROOT
from src.agent.extractors import EXTRACTORS, extract_text
from src.agent.registry import ToolDefinition

logger = logging.getLogger("agent")


def read_document(path: str, max_chars: int = 4000) -> dict:
    """Прочитать документ и вернуть текст, обрезанный до max_chars.

    Args:
        path: Путь к документу. Абсолютный или относительно корня проекта.
        max_chars: Максимум символов в ответе. По умолчанию 4000.

    Returns:
        Словарь с ключами: path, text, truncated, total_chars, suffix.

    Raises:
        ValueError: Если путь вне проекта, файл не существует
            или его не удалось прочитать.
    """
    raw = Path(path)
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (_PROJECT_ROOT / raw).resolve()

    project_resolved = _PROJECT_ROOT.resolve()
    try:
        resolved.relative_to(project_resolved)
    except ValueError:
        raise ValueError(f"path must be inside project: {resolved}")

    if not resolved.is_file():
        raise ValueError(f"cannot read {resolved}: file does not exist")

    suffix = resolved.suffix.lower()
    if suffix not in EXTRACTORS:
        raise ValueError(f"no extractor for suffix {suffix!r}: {resolved}")

    doc = extract_text(resolved)
    if doc is None:
        raise ValueError(f"cannot read {resolved}: extraction failed")

    text = "\n\n".join(seg.text for seg in doc.segments)
    total = len(text)
    truncated = total > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "path": str(resolved),
        "text": text,
        "truncated": truncated,
        "total_chars": total,
        "suffix": resolved.suffix.lower(),
    }


READ_DOCUMENT_TOOL: ToolDefinition = ToolDefinition(
    name="read_document",
    description=(
        "Read a document (Markdown, TXT, PDF) and return its text content, "
        "truncated to max_chars. Use when the user asks to read, open, or "
        "use a document as a template or sample. For searching inside "
        "documents (finding facts) use search_documents instead. "
        "Returns path, text, truncated flag, total_chars, suffix."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Path to the document. Absolute or relative to project "
                    "root. Supported: .md, .txt, .pdf."
                ),
            },
            "max_chars": {
                "type": "integer",
                "description": (
                    "Maximum number of characters to return. "
                    "Default 4000 (~1300 tokens)."
                ),
                "default": 4000,
            },
        },
        "required": ["path"],
    },
    func=read_document,
)