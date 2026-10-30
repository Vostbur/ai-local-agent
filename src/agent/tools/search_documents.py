"""Семантический поиск по корпусу документов (RAG)."""

from __future__ import annotations

import logging
from pathlib import Path

from src.agent.config import AppConfig
from src.agent.registry import ToolDefinition
from src.agent.rag.embedder import Embedder
from src.agent.rag.store import VectorStore

logger = logging.getLogger("agent")


class _RagContext:
    """Лениво загружаемый контекст RAG: VectorStore + Embedder.

    Создаётся фабрикой `make_search_documents_tool(config)` и живёт
    в замыкании возвращаемой функции. Никакого глобального состояния —
    два вызова фабрики дают два независимых контекста.
    """

    def __init__(self, index_dir: Path, embedding_model: str) -> None:
        self._index_dir = index_dir
        self._embedding_model = embedding_model
        self._store: VectorStore | None = None
        self._embedder: Embedder | None = None

    def _ensure_loaded(self) -> None:
        if self._store is None:
            self._store = VectorStore.load(self._index_dir)
            logger.info(
                "RAG store loaded: %d chunks from %s",
                len(self._store),
                self._index_dir,
            )
        if self._embedder is None:
            self._embedder = Embedder(self._embedding_model)

    @property
    def store(self) -> VectorStore:
        self._ensure_loaded()
        assert self._store is not None
        return self._store

    @property
    def embedder(self) -> Embedder:
        self._ensure_loaded()
        assert self._embedder is not None
        return self._embedder


def make_search_documents_tool(config: AppConfig) -> ToolDefinition:
    """Фабрика search_documents с контекстом из config (без глобального состояния).

    Args:
        config: Конфигурация приложения. Используются
            `paths.index_dir` и `rag.embedding_model`.

    Returns:
        ToolDefinition с именем `search_documents` и функцией,
        захватившей `_RagContext` в замыкании.
    """
    ctx = _RagContext(config.paths.index_dir, config.rag.embedding_model)

    def search_documents(query: str, top_k: int = 5) -> list[dict]:
        """Найти семантически релевантные фрагменты в корпусе документов.

        Args:
            query: Вопрос или ключевые слова на естественном языке.
            top_k: Максимальное число фрагментов.

        Returns:
            Список словарей: ``path``, ``section``, ``text``, ``score``.
        """
        if not query.strip():
            return []

        query_vec = ctx.embedder.embed_one(query)
        results = ctx.store.search_hybrid(query, query_vec, top_k=top_k)

        return [
            {
                "path": str(chunk.path),
                "section": chunk.section,
                "text": chunk.text,
                "score": round(float(score), 4),
            }
            for chunk, score in results
        ]

    return ToolDefinition(
        name="search_documents",
        description=(
            "Search the user's DOCUMENTS (README, articles, project files, "
            "knowledge base) — NOT personal notes. ALWAYS use when the user "
            "asks about: требования, установка, запуск, что умеет проект, "
            "возможности, лицензия, статьи, документация, README, исходный код, "
            "версия Python, файлы проекта. Returns matching fragments with "
            "source path, section and relevance score. "
            "For personal notes, use search_notes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language question or keywords. "
                        "Works semantically, not by exact substring."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": (
                        "Maximum number of fragments to return. Default 5."
                    ),
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        func=search_documents,
    )