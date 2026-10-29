"""Tests for PdfExtractor."""

from pathlib import Path

import pymupdf
import pytest

from src.agent.extractors.base import ExtractedDocument
from src.agent.extractors.pdf import PdfExtractor


@pytest.fixture()
def extractor() -> PdfExtractor:
    return PdfExtractor()


@pytest.fixture()
def make_pdf(tmp_path: Path):
    """Фабрика PDF с текстовыми страницами через insert_htmlbox.

    insert_htmlbox использует Story engine и автоматически подтягивает
    системный шрифт с кириллицей (Arial на Windows, DejaVu на Linux).
    insert_text с дефолтным helv кириллицу не поддерживает.
    """

    def _make_pdf(pages: list[str]) -> Path:
        doc = pymupdf.open()
        for text in pages:
            page = doc.new_page()
            page.insert_htmlbox(
                pymupdf.Rect(50, 50, 550, 750),
                f"<p>{text}</p>",
            )
        pdf_path = tmp_path / f"test_{len(pages)}pages.pdf"
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    return _make_pdf


class TestSupportedSuffixes:
    def test_returns_pdf(self, extractor: PdfExtractor):
        assert extractor.supported_suffixes() == {".pdf"}


class TestSinglePage:
    def test_one_segment_with_page_section(
        self, extractor: PdfExtractor, make_pdf
    ):
        pdf_path = make_pdf(["Привет мир"])

        result = extractor.extract(pdf_path)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 1
        assert result.segments[0].section == "Страница 1"
        assert "Привет" in result.segments[0].text


class TestMultiplePages:
    def test_three_pages_three_segments(
        self, extractor: PdfExtractor, make_pdf
    ):
        pdf_path = make_pdf(["Первая", "Вторая", "Третья"])

        result = extractor.extract(pdf_path)

        assert isinstance(result, ExtractedDocument)
        assert len(result.segments) == 3
        assert result.segments[0].section == "Страница 1"
        assert result.segments[1].section == "Страница 2"
        assert result.segments[2].section == "Страница 3"


class TestCyrillicPreserved:
    def test_cyrillic_text_not_corrupted(
        self, extractor: PdfExtractor, make_pdf
    ):
        pdf_path = make_pdf(["Требования к оперативной памяти"])

        result = extractor.extract(pdf_path)

        assert isinstance(result, ExtractedDocument)
        assert "Требования к оперативной памяти" in result.segments[0].text


class TestEmptyPagePdf:
    def test_pdf_with_single_empty_page_returns_no_segments(
        self, extractor: PdfExtractor, tmp_path: Path
    ):
        """PDF не бывает без страниц, но страница без текста — бывает.

        PyMuPDF не позволяет сохранить документ с 0 страниц
        (ValueError: cannot save with zero pages). Одна пустая
        страница — минимальный реалистичный случай.
        """
        doc = pymupdf.open()
        doc.new_page()  # пустая страница без текста
        pdf_path = tmp_path / "empty_page.pdf"
        doc.save(pdf_path)
        doc.close()

        result = extractor.extract(pdf_path)

        assert isinstance(result, ExtractedDocument)
        assert result.segments == []
        assert result.metadata["pages"] == 1


class TestImageOnlyPageSkipped:
    def test_rectangle_page_produces_no_segments(
        self, extractor: PdfExtractor, tmp_path: Path
    ):
        """Страница с графикой (без текстового слоя) — пропускается."""
        doc = pymupdf.open()
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(50, 50, 200, 200))
        pdf_path = tmp_path / "image_only.pdf"
        doc.save(pdf_path)
        doc.close()

        result = extractor.extract(pdf_path)

        assert isinstance(result, ExtractedDocument)
        assert result.segments == []
        assert result.metadata["pages"] == 1


class TestNonexistentFile:
    def test_returns_none_and_logs_warning(
        self, extractor: PdfExtractor, tmp_path: Path, caplog
    ):
        missing = tmp_path / "does_not_exist.pdf"

        with caplog.at_level("WARNING", logger="agent"):
            result = extractor.extract(missing)

        assert result is None
        assert "Failed to extract" in caplog.text or "pdf" in caplog.text.lower()


class TestBrokenPdf:
    def test_corrupted_file_returns_none_and_logs_warning(
        self, extractor: PdfExtractor, tmp_path: Path, caplog
    ):
        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"not a pdf at all")

        with caplog.at_level("WARNING", logger="agent"):
            result = extractor.extract(broken)

        assert result is None
        assert caplog.text  # warning был


class TestDocumentClosedAfterExtract:
    def test_file_can_be_deleted_after_extract(
        self, extractor: PdfExtractor, make_pdf
    ):
        """На Windows незакрытый PyMuPDF-документ блокирует файл.

        try/finally с doc.close() в PdfExtractor должен снимать блокировку.
        """
        pdf_path = make_pdf(["Тест"])

        extractor.extract(pdf_path)
        pdf_path.unlink()  # не должно бросить PermissionError


class TestMakePdfFixture:
    """Проверка, что фикстура сама создаёт валидный PDF."""

    def test_make_pdf_works(self, make_pdf):
        pdf_path = make_pdf(["Hello"])
        assert pdf_path.exists()
        doc = pymupdf.open(pdf_path)
        assert len(doc) == 1
        doc.close()