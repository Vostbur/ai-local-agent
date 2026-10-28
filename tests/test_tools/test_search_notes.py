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
    assert (
        "Молоко" in result[0]["snippet"]
        or "молоко" in result[0]["snippet"].lower()
    )


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


def test_stem_match_word_boundary(tmp_path: Path) -> None:
    note = tmp_path / "test.md"
    note.write_text(
        "# Test\n\nдокументов и недокументированный", encoding="utf-8"
    )
    result = search_notes("документы", tmp_path)
    assert len(result) == 1
    assert result[0]["matches"] == 1


def test_snippet_suffix_when_more_content_after(tmp_path: Path) -> None:
    note = tmp_path / "test.md"
    note.write_text(
        "# Test\n\nхлеб\nкупить молоко\nи другие дела", encoding="utf-8"
    )
    result = search_notes("хлеб", tmp_path)
    assert len(result) == 1
    assert result[0]["snippet"].endswith("…")


def test_no_snippet_suffix_at_end_of_file(tmp_path: Path) -> None:
    note = tmp_path / "test.md"
    note.write_text("# Test\n\nхлеб и молоко", encoding="utf-8")
    result = search_notes("хлеб", tmp_path)
    assert len(result) == 1
    assert not result[0]["snippet"].endswith("…")


def test_max_results_early_exit_reads_only_needed_files(
    tmp_path: Path, monkeypatch
) -> None:
    for i in range(10):
        (tmp_path / f"note_{i}.md").write_text(
            f"# Note {i}\nquery", encoding="utf-8"
        )

    import src.agent.tools.search_notes as mod

    call_count = 0
    original_load = mod.load_note

    def counting_load(path):
        nonlocal call_count
        call_count += 1
        return original_load(path)

    monkeypatch.setattr(mod, "load_note", counting_load)
    result = mod.search_notes("query", tmp_path, max_results=1)

    assert len(result) == 1
    assert call_count == 1


def test_max_results_reads_until_skipped_files_found(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"a_{i}.md").write_text(
            f"# A{i}\nничего", encoding="utf-8"
        )
    for i in range(5):
        (tmp_path / f"b_{i}.md").write_text(
            f"# B{i}\nquery", encoding="utf-8"
        )

    result = search_notes("query", tmp_path, max_results=2)
    assert len(result) == 2


def test_search_notes_none_max_results_uses_default(tmp_path: Path) -> None:
    """max_results=None (как передаёт модель) не ломает search_notes."""
    (tmp_path / "note.md").write_text("# Note\nquery text", encoding="utf-8")

    result = search_notes("query", tmp_path, max_results=None)

    assert len(result) == 1


def test_search_notes_zero_max_results_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Note\nquery text", encoding="utf-8")

    result = search_notes("query", tmp_path, max_results=0)

    assert result == []


def test_search_notes_negative_max_results_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Note\nquery text", encoding="utf-8")

    result = search_notes("query", tmp_path, max_results=-1)

    assert result == []