"""Tests for save_note."""

from pathlib import Path

import pytest

from src.agent.tools.save_note import SAVE_NOTE_TOOL, save_note


def test_saves_note_and_returns_path(tmp_path: Path) -> None:
    result = save_note("Заголовок", "текст", tmp_path)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_text(encoding="utf-8") == "# Заголовок\n\nтекст\n"


def test_duplicate_title_creates_suffixed_file(tmp_path: Path) -> None:
    first = save_note("My Note", "content1", tmp_path)
    second = save_note("My Note", "content2", tmp_path)

    assert first.exists()
    assert first.read_text(encoding="utf-8") == "# My Note\n\ncontent1\n"
    assert second != first
    assert second.exists()
    assert second.name == "my_note_1.md"
    assert second.read_text(encoding="utf-8") == "# My Note\n\ncontent2\n"


def test_creates_notes_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "notes"
    result = save_note("Title", "body", target)

    assert target.is_dir()
    assert result.exists()


def test_empty_title_raises_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="title must not be empty"):
        save_note("", "content", tmp_path)

    with pytest.raises(ValueError, match="title must not be empty"):
        save_note("   ", "content", tmp_path)


def test_cyrillic_title_saved_in_filename(tmp_path: Path) -> None:
    result = save_note("Привет", "text", tmp_path)

    assert result.name == "привет.md"
    assert result.exists()


def test_special_chars_removed_from_filename(tmp_path: Path) -> None:
    result = save_note('file<>:"/\\|?*name', "data", tmp_path)

    assert "<" not in result.name
    assert ">" not in result.name
    assert '"' not in result.name
    assert "/" not in result.name
    assert "\\" not in result.name
    assert "|" not in result.name
    assert "?" not in result.name
    assert "*" not in result.name
    assert result.name == "filename.md"


def test_save_note_tool_description_has_russian_triggers() -> None:
    description = SAVE_NOTE_TOOL.description

    assert any(
        word in description
        for word in ["заметку", "записать", "сохранить"]
    )

    assert "save" in description

    assert len(description) <= 300

    title_desc = SAVE_NOTE_TOOL.parameters["properties"]["title"]["description"]
    assert title_desc
    assert "Example" in title_desc

    content_desc = SAVE_NOTE_TOOL.parameters["properties"]["content"]["description"]
    assert "empty string" in content_desc


def test_reserved_windows_name_gets_prefix(tmp_path: Path) -> None:
    """Зарезервированные имена Windows получают префикс '_'."""
    for name in ("CON", "con", "PRN", "AUX", "NUL", "COM1", "com9", "LPT1", "lpt9"):
        path = save_note(name, "x", tmp_path)
        assert path.stem.startswith("_"), f"{name!r} not prefixed: {path.stem!r}"


def test_reserved_like_name_not_prefixed(tmp_path: Path) -> None:
    """Похожие на зарезервированные, но не они — без префикса."""
    for name in ("CONSOLE", "connection", "com", "com0", "com10", "lpt0", "lpt10"):
        path = save_note(name, "x", tmp_path)
        assert not path.stem.startswith("_"), f"{name!r} unexpectedly prefixed: {path.stem!r}"


def test_no_trailing_dot_or_space(tmp_path: Path) -> None:
    """Trailing точка или пробел не остаются в имени файла."""
    path = save_note("hello world . ", "x", tmp_path)
    assert not path.stem.endswith(".")
    assert not path.stem.endswith(" ")
    assert path.stem  # не пустой


def test_title_description_does_not_suggest_inventing() -> None:
    desc = SAVE_NOTE_TOOL.parameters["properties"]["title"]["description"]

    assert "do NOT invent" in desc
    assert "ask the user for clarification" in desc
    assert "extract a short descriptive phrase" not in desc