import pytest
from pathlib import Path
from docx import Document as DocxDocument
from agent.extractors.docx import DocxExtractor
from agent.extractors.html import HtmlExtractor


class TestDocxExtractor:
    def test_extracts_paragraphs(self, tmp_path):
        doc = DocxDocument()
        doc.add_heading("Заголовок", level=1)
        doc.add_paragraph("Первый абзац текста.")
        doc.add_paragraph("Второй абзац текста.")
        
        file_path = tmp_path / "test.docx"
        doc.save(file_path)
        
        extractor = DocxExtractor()
        result = extractor.extract(file_path)
        
        assert result is not None
        assert len(result.segments) >= 2
        assert any("Первый абзац" in seg.text for seg in result.segments)
        assert result.metadata.get("format") == "docx"

    def test_handles_empty_docx(self, tmp_path):
        doc = DocxDocument()
        file_path = tmp_path / "empty.docx"
        doc.save(file_path)
        
        extractor = DocxExtractor()
        result = extractor.extract(file_path)
        
        assert result is not None
        assert len(result.segments) == 0

    def test_returns_none_for_broken_file(self, tmp_path):
        file_path = tmp_path / "broken.docx"
        file_path.write_text("not a real docx file")
        
        extractor = DocxExtractor()
        result = extractor.extract(file_path)
        
        assert result is None


class TestHtmlExtractor:
    def test_extracts_text_and_metadata(self, tmp_path):
        html = """
        <html>
          <head><title>Мой заголовок</title></head>
          <body>
            <h1>Раздел</h1>
            <p>Текст параграфа.</p>
            <script>console.log('script to ignore');</script>
          </body>
        </html>
        """
        file_path = tmp_path / "test.html"
        file_path.write_text(html, encoding="utf-8")
        
        extractor = HtmlExtractor()
        result = extractor.extract(file_path)
        
        assert result is not None
        assert result.metadata.get("title") == "Мой заголовок"
        assert any("Раздел" in seg.text for seg in result.segments)
        assert any("Текст параграфа" in seg.text for seg in result.segments)
        assert not any("script to ignore" in seg.text for seg in result.segments)

    def test_handles_html_without_title(self, tmp_path):
        html = "<html><body><p>Просто текст.</p></body></html>"
        file_path = tmp_path / "no_title.html"
        file_path.write_text(html, encoding="utf-8")
        
        extractor = HtmlExtractor()
        result = extractor.extract(file_path)
        
        assert result is not None
        assert result.metadata.get("title") == ""
        assert len(result.segments) > 0