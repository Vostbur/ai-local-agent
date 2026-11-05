"""Тесты DocxExtractor после исправления T42."""
from __future__ import annotations

import logging
from pathlib import Path

from src.agent.extractors import EXTRACTORS
from src.agent.extractors.docx import DocxExtractor


def _make_docx(path: Path) -> Path:
    """Собрать минимальный DOCX: заголовок, абзацы, пустой абзац."""
    from docx import Document

    doc = Document()
    doc.add_heading("Заголовок раздела", level=1)
    doc.add_paragraph("Первый абзац текста.")
    doc.add_paragraph("")  # пустой — должен быть пропущен
    doc.add_paragraph("Второй абзац текста.")
    doc.save(path)
    return path


def test_supported_suffixes():
    """Метод протокола TextExtractor присутствует (T42)."""
    assert DocxExtractor().supported_suffixes() == {".docx"}


def test_registered_in_registry():
    """.docx зарегистрирован в реестре экстракторов."""
    assert ".docx" in EXTRACTORS
    assert isinstance(EXTRACTORS[".docx"], DocxExtractor)


def test_no_legacy_import_prefix():
    """Регресс-страх граблей импортов: префикс только src.agent (T42)."""
    import src.agent.extractors.docx as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from agent." not in src
    assert "import agent." not in src


def test_extract_sections_only_for_headings(tmp_path):
    """section — только заголовочные стили; у обычных абзацев None (T42)."""
    path = _make_docx(tmp_path / "sample.docx")

    doc = DocxExtractor().extract(path)

    assert doc is not None
    assert [s.section for s in doc.segments] == ["Heading 1", None, None]
    assert [s.text for s in doc.segments] == [
        "Заголовок раздела",
        "Первый абзац текста.",
        "Второй абзац текста.",
    ]
    assert doc.metadata["format"] == "docx"
    assert doc.metadata["paragraphs"] == 4


def test_extract_skips_empty_paragraphs(tmp_path):
    path = _make_docx(tmp_path / "sample.docx")

    doc = DocxExtractor().extract(path)

    assert doc is not None
    assert len(doc.segments) == 3
    assert all(s.text.strip() for s in doc.segments)


def test_extract_broken_file_returns_none_with_warning(tmp_path, caplog):
    """Битый DOCX → None + warning в логе, а не тихий пропуск (T42)."""
    bad = tmp_path / "broken.docx"
    bad.write_bytes(b"this is not a docx file at all")

    with caplog.at_level(logging.WARNING, logger="agent"):
        result = DocxExtractor().extract(bad)

    assert result is None
    assert any("Failed to open DOCX" in rec.message for rec in caplog.records)


def test_extract_missing_file_returns_none(tmp_path):
    result = DocxExtractor().extract(tmp_path / "nope.docx")
    assert result is None