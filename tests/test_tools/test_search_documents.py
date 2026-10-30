"""Tests for search_documents tool (factory-based)."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.agent.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    RAGConfig,
    SafetyConfig,
)
from src.agent.rag.chunker import Chunk
from src.agent.tools.search_documents import make_search_documents_tool


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        llm=LLMConfig(model="test-model"),
        paths=PathsConfig(
            data_dir=tmp_path / "data",
            notes_dir=tmp_path / "data" / "notes",
            inbox_dir=tmp_path / "data" / "inbox",
            photos_dir=tmp_path / "data" / "photos",
            documents_dir=tmp_path / "data" / "documents",
            logs_dir=tmp_path / "logs",
            generated_dir=tmp_path / "data" / "generated",
            index_dir=tmp_path / "data" / "index",
        ),
        safety=SafetyConfig(),
        rag=RAGConfig(),
    )


@pytest.fixture()
def patched_rag(monkeypatch):
    """Подменить VectorStore.load и Embedder: не грузить модель."""
    mock_store = MagicMock()
    mock_store.__len__ = MagicMock(return_value=3)
    mock_store.search_hybrid = MagicMock(
        return_value=[
            (
                Chunk(
                    text="some text",
                    path=Path("a.md"),
                    section="Intro",
                    chunk_index=0,
                ),
                0.82,
            ),
        ]
    )

    mock_embedder = MagicMock()
    mock_embedder.embed_one = MagicMock(
        return_value=np.zeros(384, dtype=np.float32)
    )

    monkeypatch.setattr(
        "src.agent.tools.search_documents.VectorStore.load",
        MagicMock(return_value=mock_store),
    )
    monkeypatch.setattr(
        "src.agent.tools.search_documents.Embedder",
        MagicMock(return_value=mock_embedder),
    )
    return mock_store, mock_embedder


class TestSearchDocumentsTool:
    def test_returns_list_of_dicts(self, tmp_path, patched_rag):
        tool = make_search_documents_tool(_make_config(tmp_path))
        result = tool.func("query")

        assert isinstance(result, list)
        assert len(result) == 1
        assert set(result[0].keys()) == {"path", "section", "text", "score"}

    def test_passes_top_k_to_store(self, tmp_path, patched_rag):
        mock_store, _ = patched_rag
        tool = make_search_documents_tool(_make_config(tmp_path))
        tool.func("query", top_k=3)

        assert mock_store.search_hybrid.call_args.kwargs["top_k"] == 3

    def test_calls_embedder_with_query(self, tmp_path, patched_rag):
        _, mock_embedder = patched_rag
        tool = make_search_documents_tool(_make_config(tmp_path))
        tool.func("test query")

        mock_embedder.embed_one.assert_called_once_with("test query")

    def test_empty_query_returns_empty_no_load(
        self, tmp_path, monkeypatch
    ):
        """Пустой query → [] без загрузки store/embedder."""
        load_mock = MagicMock()
        monkeypatch.setattr(
            "src.agent.tools.search_documents.VectorStore.load", load_mock
        )

        tool = make_search_documents_tool(_make_config(tmp_path))
        result = tool.func("")

        assert result == []
        load_mock.assert_not_called()

    def test_lazy_load_only_once(self, tmp_path, monkeypatch):
        """Store загружается только при первом непустом вызове, потом кэш."""
        load_mock = MagicMock(
            return_value=MagicMock(
                search_hybrid=MagicMock(return_value=[]),
                __len__=MagicMock(return_value=0),
            )
        )
        monkeypatch.setattr(
            "src.agent.tools.search_documents.VectorStore.load", load_mock
        )
        monkeypatch.setattr(
            "src.agent.tools.search_documents.Embedder",
            MagicMock(
                return_value=MagicMock(
                    embed_one=MagicMock(return_value=np.zeros(384)),
                )
            ),
        )

        tool = make_search_documents_tool(_make_config(tmp_path))
        assert load_mock.call_count == 0

        tool.func("query")
        assert load_mock.call_count == 1

        tool.func("another")
        assert load_mock.call_count == 1

    def test_description_mentions_documents_and_not_notes(self, tmp_path):
        tool = make_search_documents_tool(_make_config(tmp_path))
        desc = tool.description

        assert "DOCUMENTS" in desc
        assert "README" in desc
        assert "NOT personal notes" in desc
        assert "search_notes" in desc
        assert "установка" in desc
        assert "версия Python" in desc

    def test_factory_produces_independent_tools(self, tmp_path):
        """Две фабрики — два независимых контекста (нет глобального state)."""
        cfg = _make_config(tmp_path)
        tool1 = make_search_documents_tool(cfg)
        tool2 = make_search_documents_tool(cfg)

        assert tool1 is not tool2
        assert tool1.func is not tool2.func
        assert tool1.name == tool2.name == "search_documents"