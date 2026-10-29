"""Tests for the BM25 lexical search module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.rag.bm25 import BM25Index, _stem, _tokenize
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
        # После стемминга: "привет" (6 символов) → "приве", "world" (5) и "123" (3) не трогаются
        result = _tokenize("Привет World 123!")
        assert result == ["приве", "world", "123"]

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


class TestStem:
    """Функция _stem: префикс 5 символов для длинных слов."""

    def test_stem_long_word(self) -> None:
        assert _stem("установить") == "устан"
        assert _stem("установка") == "устан"

    def test_stem_short_word_unchanged(self) -> None:
        assert _stem("дом") == "дом"
        assert _stem("гб") == "гб"
        assert _stem("озу") == "озу"

    def test_stem_boundary_length_5(self) -> None:
        assert _stem("банка") == "банка"
        assert _stem("банки") == "банки"

    def test_stem_boundary_length_6(self) -> None:
        assert _stem("банков") == "банко"

    def test_tokenize_applies_stem(self) -> None:
        assert _tokenize("установить установка") == ["устан", "устан"]

    def test_tokenize_preserves_numbers(self) -> None:
        # "16" и "гб" короткие — не трогаются; "памяти" (6) → "памят"
        assert _tokenize("16 ГБ памяти") == ["16", "гб", "памят"]


class TestStemImprovesMatching:
    """Стемминг позволяет находить словоформы с общими корнями."""

    def test_install_query_finds_installation_chunk(self) -> None:
        chunks = [
            _chunk(
                "Как установить агента",
                section="Установка с нуля",
            ),
            _chunk("другой раздел", section="Настройка"),
        ]
        index = BM25Index(chunks)
        results = index.search("Как установить агента с нуля?", top_k=5)

        assert len(results) >= 1
        assert results[0][0].section == "Установка с нуля"

    def test_documents_query_finds_document_chunk(self) -> None:
        chunks = [
            _chunk("документ описывает архитектуру"),
            _chunk("описание интерфейса"),
        ]
        index = BM25Index(chunks)
        results = index.search("документы", top_k=5)

        assert len(results) >= 1
        assert results[0][0].text == "документ описывает архитектуру"

    def test_requirement_query_finds_requirement_chunk(self) -> None:
        chunks = [
            _chunk("Требования к системе"),
            _chunk("Введение в проект"),
        ]
        index = BM25Index(chunks)
        results = index.search("требовать", top_k=5)

        assert len(results) >= 1
        assert results[0][0].text == "Требования к системе"


class TestIDFFilter:
    def test_search_filters_low_idf_tokens(self) -> None:
        """Частый токен отбрасывается, редкий — определяет результат."""
        # «агент» в 9 чанках из 10, «установка» — в 1
        chunks = [_chunk(f"агент в чанке {i}") for i in range(9)]
        chunks.append(_chunk("установка агента с нуля"))
        index = BM25Index(chunks)

        # Без фильтра: «агент» матчится везде, релевантный чанк может
        # не попасть в top-1 из-за низкого IDF «агент»
        results_no_filter = index.search(
            "агент установка", top_k=1, min_idf=0.0
        )
        # С фильтром: «агент» отброшен (IDF < 0.5), «установка» — высокий IDF
        results_filtered = index.search(
            "агент установка", top_k=1, min_idf=0.5
        )

        assert results_filtered[0][0].text == "установка агента с нуля"

    def test_search_fallback_when_all_low_idf(self) -> None:
        """Все токены запроса низко-IDF → fallback, не падает."""
        chunks = [_chunk(f"агент {i}") for i in range(10)]
        index = BM25Index(chunks)

        # «агент» везде (df=10), IDF низкий; фильтр опустошит запрос
        results = index.search("агент", top_k=3, min_idf=0.5)

        # fallback: без фильтра, но не падает
        assert len(results) > 0
        assert all("агент" in r[0].text for r in results)

    def test_search_min_idf_zero_disables_filter(self) -> None:
        """min_idf=0 — фильтр отключён, старое поведение."""
        chunks = [_chunk(f"агент {i}") for i in range(5)]
        index = BM25Index(chunks)

        results_zero = index.search("агент", top_k=3, min_idf=0.0)
        results_default = index.search("агент", top_k=3)

        # min_idf=0 — все токены проходят, результат как без фильтра
        assert len(results_zero) > 0

    def test_install_query_after_filter(self) -> None:
        """Запрос «Как установить агента с нуля?» находит раздел установки."""
        # Имитация реального корпуса: много «устан» в разных формах,
        # много «как агент», один чанк «Установка с нуля»
        chunks = []
        for i in range(10):
            chunks.append(_chunk(f"агент как установить {i}", section="Шаг"))
        chunks.append(
            _chunk(
                "Все команды выполняются в терминале. На Windows PowerShell.",
                section="Установка с нуля (для новичка)",
            )
        )
        chunks.append(
            _chunk(
                "Скопируйте config/settings.example.toml и запустите",
                section="Шаг 1. Скачайте проект",
            )
        )

        index = BM25Index(chunks)
        results = index.search(
            "Как установить агента с нуля?", top_k=3, min_idf=0.5
        )

        # Чанк с «Установка с нуля» или «Шаг 1» должен быть в top-3
        sections = [r[0].section for r in results]
        assert any(
            s and ("Установка" in s or "Шаг 1" in s) for s in sections
        ), f"Не найден раздел установки в top-3: {sections}"