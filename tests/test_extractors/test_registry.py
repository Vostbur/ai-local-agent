"""Tests for the extractor registry."""

from pathlib import Path

import pymupdf
import pytest

from src.agent.extractors import extract_text, register
from src.agent.extractors.base import ExtractedDocument
from src.agent.extractors.txt import TxtExtractor


@pytest.fixture
def clean_registry(monkeypatch):
    """Изолирует EXTRACTORS от продакшн-регистрации при импорте модуля.

    Возвращает сам словарь, чтобы тесты могли проверять через него,
    а не через локальную ссылку `from ... import EXTRACTORS`, которая
    указывает на старый объект.
    """
    import src.agent.extractors as ex

    fresh: dict = {}
    monkeypatch.setattr(ex, "EXTRACTORS", fresh)
    yield fresh


class TestRegisterAndGet:
    def test_register_and_get(self, clean_registry):
        extractor = TxtExtractor()
        register({".txt"}, extractor)
        assert clean_registry[".txt"] is extractor

    def test_register_multiple_suffixes(self, clean_registry):
        extractor = TxtExtractor()
        register({".txt", ".text"}, extractor)
        assert clean_registry[".txt"] is extractor
        assert clean_registry[".text"] is extractor

    def test_register_duplicate_suffix_raises(self, clean_registry):
        extractor = TxtExtractor()
        register({".txt"}, extractor)
        with pytest.raises(ValueError, match="already registered"):
            register({".txt"}, extractor)

    def test_suffix_normalized_to_lowercase(self, clean_registry):
        extractor = TxtExtractor()
        register({".TXT"}, extractor)
        assert ".txt" in clean_registry
        assert ".TXT" not in clean_registry


class TestExtractText:
    def test_extract_text_dispatches_to_markdown(self, tmp_path: Path):
        md = tmp_path / "note.md"
        md.write_text("# H\nbody", encoding="utf-8")

        result = extract_text(md)

        assert isinstance(result, ExtractedDocument)
        assert result.path == md
        assert result.segments[0].section == "H"

    def test_extract_text_dispatches_to_pdf(self, tmp_path: Path):
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_htmlbox(
            pymupdf.Rect(50, 50, 550, 750), "<p>Тест</p>"
        )
        path = tmp_path / "test.pdf"
        doc.save(path)
        doc.close()

        result = extract_text(path)

        assert isinstance(result, ExtractedDocument)
        assert result.segments[0].section == "Страница 1"
        assert "Тест" in result.segments[0].text

    def test_extract_text_unknown_suffix_returns_none(
        self, tmp_path: Path, caplog
    ):
        # .xyz не зарегистрирован ни одним экстрактором.
        # .pdf раньше был «неизвестным», но с 7.4 зарегистрирован.
        unknown = tmp_path / "file.xyz"
        unknown.write_bytes(b"")

        with caplog.at_level("WARNING", logger="agent"):
            result = extract_text(unknown)

        assert result is None
        assert "no extractor" in caplog.text.lower()

    def test_extract_text_extractor_exception_returns_none(
        self, clean_registry, tmp_path: Path, caplog
    ):
        class BoomExtractor:
            def supported_suffixes(self):
                return {".boom"}

            def extract(self, path):
                raise RuntimeError("boom")

        register({".boom"}, BoomExtractor())
        path = tmp_path / "file.boom"
        path.write_text("x", encoding="utf-8")

        with caplog.at_level("ERROR", logger="agent"):
            result = extract_text(path)

        assert result is None
        assert "Error extracting" in caplog.text
        assert "RuntimeError" in caplog.text