"""Тесты CRUD-инструментов заметок (этап B): без LLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.tools.delete_note import delete_note
from src.agent.tools.list_categories import list_categories
from src.agent.tools.list_notes import list_notes
from src.agent.tools.move_note import move_note
from src.agent.tools.save_note import save_note
from src.agent.tools.update_note import update_note


@pytest.fixture
def notes_dir(tmp_path: Path) -> Path:
    d = tmp_path / "notes"
    d.mkdir()
    return d


@pytest.fixture
def trash_dir(tmp_path: Path) -> Path:
    return tmp_path / "trash"


def _seed(notes_dir: Path) -> None:
    save_note("Первая", "текст один", notes_dir)
    save_note("Вторая", "текст два", notes_dir, category="работа")
    save_note("Третья", "текст три", notes_dir, category="работа")


class TestListNotes:
    def test_all_notes(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = list_notes(notes_dir)
        assert len(result) == 3
        paths = {r["path"] for r in result}
        assert "первая.md" in paths
        assert "работа/вторая.md" in paths

    def test_by_category(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = list_notes(notes_dir, category="работа")
        assert len(result) == 2
        assert all(r["category"] == "работа" for r in result)

    def test_missing_category_returns_empty(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        assert list_notes(notes_dir, category="нет_такой") == []

    def test_root_notes_have_none_category(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        root = [r for r in list_notes(notes_dir) if r["path"] == "первая.md"]
        assert root[0]["category"] is None

    def test_max_results(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        assert len(list_notes(notes_dir, max_results=1)) == 1
        assert list_notes(notes_dir, max_results=0) == []
        assert list_notes(notes_dir, max_results=-5) == []

    def test_result_fields(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        item = list_notes(notes_dir)[0]
        assert set(item.keys()) == {
            "path", "title", "category", "modified", "size_chars"
        }


class TestUpdateNote:
    def test_update_title(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("первая.md", notes_dir, title="Новый заголовок")
        assert result["title"] == "Новый заголовок"
        text = (notes_dir / "первая.md").read_text(encoding="utf-8")
        assert text.startswith("# Новый заголовок")
        assert "текст один" in text

    def test_update_content(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("первая.md", notes_dir, content="новое тело")
        text = (notes_dir / "первая.md").read_text(encoding="utf-8")
        assert "новое тело" in text
        assert "текст один" not in text
        assert result["title"] == "Первая"  # заголовок сохранён

    def test_file_not_renamed_on_title_change(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        update_note("первая.md", notes_dir, title="Совсем другое имя")
        assert (notes_dir / "первая.md").exists()
        assert not (notes_dir / "совсем_другое_имя.md").exists()

    def test_update_in_category(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("работа/вторая.md", notes_dir, content="x")
        assert result["path"] == "работа/вторая.md"

    def test_missing_note_raises(self, notes_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            update_note("нет_такой.md", notes_dir, title="X")

    def test_nothing_to_update_raises(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        with pytest.raises(ValueError):
            update_note("первая.md", notes_dir)

    def test_empty_title_raises(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        with pytest.raises(ValueError):
            update_note("первая.md", notes_dir, title="   ")

    def test_path_traversal_rejected(self, notes_dir: Path, tmp_path: Path) -> None:
        _seed(notes_dir)
        outside = tmp_path / "outside.md"
        outside.write_text("# Outside", encoding="utf-8")
        with pytest.raises(ValueError):
            update_note("../outside.md", notes_dir, title="X")

    def test_strips_duplicate_heading(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        update_note(
            "первая.md",
            notes_dir,
            title="Новый заголовок",
            content="# Новый заголовок\n\nтекст",
        )
        text = (notes_dir / "первая.md").read_text(encoding="utf-8")
        assert text.count("# Новый заголовок") == 1


class TestDeleteNote:
    def test_moves_to_trash(self, notes_dir: Path, trash_dir: Path) -> None:
        _seed(notes_dir)
        result = delete_note("первая.md", notes_dir, trash_dir)
        assert not (notes_dir / "первая.md").exists()
        moved = Path(result["moved_to"])
        assert moved.exists()
        assert moved.parent == trash_dir / "notes"
        assert moved.name.endswith("_первая.md")

    def test_category_structure_preserved(self, notes_dir: Path, trash_dir: Path) -> None:
        _seed(notes_dir)
        result = delete_note("работа/вторая.md", notes_dir, trash_dir)
        moved = Path(result["moved_to"])
        assert moved.parent == trash_dir / "notes" / "работа"

    def test_missing_note_raises(self, notes_dir: Path, trash_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            delete_note("нет_такой.md", notes_dir, trash_dir)

    def test_deleted_paths_differ(self, notes_dir: Path, trash_dir: Path) -> None:
        _seed(notes_dir)
        r1 = delete_note("первая.md", notes_dir, trash_dir)
        r2 = delete_note("работа/вторая.md", notes_dir, trash_dir)
        assert Path(r1["moved_to"]) != Path(r2["moved_to"])


class TestMoveNote:
    def test_move_to_category(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = move_note("первая.md", "архив", notes_dir)
        assert result["moved"] is True
        assert result["path"] == "архив/первая.md"
        assert (notes_dir / "архив" / "первая.md").exists()
        assert not (notes_dir / "первая.md").exists()

    def test_move_to_root(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = move_note("работа/вторая.md", None, notes_dir)
        assert result["path"] == "вторая.md"
        assert result["category"] is None
        assert (notes_dir / "вторая.md").exists()

    def test_same_category_noop(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = move_note("работа/вторая.md", "работа", notes_dir)
        assert result["moved"] is False
        assert (notes_dir / "работа" / "вторая.md").exists()

    def test_conflict_gets_suffix(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        save_note("Первая", "другой текст", notes_dir, category="работа")
        result = move_note("первая.md", "работа", notes_dir)
        assert result["path"] == "работа/первая_1.md"

    def test_invalid_category_raises(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        with pytest.raises(ValueError):
            move_note("первая.md", "../evil", notes_dir)

    def test_missing_note_raises(self, notes_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            move_note("нет_такой.md", "архив", notes_dir)


class TestListCategories:
    def test_counts(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = list_categories(notes_dir)
        by_name = {r["name"]: r["note_count"] for r in result}
        assert by_name[""] == 1
        assert by_name["работа"] == 2

    def test_empty_dir(self, notes_dir: Path) -> None:
        assert list_categories(notes_dir) == [{"name": "", "note_count": 0}]

    def test_missing_dir(self, tmp_path: Path) -> None:
        assert list_categories(tmp_path / "нет") == []


class TestErrorMessageGuidesToSearch:
    """Ошибка 'заметка не найдена' должна подсказывать модели, что делать.

    Страховка от сценария smoke 2026-10-30: модель передала заголовок
    'Тест B1' вместо пути и после невнятной ошибки завершила задачу,
    не попробовав сначала найти путь.
    """

    def test_update_note_error_mentions_search_tools(self, notes_dir: Path) -> None:
        with pytest.raises(FileNotFoundError) as exc:
            update_note("Тест B1", notes_dir, title="X")
        msg = str(exc.value)
        assert "list_notes" in msg
        assert "read_notes" in msg
        assert "NOT the note title" in msg

    def test_move_note_error_mentions_search_tools(self, notes_dir: Path) -> None:
        with pytest.raises(FileNotFoundError) as exc:
            move_note("Тест B1", "архив", notes_dir)
        msg = str(exc.value)
        assert "list_notes" in msg
        assert "read_notes" in msg

    def test_delete_note_error_mentions_search_tools(
        self, notes_dir: Path, trash_dir: Path
    ) -> None:
        with pytest.raises(FileNotFoundError) as exc:
            delete_note("Тест B1", notes_dir, trash_dir)
        msg = str(exc.value)
        assert "list_notes" in msg
        assert "read_notes" in msg


class TestToolDescriptionsWarnAboutPath:
    """Описание параметра path должно явно запрещать передавать заголовок."""

    def test_update_note_path_description(self) -> None:
        from src.agent.tools.update_note import UPDATE_NOTE_TOOL

        desc = UPDATE_NOTE_TOOL.parameters["properties"]["path"]["description"]
        assert "NOT the note title" in desc

    def test_move_note_path_description(self) -> None:
        from src.agent.tools.move_note import MOVE_NOTE_TOOL

        desc = MOVE_NOTE_TOOL.parameters["properties"]["path"]["description"]
        assert "NOT the note title" in desc

    def test_delete_note_path_description(self) -> None:
        from src.agent.tools.delete_note import DELETE_NOTE_TOOL

        desc = DELETE_NOTE_TOOL.parameters["properties"]["path"]["description"]
        assert "NOT the note title" in desc


class TestTitleFallback:
    """План Б: инструменты принимают заголовок вместо пути.

    Страховка от устойчивого поведения 7B (три прогона 2026-10-30):
    модель передаёт заголовок вместо пути и не восстанавливается
    после направляющей ошибки.
    """

    def test_update_by_title(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("Первая", notes_dir, content="новое")
        assert result["path"] == "первая.md"
        assert (notes_dir / "первая.md").read_text(encoding="utf-8").count("новое") == 1

    def test_update_by_category_and_title(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("работа/Вторая", notes_dir, content="x")
        assert result["path"] == "работа/вторая.md"

    def test_update_by_title_with_md_suffix(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = update_note("тесты/Третья".replace("тесты", "работа"), notes_dir, content="x")
        assert result["path"] == "работа/третья.md"

    def test_move_by_title(self, notes_dir: Path) -> None:
        _seed(notes_dir)
        result = move_note("Первая", "архив", notes_dir)
        assert result["path"] == "архив/первая.md"
        assert (notes_dir / "архив" / "первая.md").exists()

    def test_delete_by_title(self, notes_dir: Path, trash_dir: Path) -> None:
        _seed(notes_dir)
        result = delete_note("Первая", notes_dir, trash_dir)
        assert not (notes_dir / "первая.md").exists()
        assert Path(result["moved_to"]).exists()

    def test_ambiguous_title_lists_candidates(
        self, notes_dir: Path, trash_dir: Path
    ) -> None:
        save_note("Дубль", "один", notes_dir)
        save_note("Дубль", "два", notes_dir)  # файл дубль_1.md, заголовок тот же
        with pytest.raises(FileNotFoundError) as exc:
            delete_note("Дубль", notes_dir, trash_dir)
        msg = str(exc.value)
        assert "дубль.md" in msg
        assert "дубль_1.md" in msg
        # Оба файла на месте — ничего не удалено.
        assert (notes_dir / "дубль.md").exists()
        assert (notes_dir / "дубль_1.md").exists()

    def test_no_match_raises_guiding_error(
        self, notes_dir: Path, trash_dir: Path
    ) -> None:
        with pytest.raises(FileNotFoundError) as exc:
            delete_note("Не существует", notes_dir, trash_dir)
        assert "list_notes" in str(exc.value)

    def test_exact_path_still_preferred_over_title(self, notes_dir: Path) -> None:
        """Если файл по пути существует — фолбэк не срабатывает."""
        _seed(notes_dir)
        result = update_note("работа/вторая.md", notes_dir, content="x")
        assert result["path"] == "работа/вторая.md"