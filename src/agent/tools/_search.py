"""Хелперы для работы с Markdown-заметками."""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

from src.agent.stem import stem

logger = logging.getLogger(__name__)

_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def iter_md_files(notes_dir: Path, recursive: bool = True) -> list[Path]:
    """Отсортированный список *.md файлов в notes_dir.

    Args:
        notes_dir: Корневая директория заметок.
        recursive: Если True — обходит подпапки (категории).
            По умолчанию True, начиная с этапа B (категории).
    """
    if not notes_dir.exists():
        return []

    if recursive:
        return sorted(
            p
            for p in notes_dir.rglob("*.md")
            if p.is_file() and "trash" not in p.parts
        )

    return sorted(
        p for p in notes_dir.iterdir() if p.suffix == ".md" and p.is_file()
    )


def load_note(path: Path) -> Optional[dict]:
    """Прочитать заметку.

    Возвращает ``{"title": ..., "body": ...}`` или ``None`` при ошибке чтения.
    Title берётся из первой строки, если она начинается с ``#``;
    иначе используется имя файла без расширения.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Failed to read %s", path)
        return None

    lines = text.splitlines()

    if lines and lines[0].startswith("#"):
        title = lines[0][1:].strip()
        body = "\n".join(lines[1:])
    else:
        title = path.stem
        body = text

    return {"title": title, "body": body}


def relative_path(path: Path, root: Path) -> str:
    """Относительный путь от root через POSIX-слэши.

    Используется для передачи путёй между инструментами агента.
    """
    return path.relative_to(root).as_posix()


def is_safe_path(path: Path, root: Path) -> bool:
    """Проверка, что path находится внутри root (защита от path traversal).

    Работает через resolve() — корректно обрабатывает ``..`` и символические ссылки.
    """
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return root_resolved in resolved.parents or resolved == root_resolved
    except (OSError, ValueError):
        return False


def _make_slug_safe_name(name: str) -> str:
    """Общая логика превращения строки в безопасное имя (для категории).

    Совместима с ``save_note._make_slug`` по ограничениям Windows.
    """
    slug = name.strip().lower()
    slug = slug.replace(" ", "_")
    slug = re.sub(r'[<>:"/|?*]', "", slug)
    slug = re.sub(r"[\u0000-\u001f\u007f-\u009f]", "", slug)
    slug = "".join(
        ch
        for ch in slug
        if unicodedata.category(ch).startswith("L") or ch in ("_", "-") or ch.isdigit()
    )
    slug = slug[:100]
    slug = slug.rstrip(" .")
    if not slug:
        return ""
    if slug in _WINDOWS_RESERVED:
        return f"_{slug}"
    return slug


def validate_category(category: str | None) -> str | None:
    """Валидация имени категории.

    Args:
        category: Имя категории, переданное пользователем/моделью.

    Returns:
        ``None``, если категория не задана (пустая строка или None).

    Raises:
        ValueError: Если категория содержит запрещённые символы,
            совпадает с зарезервированными именами Windows или пустая после фильтра.
    """
    if category is None or not category.strip():
        return None

    if ".." in category or "/" in category or "\\" in category:
        raise ValueError(f"Invalid category name: {category!r}")

    safe = _make_slug_safe_name(category)
    if not safe:
        raise ValueError(f"Invalid category name: {category!r}")
    if safe != category.strip().lower().replace(" ", "_"):
        # Имя содержит запрещённые символы, которые были удалены
        raise ValueError(f"Invalid category name: {category!r}")
    return safe


def find_match(text: str, query: str) -> Optional[tuple[int, int]]:
    """Поиск подстроки query в text (без учёта регистра).

    Возвращает ``(start, end)`` или ``None``.
    """
    return find_match_with_kind(text, query)[:2] if find_match_with_kind(text, query) else None


def find_match_with_kind(
    text: str, query: str
) -> Optional[tuple[int, int, str]]:
    """Поиск подстроки query в text.

    Сначала ищет точное совпадение (без учёта регистра).
    Если не найдено — ищет по стеммингу (граница слова, 5-символьный префикс).

    Returns:
        ``(start, end, kind)`` где ``kind`` — ``"exact"`` или ``"stem"``,
        или ``None``.
    """
    if not query:
        return None

    text_lower = text.lower()
    query_lower = query.lower()

    idx = text_lower.find(query_lower)
    if idx != -1:
        return idx, idx + len(query_lower), "exact"

    stemmed = stem(query_lower)
    if not stemmed:
        return None

    m = re.search(rf"\b{re.escape(stemmed)}", text_lower)
    if m:
        return m.start(), m.end(), "stem"

    return None

def resolve_note_path(path: str, notes_dir: Path) -> Path:
    """Резолвит путь заметки и проверяет, что он внутри ``notes_dir``.

    Принимает относительный путь (от ``notes_dir``) или абсолютный.

    Raises:
        ValueError: Если путь выходит за пределы ``notes_dir``.
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = notes_dir / candidate
    if not is_safe_path(candidate, notes_dir):
        raise ValueError(f"Path is outside the notes directory: {path!r}")
    return candidate

def ensure_note_file(candidate: Path, path_repr: str) -> None:
    """Проверить, что заметка существует; иначе поднять ошибку с подсказкой.

    Сообщение об ошибке явно говорит модели, что ``path`` — это путь к файлу,
    а не заголовок, и что путь нужно сначала получить через ``list_notes`` /
    ``read_notes``. Текст ошибки попадает в ``tool_result`` со статусом
    ``ERROR``, и оркестратор передаёт его модели — это позволяет модели
    восстановиться на следующем шаге вместо завершения задачи.

    Raises:
        FileNotFoundError: Если файл не существует.
    """
    if not candidate.is_file():
        raise FileNotFoundError(
            f"Note not found: {path_repr!r}. The 'path' argument must be a "
            f"file path relative to data/notes/ (e.g. 'тесты/тест_b1.md'), "
            f"NOT the note title. If you only know the title, call list_notes "
            f"or read_notes first to get the path, then retry."
        )

def find_notes_by_title(title: str, notes_dir: Path) -> list[Path]:
    """Заметки, чей заголовок (первая строка ``# ...``) совпадает с ``title``.

    Сравнение без учёта регистра. Ищет рекурсивно по всем категориям.
    """
    target = title.strip().lower()
    if not target:
        return []

    matches: list[Path] = []
    for path in iter_md_files(notes_dir):
        note = load_note(path)
        if note is not None and note["title"].strip().lower() == target:
            matches.append(path)
    return matches

def resolve_note_file(path_repr: str, notes_dir: Path) -> Path:
    """Резолвит заметку по пути с фолбэком на поиск по заголовку.

    Защита от устойчивого поведения 7B (три прогона 2026-10-30):
    модель передаёт заголовок заметки вместо пути и не восстанавливается
    после ошибки через list_notes.

    Порядок:
    1. Файл существует по пути — вернуть его.
    2. Иначе поиск по заголовку (вся строка), затем по базовому имени
       последней компоненты пути (без ``.md``). Ровно одно совпадение —
       вернуть его.
    3. Несколько совпадений — ``FileNotFoundError`` со списком
       кандидатов: модель должна передать точный путь одного из них.
    4. Нет совпадений — направляющая ``FileNotFoundError``.

    Raises:
        ValueError: Если путь выходит за пределы ``notes_dir``.
        FileNotFoundError: Если заметка не найдена или неоднозначна.
    """
    candidate = resolve_note_path(path_repr, notes_dir)
    if candidate.is_file():
        return candidate

    queries = [path_repr]
    base = Path(path_repr).name
    if base.endswith(".md"):
        base = base[:-3]
    if base and base != path_repr:
        queries.append(base)

    for query in queries:
        matches = find_notes_by_title(query, notes_dir)
        if len(matches) == 1:
            logger.info(
                "resolved note by title: %r -> %s",
                path_repr,
                matches[0].relative_to(notes_dir).as_posix(),
            )
            return matches[0]
        if len(matches) > 1:
            options = ", ".join(
                m.relative_to(notes_dir).as_posix() for m in matches
            )
            raise FileNotFoundError(
                f"Found {len(matches)} notes with title {query!r}: {options}. "
                f"Pass the exact 'path' of one of them."
            )

    ensure_note_file(candidate, path_repr)
    return candidate  # недостижимо: ensure_note_file бросает исключение

def category_of(path: Path, notes_dir: Path) -> str | None:
    """Категория заметки: относительная папка или ``None`` для корня."""
    parent_rel = path.parent.relative_to(notes_dir).as_posix()
    return None if parent_rel == "." else parent_rel