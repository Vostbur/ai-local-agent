"""Tests for read_document tool."""

from pathlib import Path

import pymupdf
import pytest

from src.agent.tools.read_document import read_document


@pytest.fixture()
def patched_root(tmp_path: Path, monkeypatch):
    """Подменить _PROJECT_ROOT на tmp_path, чтобы тестовые файлы были «внутри проекта»."""
    monkeypatch.setattr(
        "src.agent.tools.read_document._PROJECT_ROOT", tmp_path
    )
    return tmp_path


@pytest.fixture()
def make_pdf(tmp_path: Path):
    """PDF с текстовыми страницами через insert_htmlbox (кириллица)."""

    def _make_pdf(pages: list[str]) -> Path:
        doc = pymupdf.open()
        for text in pages:
            page = doc.new_page()
            page.insert_htmlbox(
                pymupdf.Rect(50, 50, 550, 750), f"<p>{text}</p>"
            )
        pdf_path = tmp_path / f"test_{len(pages)}pages.pdf"
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    return _make_pdf


def test_reads_markdown_file(patched_root: Path) -> None:
    path = patched_root / "template.md"
    path.write_text("# Template\n\nSome content here.", encoding="utf-8")

    result = read_document(str(path))

    assert result["path"] == str(path.resolve())
    assert result["suffix"] == ".md"
    assert "Some content here" in result["text"]
    # Markdown-экстрактор убирает заголовок "# Template" в section;
    # в text остаётся только body.
    assert "# Template" not in result["text"]
    assert result["truncated"] is False
    assert result["total_chars"] == len("Some content here.")


def test_reads_txt_file(patched_root: Path) -> None:
    path = patched_root / "readme.txt"
    path.write_text("Hello world\nLine two.", encoding="utf-8")

    result = read_document(str(path))

    assert result["suffix"] == ".txt"
    assert "Hello world" in result["text"]
    assert "Line two" in result["text"]


def test_reads_pdf_file(patched_root: Path, make_pdf) -> None:
    pdf_path = make_pdf(["Привет", "Тест"])

    result = read_document(str(pdf_path))

    assert result["suffix"] == ".pdf"
    assert "Привет" in result["text"]
    assert "Тест" in result["text"]


def test_truncates_long_document(patched_root: Path) -> None:
    long_text = "x" * 10_000
    path = patched_root / "long.md"
    path.write_text(long_text, encoding="utf-8")

    result = read_document(str(path), max_chars=1000)

    assert len(result["text"]) == 1000
    assert result["truncated"] is True
    assert result["total_chars"] == 10_000


def test_short_document_not_truncated(patched_root: Path) -> None:
    short_text = "y" * 500
    path = patched_root / "short.md"
    path.write_text(short_text, encoding="utf-8")

    result = read_document(str(path), max_chars=4000)

    assert result["truncated"] is False
    assert result["total_chars"] == 500
    assert len(result["text"]) == 500


def test_relative_path_resolved_from_project_root(
    patched_root: Path,
) -> None:
    data_dir = patched_root / "data" / "documents"
    data_dir.mkdir(parents=True)
    readme = data_dir / "README.md"
    readme.write_text("# README\n\nProject documentation.", encoding="utf-8")

    result = read_document("data/documents/README.md")

    assert Path(result["path"]).parts[-3:] == (
        "data",
        "documents",
        "README.md",
    )
    assert "Project documentation" in result["text"]


def test_path_outside_project_raises(tmp_path: Path, monkeypatch) -> None:
    """Путь вне _PROJECT_ROOT → ValueError (path traversal защита)."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    monkeypatch.setattr(
        "src.agent.tools.read_document._PROJECT_ROOT", project
    )

    with pytest.raises(ValueError, match="path must be inside project"):
        read_document(str(outside))


def test_unknown_suffix_raises(patched_root: Path) -> None:
    fake_file = patched_root / "file.xyz"
    fake_file.write_text("data", encoding="utf-8")

    with pytest.raises(ValueError, match="no extractor for suffix"):
        read_document(str(fake_file))


def test_missing_file_raises(patched_root: Path) -> None:
    missing = patched_root / "does_not_exist.md"

    with pytest.raises(ValueError, match="cannot read"):
        read_document(str(missing))