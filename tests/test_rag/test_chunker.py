"""Tests for the text chunking module."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.agent.extractors.base import ExtractedDocument, Segment
from src.agent.rag.chunker import Chunk, chunk_document, split_text


class TestSplitTextShort:
    def test_short_text_one_chunk(self):
        result = split_text("короткий текст", chunk_size=800, overlap=100)

        assert result == ["короткий текст"]
        assert len(result) == 1

    def test_exact_size_one_chunk(self):
        text = "a" * 800
        result = split_text(text, chunk_size=800, overlap=100)

        assert len(result) == 1
        assert result[0] == text

    def test_one_over_char_over_size(self):
        text = "a" * 801
        result = split_text(text, chunk_size=800, overlap=100)

        assert len(result) >= 2


class TestSplitTextLong:
    def test_long_text_multiple_chunks(self):
        text = "x" * 2000
        result = split_text(text, chunk_size=800, overlap=100)

        assert len(result) >= 3
        for chunk in result:
            assert len(chunk) <= 800

    def test_chunks_overlap(self):
        # Create text with a distinctive repeated marker
        marker = "UNIQUE_MARKER_42"
        # Build text: first 800 chars, then overlap region with marker, then rest
        prefix = "A" * 700
        middle = marker * 5  # "UNIQUE_MARKER_42" * 5
        suffix = "B" * 700
        text = prefix + middle + suffix

        result = split_text(text, chunk_size=800, overlap=100)

        # At least some adjacent chunks should share content
        for i in range(len(result) - 1):
            chunk_a = result[i]
            chunk_b = result[i + 1]
            # Check that some overlap exists: suffix of chunk_a appears in chunk_b
            # or prefix of chunk_b appears in chunk_a
            suffix_len = min(50, len(chunk_a))
            chunk_suffix = chunk_a[-suffix_len:]
            assert (
                chunk_suffix in chunk_b or chunk_suffix in chunk_a
            ), f"Chunks {i} and {i+1} should have overlapping content"

    def test_break_at_sentence_boundary(self):
        text = (
            "First sentence here. "
            + "A" * 700
            + ". "
            + "B" * 500
        )
        result = split_text(text, chunk_size=800, overlap=100)

        # At least one chunk should end near a sentence boundary
        ends_with_period = any(chunk.rstrip().endswith(".") for chunk in result)
        assert ends_with_period, "At least one chunk should end at a sentence boundary"

    def test_no_empty_chunks(self):
        text = "A" * 2000 + "   " + "B" * 2000
        result = split_text(text, chunk_size=800, overlap=100)

        for chunk in result:
            assert chunk != ""
            assert chunk.strip() != ""


class TestChunkDocument:
    @pytest.fixture
    def sample_doc(self, tmp_path: Path):
        """Create an ExtractedDocument with two segments."""
        doc_path = tmp_path / "sample.md"
        doc_path.write_text("Intro and Body text", encoding="utf-8")

        return ExtractedDocument(
            path=doc_path,
            segments=[
                Segment(text="Intro paragraph with some text to make it longer for chunking purposes.", section="Intro"),
                Segment(text="Body paragraph with additional content for testing chunk boundaries and overlap behavior in documents.", section="Body"),
            ],
            metadata={"source": "test"},
        )

    def test_chunk_document_preserves_section(self, sample_doc: ExtractedDocument):
        result = chunk_document(sample_doc, chunk_size=800, overlap=100)

        sections_found = {chunk.section for chunk in result}
        assert "Intro" in sections_found
        assert "Body" in sections_found

    def test_chunk_document_sequential_index(self, sample_doc: ExtractedDocument):
        result = chunk_document(sample_doc, chunk_size=800, overlap=100)

        indices = [chunk.chunk_index for chunk in result]
        expected = list(range(len(result)))
        assert indices == expected

    def test_chunk_document_empty_segments(self, tmp_path: Path):
        doc_path = tmp_path / "empty.md"
        doc_path.write_text("", encoding="utf-8")

        doc = ExtractedDocument(
            path=doc_path,
            segments=[],
            metadata={"source": "test"},
        )

        result = chunk_document(doc, chunk_size=800, overlap=100)

        assert result == []

    def test_chunk_document_preserves_path(self, sample_doc: ExtractedDocument):
        result = chunk_document(sample_doc, chunk_size=800, overlap=100)

        for chunk in result:
            assert chunk.path == sample_doc.path

    def test_chunk_document_no_empty_chunks(self, sample_doc: ExtractedDocument):
        result = chunk_document(sample_doc, chunk_size=800, overlap=100)

        for chunk in result:
            assert chunk.text.strip() != ""


class TestEmbedderMock:
    def test_embedder_embed_mocked(self, monkeypatch: pytest.MonkeyPatch):
        import numpy as np

        class FakeST:
            def __init__(self, *args, **kwargs):
                pass

            def encode(self, texts, **kwargs):
                return np.array(
                    [[1.0, 2.0] for _ in texts], dtype=np.float32
                )

        monkeypatch.setattr(
            "src.agent.rag.embedder.SentenceTransformer", FakeST
        )

        from src.agent.rag.embedder import Embedder

        embedder = Embedder("mock-model")
        assert embedder._model is None

        vectors = embedder.embed(["hello", "world"])

        assert embedder._model is not None
        assert vectors.shape == (2, 2)
        assert vectors.dtype == np.float32

    def test_embed_empty_returns_empty(self):
        import numpy as np
        from src.agent.rag.embedder import Embedder

        embedder = Embedder("mock-model")
        result = embedder.embed([])

        assert result.shape == (0, 0)
        assert embedder._model is None

    def test_embed_one_returns_1d(self, monkeypatch: pytest.MonkeyPatch):
        import numpy as np

        class FakeST:
            def __init__(self, *args, **kwargs):
                pass

            def encode(self, texts, **kwargs):
                return np.array(
                    [[1.0, 2.0, 3.0] for _ in texts], dtype=np.float32
                )

        monkeypatch.setattr(
            "src.agent.rag.embedder.SentenceTransformer", FakeST
        )

        from src.agent.rag.embedder import Embedder

        v = Embedder("m").embed_one("x")

        assert v.shape == (3,)