from pathlib import Path

from src.agent.tools._search import (
    find_match,
    find_match_with_kind,
    iter_md_files,
    load_note,
)

class TestFindMatchExact:
    def test_exact_match(self):
        result = find_match("Список покупок", "покупок")
        assert result == (7, 14)

    def test_exact_match_returns_kind(self):
        result = find_match_with_kind("Список покупок", "покупок")
        assert result is not None
        assert result[2] == "exact"


class TestFindMatchCaseInsensitive:
    def test_case_insensitive(self):
        result = find_match("Список Покупок", "покупок")
        assert result is not None


class TestFindMatchStem:
    def test_stem_match(self):
        result = find_match("Сделать для документов", "документы")
        assert result is not None

    def test_stem_kind(self):
        _, _, kind = find_match_with_kind("Сделать для документов", "документы")
        assert kind == "stem"

    def test_short_query_no_stem(self):
        result = find_match("стол", "столы")
        assert result is None


class TestFindMatchNoMatch:
    def test_no_match(self):
        result = find_match("Завтра встреча", "проекта")
        assert result is None


class TestFindMatchEmptyQuery:
    def test_empty_query(self):
        result = find_match("текст", "")
        assert result is None


def test_iter_md_files_sorted_and_only_md(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("# B", encoding="utf-8")
    (tmp_path / "a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "c.txt").write_text("not a note", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "d.md").write_text("# D", encoding="utf-8")

    result = iter_md_files(tmp_path)

    names = [p.name for p in result]
    assert names == ["a.md", "b.md"]


def test_load_note_with_heading(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("# Заголовок\n\nтело заметки", encoding="utf-8")

    result = load_note(path)

    assert result == {"title": "Заголовок", "body": "\nтело заметки"}


def test_load_note_without_heading(tmp_path: Path) -> None:
    path = tmp_path / "my_note.md"
    path.write_text("просто текст без заголовка", encoding="utf-8")

    result = load_note(path)

    assert result == {"title": "my_note", "body": "просто текст без заголовка"}


def test_load_note_missing_file_returns_none(tmp_path: Path) -> None:
    result = load_note(tmp_path / "does_not_exist.md")

    assert result is None


def test_load_note_invalid_utf8_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_bytes(b"\xff\xfe\x00\x00 invalid")

    result = load_note(path)

    assert result is None


def test_stem_uses_word_boundary():
    """«документы» не матчит «недокументированный» (нет \b перед «докум»)."""
    assert find_match("недокументированный", "документы") is None


def test_stem_matches_shorter_word_form():
    """«документы» находит «документ» через стем на границе слова."""
    result = find_match("документ", "документы")
    assert result is not None
    assert result[0] == 0


def test_stem_matches_word_form_at_boundary():
    """«требования» находит «требований» через стем."""
    result = find_match("система требований", "требования")
    assert result is not None