"""Поиск заметок по содержимому тела документа."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.agent.registry import ToolDefinition
from src.agent.tools._search import find_match_with_kind

logger = logging.getLogger("agent")


def search_notes(
    query: str, notes_dir: Path, max_results: int = 5
) -> list[dict]:
    """Поиск Markdown-заметок по вхождению запроса в тело документа.

    Args:
        query: Строка поиска (ищется в body).
        notes_dir: Директория с Markdown-заметками.
        max_results: Максимальное число результатов.

    Returns:
        Список словарей с полями path, title, snippet, matches.
    """
    if not query.strip() or not notes_dir.exists():
        return []

    md_files = sorted(
        p for p in notes_dir.iterdir() if p.suffix == ".md" and p.is_file()
    )

    results: list[dict] = []

    for path in md_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            logger.warning("Failed to read %s", path)
            continue

        lines = text.splitlines()

        if lines and lines[0].startswith("#"):
            title = lines[0][1:].strip()
            body = "\n".join(lines[1:])
        else:
            title = path.stem
            body = text

        res = find_match_with_kind(body, query)
        if res is None:
            continue

        start, _end, kind = res

        if kind == "exact":
            matches = body.lower().count(query.lower())
        else:  # kind == "stem"
            stem = query[:-2].lower()
            matches = len(re.findall(rf"\b{re.escape(stem)}", body.lower()))

        # snippet: строка с совпадением + одна до и одна после
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

    results.sort(key=lambda r: r["path"])
    return results[:max_results]


SEARCH_NOTES_TOOL: ToolDefinition = ToolDefinition(
    name="search_notes",
    description=(
        "Search INSIDE note bodies (content) for a substring and return snippets. Use this when the user asks: \"в какой заметке я упоминал\", \"найди, что я писал про\", \"поиск по содержимому\", \"which note mentions\", \"search inside notes\", \"what did I write about\". Do NOT use this for finding a note by its title — use read_notes for that. Returns path, title, snippet, matches."
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
)