"""Tests for the search_documents tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.agent.tools.search_documents import (
    SEARCH_DOCUMENTS_TOOL,
    _reset_rag_service,
    search_documents,
)
from src.agent.rag.chunker import Chunk


class TestSearchDocumentsUsesHybrid:
    """Проверка, что search_documents вызывает store.search_hybrid."""

    @pytest.fixture
    def mock_rag_service(self, monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
        """Замокать _get_rag_service с моковыми store и embedder."""
        mock_store = MagicMock()
        mock_embedder = MagicMock()

        mock_store.search_hybrid.return_value = [
            (
                Chunk(text="результат 1", path=Path("doc1.md"), section="Раздел", chunk_index=0),
                0.95,
            ),
            (
                Chunk(text="результат 2", path=Path("doc2.md"), section="Раздел", chunk_index=1),
                0.80,
            ),
        ]
        mock_embedder.embed_one.return_value = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        def fake_get_rag_service():
            return (mock_store, mock_embedder)

        monkeypatch.setattr(
            "src.agent.tools.search_documents._get_rag_service",
            fake_get_rag_service,
        )
        return mock_store, mock_embedder

    def test_search_documents_uses_hybrid(
        self,
        mock_rag_service: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """search_documents вызывает store.search_hybrid, а не store.search."""
        mock_store, mock_embedder = mock_rag_service

        result = search_documents("тестовый запрос", top_k=5)

        # search_hybrid вызван с query_text и query_vec
        mock_store.search_hybrid.assert_called_once()
        call_args = mock_store.search_hybrid.call_args
        assert call_args[0][0] == "тестовый запрос"  # query_text
        assert isinstance(call_args[0][1], np.ndarray)  # query_vec

        # search НЕ должен вызываться напрямую
        mock_store.search.assert_not_called()

        # Результат содержит ожидаемые поля
        assert len(result) == 2
        assert result[0]["text"] == "результат 1"
        assert result[0]["score"] == 0.95
        assert result[1]["section"] == "Раздел"

    def test_search_documents_empty_query_returns_empty(
        self,
        mock_rag_service: tuple[MagicMock, MagicMock],
    ) -> None:
        """Пустой query → [] без вызова store."""
        mock_store, _ = mock_rag_service

        result = search_documents("", top_k=5)

        assert result == []
        mock_store.search_hybrid.assert_not_called()

    def test_search_documents_passes_top_k(
        self,
        mock_rag_service: tuple[MagicMock, MagicMock],
    ) -> None:
        """top_k передаётся в store.search_hybrid."""
        mock_store, _ = mock_rag_service

        search_documents("запрос", top_k=3)

        mock_store.search_hybrid.assert_called_once()
        call_args = mock_store.search_hybrid.call_args
        assert call_args[1]["top_k"] == 3  # keyword argument

def test_description_mentions_documents_and_not_notes():
    desc = SEARCH_DOCUMENTS_TOOL.description

    assert "DOCUMENTS" in desc
    assert "README" in desc
    assert "NOT personal notes" in desc
    assert "search_notes" in desc
    assert "установка" in desc
    assert "версия Python" in desc