"""Tests for search_notes."""

from pathlib import Path

import pytest

from src.agent.tools.search_notes import SEARCH_NOTES_TOOL, search_notes


def test_empty_dir_returns_empty_list(tmp_path: Path) -> None:
    result = search_notes("молоко", tmp_path)

    assert result == []


def test_empty_query_returns_empty_list(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Title\ntext", encoding="utf-8")

    result = search_notes("", tmp_path)

    assert result == []


def test_query_in_body_returns_one_result(tmp_path: Path) -> None:
    note = tmp_path / "shop.md"
    note.write_text("# Список\n\nМолоко, хлеб, яйца", encoding="utf-8")

    result = search_notes("молоко", tmp_path)

    assert len(result) == 1
    assert result[0]["matches"] == 1
    assert "Молоко" in result[0]["snippet"] or "молоко" in result[0]["snippet"].lower()


def test_multiple_matches_same_word(tmp_path: Path) -> None:
    note = tmp_path / "test.md"
    note.write_text("# Тест\n\nхлеб и ещё хлеб", encoding="utf-8")

    result = search_notes("хлеб", tmp_path)

    assert len(result) == 1
    assert result[0]["matches"] == 2


def test_max_results_limits_output(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}\ntext with query", encoding="utf-8"
        )

    result = search_notes("query", tmp_path, max_results=1)

    assert len(result) == 1


def test_query_in_title_not_in_body_not_found(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Поиск\n\nдругой текст без запроса", encoding="utf-8")

    result = search_notes("поиск", tmp_path)

    assert result == []


def test_tool_description_contains_keywords() -> None:
    description = SEARCH_NOTES_TOOL.description

    assert "snippet" in description
    assert "use read_notes" in description


def test_stem_match_finds_word_form(tmp_path: Path) -> None:
    note = tmp_path / "ideas.md"
    note.write_text(
        "# Идеи проекта\n\nСделать локального агента для документов",
        encoding="utf-8",
    )

    result = search_notes("документы", tmp_path, max_results=5)

    assert len(result) > 0
    assert result[0]["matches"] >= 1
    assert "документ" in result[0]["snippet"]


def test_exact_match_still_works(tmp_path: Path) -> None:
    note = tmp_path / "test.md"
    note.write_text("# Тест\n\nхлеб и молоко", encoding="utf-8")

    result = search_notes("молоко", tmp_path)

    assert result[0]["matches"] == 1
