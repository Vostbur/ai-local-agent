"""Тесты HtmlExtractor после исправления T43."""
from __future__ import annotations

import logging
from pathlib import Path

from src.agent.extractors import EXTRACTORS
from src.agent.extractors.html import HtmlExtractor

SAMPLE = """<html><head><title>Тестовая страница</title>
<style>p { color: red; }</style></head>
<body>
<p>Вступление без заголовка.</p>
<h1>Раздел один</h1>
<p>Текст раздела один.</p>
<ul><li>Пункт один</li></ul>
<script>var x = 1;</script>
</body></html>"""


def _write(tmp_path: Path, name: str = "page.html") -> Path:
    path = tmp_path / name
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_supported_suffixes():
    assert HtmlExtractor().supported_suffixes() == {".html", ".htm"}


def test_registered_in_registry():
    assert isinstance(EXTRACTORS[".html"], HtmlExtractor)
    assert isinstance(EXTRACTORS[".htm"], HtmlExtractor)


def test_no_legacy_import_prefix():
    """Регресс-страх граблей импортов: префикс только src.agent (T43)."""
    import src.agent.extractors.html as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from agent." not in src
    assert "import agent." not in src


def test_extract_sections_follow_headings(tmp_path):
    doc = HtmlExtractor().extract(_write(tmp_path))

    assert doc is not None
    assert [(s.section, s.text) for s in doc.segments] == [
        (None, "Вступление без заголовка."),
        ("Раздел один", "Раздел один"),
        ("Раздел один", "Текст раздела один."),
        ("Раздел один", "Пункт один"),
    ]
    assert doc.metadata == {"format": "html", "title": "Тестовая страница"}


def test_extract_drops_script_and_style(tmp_path):
    doc = HtmlExtractor().extract(_write(tmp_path))

    assert doc is not None
    joined = " ".join(s.text for s in doc.segments)
    assert "var x" not in joined
    assert "color: red" not in joined


def test_extract_broken_file_returns_none_with_warning(tmp_path, caplog):
    bad = tmp_path / "broken.html"
    bad.write_bytes(b"\xff\xfe\x00bad bytes")

    with caplog.at_level(logging.WARNING, logger="agent"):
        result = HtmlExtractor().extract(bad)

    assert result is None
    assert any("Failed to read HTML" in rec.message for rec in caplog.records)


def test_extract_missing_file_returns_none(tmp_path):
    assert HtmlExtractor().extract(tmp_path / "nope.html") is None