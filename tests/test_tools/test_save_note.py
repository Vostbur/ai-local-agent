"""Тесты инструмента save_note.

Контракт: save_note возвращает dict {"path": относительный путь, "title": str, "category": str | None}.
Путь относительный от notes_dir (POSIX-слэши) — удобно передавать в другие инструменты.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.tools.save_note import SAVE_NOTE_TOOL, save_note


def _saved_path(result: dict, notes_dir: Path) -> Path:
    """Абсолютный путь из dict, возвращённого save_note."""
    return notes_dir / result["path"]


def test_saves_note_and_returns_path(tmp_path: Path) -> None:
    result = save_note("Заголовок", "текст", tmp_path)

    assert isinstance(result, dict)
    assert result["title"] == "Заголовок"
    assert result["category"] is None
    saved = _saved_path(result, tmp_path)
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == "# Заголовок\n\nтекст\n"


def test_duplicate_title_creates_suffixed_file(tmp_path: Path) -> None:
    first = save_note("My Note", "content1", tmp_path)
    second = save_note("My Note", "content2", tmp_path)

    first_path = _saved_path(first, tmp_path)
    second_path = _saved_path(second, tmp_path)
    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path
    assert first_path.name == "my_note.md"
    assert second_path.name == "my_note_1.md"


def test_creates_notes_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "notes"
    result = save_note("Title", "body", target)

    assert target.is_dir()
    saved = _saved_path(result, target)
    assert saved.exists()


def test_empty_title_raises_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_note("", "content", tmp_path)


def test_cyrillic_title_saved_in_filename(tmp_path: Path) -> None:
    result = save_note("Привет", "text", tmp_path)
    saved = _saved_path(result, tmp_path)
    assert saved.name == "привет.md"


def test_special_chars_removed_from_filename(tmp_path: Path) -> None:
    result = save_note('file<>:"/\\|?*name', "data", tmp_path)
    saved = _saved_path(result, tmp_path)
    assert "<" not in saved.name
    assert ">" not in saved.name


def test_save_note_tool_description_has_russian_triggers() -> None:
    desc = SAVE_NOTE_TOOL.description.lower()
    assert "сохранить заметку" in desc
    assert "записать заметку" in desc
    assert "создать заметку" in desc
    assert "save a note" in desc
    assert "never overwrites" in desc


def test_reserved_windows_name_gets_prefix(tmp_path: Path) -> None:
    """Зарезервированные имена Windows получают префикс '_'."""
    for name in ("CON", "con", "PRN", "AUX", "NUL", "COM1", "com9", "LPT1", "lpt9"):
        result = save_note(name, "x", tmp_path)
        saved = _saved_path(result, tmp_path)
        assert saved.stem.startswith("_"), f"{name!r} not prefixed: {saved.stem!r}"


def test_reserved_like_name_not_prefixed(tmp_path: Path) -> None:
    """Похожие на зарезервированные, но не они — без префикса."""
    for name in ("CONSOLE", "connection", "com", "com0", "com10", "lpt0", "lpt10"):
        result = save_note(name, "x", tmp_path)
        saved = _saved_path(result, tmp_path)
        assert not saved.stem.startswith("_"), f"{name!r} unexpectedly prefixed: {saved.stem!r}"


def test_no_trailing_dot_or_space(tmp_path: Path) -> None:
    """Trailing точка или пробел не остаются в имени файла."""
    result = save_note("hello world . ", "x", tmp_path)
    saved = _saved_path(result, tmp_path)
    assert not saved.stem.endswith(".")


def test_title_description_does_not_suggest_inventing() -> None:
    """Описание параметра title не должно провоцировать модель выдумывать заголовок."""
    schema = SAVE_NOTE_TOOL.parameters
    desc = schema["properties"]["title"]["description"]
    assert "invent" in desc or "не выдумывай" in desc or "не придумывай" in desc
    # Урок 6.7/T26: промпт не просит извлекать "short descriptive phrase"
    assert "extract" not in desc.lower()
    assert "short descriptive" not in desc.lower()


def test_save_note_with_category(tmp_path: Path) -> None:
    """Категория создаётся как подпапка."""
    result = save_note("Заголовок", "текст", tmp_path, category="Работа")

    assert result["category"] == "работа"
    assert result["path"] == "работа/заголовок.md"
    saved = _saved_path(result, tmp_path)
    assert saved.exists()
    assert saved.parent.name == "работа"


def test_save_note_invalid_category_raises(tmp_path: Path) -> None:
    """Запрещённые символы в категории (path traversal) отбрасываются."""
    with pytest.raises(ValueError):
        save_note("X", "y", tmp_path, category="..")
    with pytest.raises(ValueError):
        save_note("X", "y", tmp_path, category="parent/child")
    with pytest.raises(ValueError):
        save_note("X", "y", tmp_path, category="parent\\child")


def test_save_note_empty_category_means_root(tmp_path: Path) -> None:
    """Пустая строка или None в категории — корневая директория notes_dir."""
    result1 = save_note("A", "x", tmp_path, category="")
    result2 = save_note("B", "y", tmp_path, category=None)

    assert result1["category"] is None
    assert result2["category"] is None
    assert _saved_path(result1, tmp_path).parent == tmp_path
    assert _saved_path(result2, tmp_path).parent == tmp_path


def test_save_note_reserved_category_raises(tmp_path: Path) -> None:
    """Зарезервированные имена Windows запрещены и для категорий."""
    for name in ("CON", "con", "NUL", "COM1", "lpt1"):
        with pytest.raises(ValueError):
            save_note("X", "y", tmp_path, category=name)