"""Семантический поиск по корпусу документов (RAG)."""

from __future__ import annotations

import logging

from src.agent.config import load_config
from src.agent.registry import ToolDefinition
from src.agent.rag.chunker import Chunk
from src.agent.rag.embedder import Embedder
from src.agent.rag.store import VectorStore

logger = logging.getLogger("agent")

_rag_service: tuple[VectorStore, Embedder] | None = None


def _get_rag_service() -> tuple[VectorStore, Embedder]:
    """Ленивая загрузка индекса и модели эмбеддингов.

    Один раз на процесс: при первом вызове читает config, грузит
    VectorStore из config.paths.index_dir и создаёт Embedder.
    """
    global _rag_service
    if _rag_service is None:
        config = load_config()
        store = VectorStore.load(config.paths.index_dir)
        embedder = Embedder(config.rag.embedding_model)
        logger.info(
            "RAG service loaded: %d chunks, model=%s",
            len(store),
            config.rag.embedding_model,
        )
        _rag_service = (store, embedder)
    return _rag_service


def _reset_rag_service() -> None:
    """Сбросить закэшированный сервис. Для тестов."""
    global _rag_service
    _rag_service = None


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

    store, embedder = _get_rag_service()
    query_vec = embedder.embed_one(query)
    results = store.search(query_vec, top_k=top_k)

    return [
        {
            "path": str(chunk.path),
            "section": chunk.section,
            "text": chunk.text,
            "score": round(float(score), 4),
        }
        for chunk, score in results
    ]


SEARCH_DOCUMENTS_TOOL: ToolDefinition = ToolDefinition(
    name="search_documents",
    description=(
        "Search INSIDE the user's documents (Markdown, TXT, later PDF/DOCX) "
        "for semantically relevant fragments. Use when the user asks what is "
        "written in their documents, files, corpus, knowledge base, or asks "
        "for facts from their documents: \"что в документах\", "
        "\"найди в документах\", \"что написано в файлах\", "
        "\"search my documents\", \"find in docs\". Returns top matching "
        "fragments with source path, section and relevance score. "
        "Do NOT use for personal notes — use search_notes for that."
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
                "description": "Maximum number of fragments to return. Default 5.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    func=search_documents,
)