"""Тесты фильтрации корзины в _search.py."""
import pytest
from pathlib import Path

from src.agent.tools._search import (
    _is_in_trash,
    iter_md_files,
    find_notes_by_title,
)


def test_is_in_trash_none():
    """Если trash_dir не задан, ничего не считается корзиной."""
    path = Path("data/notes/trash/note.md")
    assert not _is_in_trash(path, None)


def test_is_in_trash_inside(tmp_path):
    """Файл внутри корзины определяется корректно."""
    trash = tmp_path / "trash"
    trash.mkdir()
    note = trash / "note.md"
    note.write_text("# Test", encoding="utf-8")

    assert _is_in_trash(note, trash)


def test_is_in_trash_nested(tmp_path):
    """Файл во вложенной папке корзины определяется корректно."""
    trash = tmp_path / "trash" / "notes"
    trash.mkdir(parents=True)
    note = trash / "category" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Test", encoding="utf-8")

    assert _is_in_trash(note, tmp_path / "trash")


def test_is_in_trash_outside(tmp_path):
    """Файл вне корзины не считается корзиной."""
    trash = tmp_path / "trash"
    trash.mkdir()
    notes = tmp_path / "notes"
    notes.mkdir()
    note = notes / "note.md"
    note.write_text("# Test", encoding="utf-8")

    assert not _is_in_trash(note, trash)


def test_category_named_trash_is_not_filtered(tmp_path):
    """Категория с именем 'trash' НЕ фильтруется, если trash_dir вне notes_dir."""
    notes_dir = tmp_path / "notes"
    trash_dir = tmp_path / "trash"  # Корзина вне notes_dir

    # Создаём легитимную категорию "trash" внутри notes_dir
    category = notes_dir / "trash"
    category.mkdir(parents=True)
    note = category / "note.md"
    note.write_text("# Заметка в категории trash", encoding="utf-8")

    # Создаём файл в реальной корзине
    trash_dir.mkdir(parents=True)
    trash_note = trash_dir / "deleted.md"
    trash_note.write_text("# Удалённая заметка", encoding="utf-8")

    # Ищем с указанием корзины
    files = iter_md_files(notes_dir, trash_dir=trash_dir)
    assert len(files) == 1
    assert files[0] == note


def test_trash_inside_notes_dir_is_filtered(tmp_path):
    """Если корзина находится внутри notes_dir, её файлы исключаются."""
    notes_dir = tmp_path / "notes"
    trash_dir = notes_dir / "trash"  # Корзина внутри notes_dir

    # Обычная заметка
    notes_dir.mkdir(parents=True)
    normal = notes_dir / "normal.md"
    normal.write_text("# Обычная заметка", encoding="utf-8")

    # Заметка в корзине
    trash_dir.mkdir()
    deleted = trash_dir / "deleted.md"
    deleted.write_text("# Удалённая заметка", encoding="utf-8")

    files = iter_md_files(notes_dir, trash_dir=trash_dir)
    assert len(files) == 1
    assert files[0] == normal


def test_find_notes_by_title_excludes_trash(tmp_path):
    """find_notes_by_title не находит заметки в корзине."""
    notes_dir = tmp_path / "notes"
    trash_dir = tmp_path / "trash"

    # Заметка в корне
    notes_dir.mkdir(parents=True)
    normal = notes_dir / "note.md"
    normal.write_text("# Тест", encoding="utf-8")

    # Заметка с тем же заголовком в корзине
    trash_dir.mkdir(parents=True)
    deleted = trash_dir / "note.md"
    deleted.write_text("# Тест", encoding="utf-8")

    matches = find_notes_by_title("Тест", notes_dir, trash_dir=trash_dir)
    assert len(matches) == 1
    assert matches[0] == normal


def test_backward_compatibility_no_trash_dir(tmp_path):
    """Без trash_dir функция работает как раньше (но без хрупкого фильтра)."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir(parents=True)

    # Создаём категорию с именем "trash" — раньше она была бы отфильтрована
    category = notes_dir / "trash"
    category.mkdir()
    note = category / "note.md"
    note.write_text("# Заметка", encoding="utf-8")

    # Без trash_dir файл должен быть найден
    files = iter_md_files(notes_dir)
    assert len(files) == 1
    assert files[0] == note