"""Tests for read_notes."""

from pathlib import Path

import pytest

from src.agent.tools.read_notes import READ_NOTES_TOOL, read_notes


def test_empty_dir_returns_empty_list(tmp_path: Path) -> None:
    result = read_notes("", tmp_path)

    assert result == []


def test_nonexistent_dir_returns_empty_list(tmp_path: Path) -> None:
    notes_dir = tmp_path / "does_not_exist"

    result = read_notes("", notes_dir)

    assert result == []


def test_two_notes_query_matches_title(tmp_path: Path) -> None:
    shop = tmp_path / "shop.md"
    shop.write_text("# Список покупок\nхлеб, молоко", encoding="utf-8")

    ideas = tmp_path / "ideas.md"
    ideas.write_text("# Идеи\nновая фича", encoding="utf-8")

    result = read_notes("покуп", tmp_path)

    assert len(result) == 1
    assert result[0]["title"] == "Список покупок"
    assert "хлеб" in result[0]["preview"]


def test_empty_query_returns_all_notes(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}\ntext {i}", encoding="utf-8"
        )

    result = read_notes("", tmp_path)

    assert len(result) == 10


def test_empty_query_respects_max_results(tmp_path: Path) -> None:
    for i in range(60):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}\ntext {i}", encoding="utf-8"
        )

    result = read_notes("", tmp_path)

    assert len(result) == 50


def test_query_matches_filename_not_title(tmp_path: Path) -> None:
    file_path = tmp_path / "купить_хлеб.md"
    file_path.write_text("# Список\nхлеб", encoding="utf-8")

    result = read_notes("хлеб", tmp_path)

    assert len(result) == 1
    assert result[0]["title"] == "Список"


def test_case_insensitive_query(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Список покупок\nмного всего", encoding="utf-8")

    result = read_notes("СПИСОК", tmp_path)

    assert len(result) == 1
    assert result[0]["title"] == "Список покупок"


def test_multiword_query_matches_full_phrase_only(tmp_path: Path) -> None:
    (tmp_path / "идеи_проекта.md").write_text(
        "# Идеи проекта\ntext", encoding="utf-8"
    )
    (tmp_path / "идеи.md").write_text("# Идеи\ntext", encoding="utf-8")
    (tmp_path / "завтра_встреча_с_командой.md").write_text(
        "# Завтра встреча с командой\nСделать локального агента для документов",
        encoding="utf-8",
    )

    result = read_notes("Идеи проекта", tmp_path)

    assert len(result) == 1
    assert result[0]["title"] == "Идеи проекта"


def test_body_match_not_included(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Заметка\nпроекты на будущий месяц", encoding="utf-8")

    result = read_notes("проекты", tmp_path)

    assert result == []


def test_tool_description_contains_keywords() -> None:
    description = READ_NOTES_TOOL.description

    assert "заметки" in description
    assert "list notes" in description
    # 400: описание содержит routing-примеры для 3B-модели (шаг 6.4)
    assert len(description) <= 400


def test_read_notes_without_query_returns_all(tmp_path: Path) -> None:
    (tmp_path / "first.md").write_text("# First\nnote one", encoding="utf-8")
    (tmp_path / "second.md").write_text("# Second\nnote two", encoding="utf-8")

    result = read_notes(notes_dir=tmp_path)

    assert len(result) == 2


def test_tool_schema_query_not_required() -> None:
    assert "required" not in READ_NOTES_TOOL.parameters or "query" not in READ_NOTES_TOOL.parameters.get("required", [])

def test_read_notes_default_notes_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """Вызов без notes_dir не падает и использует Path('data/notes')."""
    monkeypatch.chdir(tmp_path)
    default_dir = tmp_path / "data" / "notes"
    default_dir.mkdir(parents=True)
    (default_dir / "test.md").write_text("# Test\n\nbody", encoding="utf-8")

    result = read_notes("")

    assert len(result) == 1
    assert result[0]["title"] == "Test"

def test_read_notes_custom_max_results(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}\ntext {i}", encoding="utf-8"
        )

    result = read_notes("", tmp_path, max_results=3)

    assert len(result) == 3


def test_tool_schema_has_max_results() -> None:
    props = READ_NOTES_TOOL.parameters["properties"]

    assert "max_results" in props
    assert props["max_results"]["type"] == "integer"
    assert props["max_results"].get("default") == 50


def test_read_notes_none_max_results_uses_default(tmp_path: Path) -> None:
    """max_results=None (как передаёт модель) не ломает read_notes."""
    for i in range(3):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}", encoding="utf-8"
        )

    result = read_notes("", tmp_path, max_results=None)

    assert len(result) == 3


def test_read_notes_zero_max_results_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Note", encoding="utf-8")

    result = read_notes("", tmp_path, max_results=0)

    assert result == []


def test_read_notes_negative_max_results_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Note", encoding="utf-8")

    result = read_notes("", tmp_path, max_results=-5)

    assert result == []