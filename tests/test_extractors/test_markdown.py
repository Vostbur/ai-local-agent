"""Tests for the Markdown document extractor."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.agent.extractors.base import ExtractedDocument, Segment
from src.agent.extractors.markdown import MarkdownExtractor


@pytest.fixture
def extractor():
    return MarkdownExtractor()


class TestSimpleWithHeadings:
    def test_two_segments(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H1\ntext1\n## H2\ntext2", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 2
        assert result.segments[0] == Segment(text="text1", section="H1")
        assert result.segments[1] == Segment(text="text2", section="H2")


class TestNoHeadings:
    def test_single_segment_no_section(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("just text", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0] == Segment(text="just text", section=None)


class TestPreambleBeforeFirstHeading:
    def test_preamble_and_section(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("intro\n# H1\ntext", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 2
        assert result.segments[0] == Segment(text="intro", section=None)
        assert result.segments[1] == Segment(text="text", section="H1")


class TestEmptyFile:
    def test_empty_file_returns_empty_segments(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert result.segments == []


class TestHeadingWithoutBodySkipped:
    def test_header_without_body_ignored(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H1\n## H2\ntext", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0] == Segment(text="text", section="H2")


class TestCodeBlockRemoved:
    def test_fenced_code_block_stripped(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\ntext\n```python\ncode\n```\nmore", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        seg = result.segments[0]
        assert seg.section == "H"
        assert "code" not in seg.text
        assert "text" in seg.text
        assert "more" in seg.text


class TestInlineCodeRemoved:
    def test_inline_code_stripped(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\ntext `zzz` more", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert "zzz" not in seg.text
        assert "text" in seg.text
        assert "more" in seg.text


class TestImageRemoved:
    def test_image_completely_removed(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\n![alt](https://example.com/img.png) text", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert "alt" not in seg.text
        assert "example.com" not in seg.text
        assert "img.png" not in seg.text
        assert "text" in seg.text


class TestLinkUnwrapped:
    def test_link_url_removed_text_kept(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\nsee [docs](https://example.com) here", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert "docs" in seg.text
        assert "https" not in seg.text
        assert "example.com" not in seg.text
        assert "see" in seg.text
        assert "here" in seg.text


class TestInlineFormattingRemoved:
    def test_bold_italic_stripped(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\n**bold** *italic* ~~strike~~", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert "bold" in seg.text
        assert "italic" in seg.text
        assert "strike" in seg.text
        assert "**" not in seg.text
        assert "*" not in seg.text
        assert "~~" not in seg.text


class TestHtmlTagsRemoved:
    def test_html_tags_stripped(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\n<div>text</div>", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert seg.text == "text"
        assert "<div>" not in seg.text


class TestCyrillicPreserved:
    def test_cyrillic_text_untouched(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# Заголовок\nТело", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].section == "Заголовок"
        assert result.segments[0].text == "Тело"


class TestUtf8BomHandled:
    def test_bom_not_in_text(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("\ufeff# H\ntext", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        seg = result.segments[0]
        assert seg.text.startswith("text")
        assert "\ufeff" not in seg.text


class TestCp1251Fallback:
    def test_cp1251_file_read_correctly(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# Заголовок\nТело", encoding="cp1251")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].section == "Заголовок"
        assert result.segments[0].text == "Тело"


class TestMissingFile:
    def test_missing_file_returns_none(self, extractor: MarkdownExtractor, caplog):
        with caplog.at_level(logging.WARNING, logger="agent"):
            result = extractor.extract(Path("/nonexistent/file.md"))

        assert result is None
        assert "nonexistent" in caplog.text


class TestMultipleSpacesNormalized:
    def test_spaces_collapsed(self, extractor: MarkdownExtractor, tmp_path: Path):
        md = tmp_path / "test.md"
        md.write_text("# H\na   b", encoding="utf-8")

        result = extractor.extract(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].text == "a b"
