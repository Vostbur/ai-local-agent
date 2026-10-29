"""Tests for the BM25 lexical search module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.rag.bm25 import BM25Index, _tokenize
from src.agent.rag.chunker import Chunk


def _chunk(text: str, section: str | None = None, path: str = "doc.md") -> Chunk:
    return Chunk(text=text, path=Path(path), section=section, chunk_index=0)


class TestSingleTermInOneChunk:
    def test_single_term_in_one_chunk(self) -> None:
        chunks = [
            _chunk("здесь есть особый термин"),
            _chunk("не содержит этого слова"),
            _chunk("тоже не содержит"),
        ]
        index = BM25Index(chunks)
        results = index.search("особый", top_k=5)

        assert len(results) == 1
        assert results[0][0].text == "здесь есть особый термин"

    def test_term_not_present_returns_empty(self) -> None:
        chunks = [
            _chunk("один"),
            _chunk("два"),
            _chunk("три"),
        ]
        index = BM25Index(chunks)
        results = index.search("отсутствующий", top_k=5)

        assert results == []


class TestExactTermMatching:
    def test_exact_term_16_gb(self) -> None:
        chunks = [
            _chunk("система с 16 ГБ памяти"),
            _chunk("базовая модель с 3 ГБ памяти"),
            _chunk("промежуточная модель с 8 ГБ памяти"),
        ]
        index = BM25Index(chunks)
        results = index.search("16 ГБ", top_k=5)

        # «гб» есть во всех чанках, но «16» даёт чёткий отрыв
        assert len(results) >= 1
        assert results[0][0].text == "система с 16 ГБ памяти"
        if len(results) > 1:
            assert results[0][1] > results[1][1] * 3

    def test_different_term_3_gb(self) -> None:
        chunks = [
            _chunk("система с 16 ГБ памяти"),
            _chunk("базовая модель с 3 ГБ памяти"),
        ]
        index = BM25Index(chunks)
        results = index.search("3 ГБ", top_k=5)

        assert len(results) >= 1
        assert results[0][0].text == "базовая модель с 3 ГБ памяти"
        if len(results) > 1:
            assert results[0][1] > results[1][1] * 3


class TestSectionPrefixMatching:
    """Чанк с section="Требования" находится запросом через _chunk_text."""

    def test_requirement_matches_section_header(self) -> None:
        chunks = [
            _chunk("должно быть не менее 8 ГБ", section="Требования"),
            _chunk("документ описывает архитектуру", section="Введение"),
        ]
        index = BM25Index(chunks)
        results = index.search("требования к памяти", top_k=5)

        # section="Требования" + текст = "Требования. должно быть..."
        # токен "требования" должен найтись
        assert len(results) >= 1
        assert results[0][0].section == "Требования"


class TestTokenize:
    """Функция _tokenize."""

    def test_tokenize_handles_cyrillic_and_latin(self) -> None:
        result = _tokenize("Привет World 123!")
        assert result == ["привет", "world", "123"]

    def test_tokenize_strips_punctuation(self) -> None:
        result = _tokenize("a,b;c!d?")
        assert result == ["a", "b", "c", "d"]


class TestIDFRareTerm:
    """Редкий термин (в 1 из 5 чанков) даёт больший score, чем частый (в 4 из 5)."""

    def test_idf_rare_term_scores_higher(self) -> None:
        # Термин "x" только в чанке 0 (df=1), термин "y" в 4 чанках (df=4)
        chunks = [
            _chunk("x y y y y"),
            _chunk("y y y y"),
            _chunk("y y y y"),
            _chunk("y y y y"),
            _chunk("y y y y"),
        ]
        index = BM25Index(chunks)

        results_x = index.search("x", top_k=5)
        results_y = index.search("y", top_k=5)

        # score от редкого термина должен быть больше
        assert results_x[0][1] > results_y[0][1]


class TestEmptyInputs:
    """Пустые запросы и пустые чанки."""

    def test_empty_query_returns_empty(self) -> None:
        chunks = [
            _chunk("какой-то текст"),
            _chunk("другой текст"),
        ]
        index = BM25Index(chunks)
        results = index.search("")

        assert results == []

    def test_empty_chunks_returns_empty(self) -> None:
        index = BM25Index([])
        results = index.search("x")

        assert results == []
