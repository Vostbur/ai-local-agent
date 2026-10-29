"""Tests for the TXT document extractor."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.agent.extractors.base import ExtractedDocument, Segment
from src.agent.extractors.txt import TxtExtractor


@pytest.fixture
def extractor():
    return TxtExtractor()


class TestSimpleUtf8:
    def test_single_segment_no_section(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("hello world", encoding="utf-8")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0] == Segment(text="hello world", section=None)


class TestEmptyFile:
    def test_empty_file_returns_empty_segments(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("", encoding="utf-8")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert result.segments == []


class TestCp1251Fallback:
    def test_cp1251_file_read_correctly(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("Привет мир", encoding="cp1251")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].text == "Привет мир"
        assert result.segments[0].section is None


class TestUtf8BomHandled:
    def test_bom_not_in_text(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("\ufeffhello world", encoding="utf-8")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert "\ufeff" not in result.segments[0].text
        assert result.segments[0].text == "hello world"


class TestMissingFile:
    def test_missing_file_returns_none(self, extractor: TxtExtractor, caplog):
        with caplog.at_level(logging.WARNING, logger="agent"):
            result = extractor.extract(Path("/nonexistent/file.txt"))

        assert result is None
        assert "nonexistent" in caplog.text


class TestMultipleSpacesNormalized:
    def test_spaces_collapsed(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("a   b    c", encoding="utf-8")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].text == "a b c"


class TestNoHeadingParsing:
    def test_hash_at_start_not_split(self, extractor: TxtExtractor, tmp_path: Path):
        txt = tmp_path / "test.txt"
        txt.write_text("# Not a heading\nMore text", encoding="utf-8")

        result = extractor.extract(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].section is None
        assert "# Not a heading" in result.segments[0].text
        assert "More text" in result.segments[0].text
