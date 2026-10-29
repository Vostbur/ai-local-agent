"""End-to-end tests for extract_text across formats."""

import logging
from pathlib import Path

from src.agent.extractors import extract_text
from src.agent.extractors.base import ExtractedDocument


class TestExtractTextMdEndToEnd:
    def test_full_pipeline(self, tmp_path: Path, caplog):
        md = tmp_path / "readme.md"
        md.write_text(
            "# Project\n\n"
            "Intro paragraph.\n\n"
            "## Installation\n\n"
            "Run `pip install foo` to install.\n\n"
            "```python\n"
            "import foo\n"
            "print('hello')\n"
            "```\n\n"
            "## Usage\n\n"
            "See [docs](https://example.com/docs) for details.\n\n"
            "<div>hidden</div>\n\n"
            "## Conclusion\n\n"
            "That's it.",
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING, logger="agent"):
            result = extract_text(md)

        assert isinstance(result, ExtractedDocument)
        assert result.path == md
        # 4 сегмента: Project, Installation, Usage, Conclusion
        assert len(result.segments) == 4

        assert result.segments[0].section == "Project"
        assert "Intro paragraph" in result.segments[0].text

        # Installation: fenced code вырезан, inline code тоже вырезан
        assert result.segments[1].section == "Installation"
        assert "import foo" not in result.segments[1].text
        assert "print" not in result.segments[1].text
        assert "pip install foo" not in result.segments[1].text
        assert "Run" in result.segments[1].text
        assert "to install" in result.segments[1].text

        # Usage: URL ссылки вырезан, текст ссылки остался, HTML-теги вырезаны, текст остался
        assert result.segments[2].section == "Usage"
        assert "https://example.com" not in result.segments[2].text
        assert "docs" in result.segments[2].text
        assert "<div>" not in result.segments[2].text
        assert "hidden" in result.segments[2].text

        assert result.segments[3].section == "Conclusion"

    def test_with_preamble(self, tmp_path: Path):
        md = tmp_path / "readme.md"
        md.write_text(
            "Intro paragraph before any heading.\n\n"
            "# Project\n\n"
            "Body under Project.",
            encoding="utf-8",
        )

        result = extract_text(md)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 2
        assert result.segments[0].section is None
        assert "Intro paragraph" in result.segments[0].text
        assert result.segments[1].section == "Project"


class TestExtractTextTxtEndToEnd:
    def test_full_pipeline(self, tmp_path: Path):
        txt = tmp_path / "note.txt"
        txt.write_text("Просто текст.\n\nС абзацами.", encoding="utf-8")

        result = extract_text(txt)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].section is None
        assert "Просто текст" in result.segments[0].text

    def test_empty_txt_returns_empty_segments(self, tmp_path: Path):
        txt = tmp_path / "empty.txt"
        txt.write_text("", encoding="utf-8")

        result = extract_text(txt)

        assert isinstance(result, ExtractedDocument)
        assert result.segments == []

    def test_missing_txt_returns_none_and_warns(
        self, tmp_path: Path, caplog
    ):
        missing = tmp_path / "does_not_exist.txt"

        with caplog.at_level("WARNING", logger="agent"):
            result = extract_text(missing)

        assert result is None
        assert caplog.text  # warning был