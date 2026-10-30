"""Тесты для write_document."""

from pathlib import Path

import pytest

from src.agent.tools.write_document import write_document


def test_writes_markdown_file(tmp_path: Path) -> None:
    result = write_document("Test", "body", tmp_path)

    assert isinstance(result, dict)
    assert "path" in result

    file_path = Path(result["path"])
    assert file_path.exists()
    assert file_path.suffix == ".md"

    content = file_path.read_text(encoding="utf-8")
    assert content == "# Test\n\nbody\n"


def test_does_not_overwrite(tmp_path: Path) -> None:
    first = write_document("Test", "first", tmp_path)
    second = write_document("Test", "second", tmp_path)

    first_path = Path(first["path"])
    second_path = Path(second["path"])

    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path

    # второй файл должен иметь суффикс _1
    assert second_path.name == "test_1.md"

    # первый файл не изменён
    assert first_path.read_text(encoding="utf-8") == "# Test\n\nfirst\n"


def test_empty_title_raises() -> None:
    with pytest.raises(ValueError, match="title must not be empty"):
        write_document("", "body", Path("/tmp"))


def test_cyrillic_title(tmp_path: Path) -> None:
    result = write_document("Привет", "text", tmp_path)

    file_path = Path(result["path"])
    assert file_path.exists()

    slug = file_path.stem
    assert any(ord(ch) > 127 for ch in slug), "slug должен содержать кириллицу"


def test_returns_size_chars(tmp_path: Path) -> None:
    content = "hello world"
    result = write_document("Title", content, tmp_path)

    assert result["size_chars"] == len(content)


def test_creates_output_dir(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    assert not nested.exists()

    result = write_document("Doc", "body", nested)

    assert Path(result["path"]).exists()
    assert nested.exists()
