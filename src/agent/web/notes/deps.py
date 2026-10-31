"""Адаптер между web-слоем и существующими инструментами заметок.

Заметки идентифицируются по `path` (относительный POSIX-путь от notes_dir).
Все операции синхронные, как и сами инструменты.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools.list_notes import list_notes
from agent.tools.read_notes import read_notes
from agent.tools.search_notes import search_notes
from agent.tools.save_note import save_note  # re-export
from agent.tools.update_note import update_note  # re-export
from agent.tools.delete_note import delete_note  # re-export
from agent.tools.move_note import move_note  # re-export
from agent.tools.list_categories import list_categories  # re-export

__all__ = [
    "notes_dir", "trash_dir", "fetch_notes", "find_one", "read_body",
    "all_categories",
    "save_note", "update_note", "delete_note", "move_note",
]


def _pick_path(cfg: Any, name: str, default: str) -> Path:
    """Достаёт Path из config.

    Порядок поиска:
      1. cfg.paths.name  (например, config.paths.notes_dir)
      2. cfg.name        (например, config.notes_dir)
      3. default
    """
    if cfg is None:
        return Path(default)

    # 1. Ищем во вложенном объекте paths (ваш случай)
    paths_obj = getattr(cfg, "paths", None)
    if paths_obj is not None:
        value = getattr(paths_obj, name, None)
        if value is None and isinstance(paths_obj, dict):
            value = paths_obj.get(name)
        if value:
            return Path(value)

    # 2. Fallback на верхний уровень
    value = getattr(cfg, name, None)
    if value is None and isinstance(cfg, dict):
        value = cfg.get(name)

    return Path(value) if value else Path(default)


def notes_dir(cfg: Any) -> Path:
    return _pick_path(cfg, "notes_dir", "data/notes")


def trash_dir(cfg: Any) -> Path:
    return _pick_path(cfg, "trash_dir", "data/trash")


def all_categories(cfg: Any) -> list[dict]:
    """list_categories возвращает [{"name": str, "note_count": int}]."""
    return list_categories(notes_dir(cfg))


def fetch_notes(cfg: Any, category: str | None, query: str | None) -> list[dict]:
    """Единый ответ для UI.

    Форма элемента:
      {path, title, category, preview, modified, size_chars, matches}
    """
    nd = notes_dir(cfg)
    meta = {n["path"]: n for n in list_notes(nd, max_results=1000)}

    if query:
        hits = search_notes(query, nd, max_results=300)
        out: list[dict] = []
        for h in hits:
            if category and h.get("category") != category:
                continue
            m = meta.get(h["path"], {})
            out.append({
                "path": h["path"],
                "title": h["title"],
                "category": h.get("category"),
                "preview": h.get("snippet", ""),
                "modified": m.get("modified"),
                "size_chars": m.get("size_chars"),
                "matches": h.get("matches", 0),
            })
        return out

    rows = read_notes("", nd, max_results=1000)
    out = []
    for r in rows:
        if category and r.get("category") != category:
            continue
        m = meta.get(r["path"], {})
        out.append({
            "path": r["path"],
            "title": r["title"],
            "category": r.get("category"),
            "preview": r.get("preview", ""),
            "modified": m.get("modified"),
            "size_chars": m.get("size_chars"),
            "matches": 0,
        })
    out.sort(key=lambda x: x.get("modified") or "", reverse=True)
    return out


def find_one(cfg: Any, path: str) -> dict | None:
    for n in fetch_notes(cfg, None, None):
        if n["path"] == path:
            return n
    return None


def read_body(cfg: Any, path: str) -> str:
    """Читает ПОЛНОЕ тело заметки с диска (без frontmatter).

    Нужна для формы редактирования: preview из read_notes обрезан
    и не годится для записи обратно через update_note.
    """
    full = notes_dir(cfg) / path
    try:
        text = full.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

    lines = text.split("\n")
    # Frontmatter: первая строка "---", затем закрывающий "---" на своей строке
    if lines and lines[0].rstrip() == "---":
        for i in range(1, len(lines)):
            if lines[i].rstrip() == "---":
                return "\n".join(lines[i + 1:])
    return text