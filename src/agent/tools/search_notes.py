"""Поиск заметок по содержимому тела документа."""

from __future__ import annotations

import re
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.stem import stem
from src.agent.tools._search import find_match_with_kind, iter_md_files, load_note


def search_notes(
    query: str, notes_dir: Path, max_results: int | None = 5
) -> list[dict]:
    """Поиск Markdown-заметок по вхождению запроса в тело документа.

    Args:
        query: Строка поиска (ищется в body).
        notes_dir: Директория с Markdown-заметками.
        max_results: Максимальное число результатов. ``None`` — дефолт 5;
            ``<= 0`` — вернуть пустой список. Чтение прекращается,
            как только найдено нужное число совпадений.

    Returns:
        Список словарей с полями path, title, snippet, matches.
    """
    if max_results is None:
        max_results = 5
    if max_results <= 0:
        return []

    if not query.strip() or not notes_dir.exists():
        return []

    results: list[dict] = []

    for path in iter_md_files(notes_dir):
        note = load_note(path)
        if note is None:
            continue

        title = note["title"]
        body = note["body"]

        res = find_match_with_kind(body, query)
        if res is None:
            continue

        start, _end, kind = res

        if kind == "exact":
            matches = body.lower().count(query.lower())
        else:  # kind == "stem"
            stemmed = stem(query.lower())
            matches = len(
                re.findall(rf"\b{re.escape(stemmed)}", body.lower())
            )

        line_start = body.rfind("\n", 0, start) + 1
        line_end = body.find("\n", start)
        if line_end == -1:
            line_end = len(body)

        context_lines = []
        has_prev = False
        if line_start > 0:
            prev_line_start = body.rfind("\n", 0, line_start - 1) + 1
            context_lines.append(body[prev_line_start:line_start])
            has_prev = True
        context_lines.append(body[line_start:line_end])

        has_next = False
        next_line_start = line_end + 1
        if next_line_start < len(body):
            next_line_end = body.find("\n", next_line_start)
            if next_line_end == -1:
                next_line_end = len(body)
            context_lines.append(body[next_line_start:next_line_end])
            has_next = next_line_end < len(body)

        snippet = " ".join(context_lines).strip()

        ellipsis_prefix = "…" if has_prev else ""
        trimmed_right = len(snippet) > 300
        if trimmed_right:
            snippet = snippet[:300]
        ellipsis_suffix = "…" if (trimmed_right or has_next) else ""

        results.append(
            {
                "path": str(path),
                "title": title,
                "snippet": ellipsis_prefix + snippet + ellipsis_suffix,
                "matches": matches,
            }
        )

        if len(results) >= max_results:
            break

    return results


SEARCH_NOTES_TOOL: ToolDefinition = ToolDefinition(
    name="search_notes",
    description=(
        "Search the user's PERSONAL NOTES (in data/notes/, created via save_note) "
        "— NOT documents, README, or project files. Use only when the user "
        "explicitly asks about their own notes: \"мои заметки\", \"что я записал\", "
        "\"найди заметку\", \"my notes\", \"what did I write\". "
        "For documents, README, articles, project files — use search_documents. "
        "Returns path, title, snippet, matches."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to find in note body text. Required.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Defaults to 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    func=search_notes,
    needs_notes_dir=True,
)