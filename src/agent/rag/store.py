"""Vector store for RAG chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from src.agent.rag.chunker import Chunk
from src.agent.rag.bm25 import BM25Index

if TYPE_CHECKING:
    pass


class VectorStore:
    """Store chunk embeddings and support cosine-like search."""

    def __init__(self, vectors: np.ndarray, chunks: list[Chunk], meta: dict) -> None:
        self.vectors = vectors
        self.chunks = chunks
        self.meta = meta
        self._bm25: BM25Index | None = None

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)

        np.save(directory / "vectors.npy", self.vectors)

        (directory / "chunks.json").write_text(
            json.dumps(
                [
                    {
                        "text": c.text,
                        "path": str(c.path),
                        "section": c.section,
                        "chunk_index": c.chunk_index,
                    }
                    for c in self.chunks
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        (directory / "meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> VectorStore:
        vectors_path = directory / "vectors.npy"

        if not vectors_path.exists():
            raise FileNotFoundError(
                f"index not found at {directory}, run scripts/build_index.py first"
            )

        vectors = np.load(vectors_path)

        chunks_data = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
        chunks: list[Chunk] = [
            Chunk(
                text=c["text"],
                path=Path(c["path"]),
                section=c["section"],
                chunk_index=c["chunk_index"],
            )
            for c in chunks_data
        ]

        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))

        store = cls(vectors=vectors, chunks=chunks, meta=meta)
        # BM25 строится из chunks, на диск не сохраняется
        store._bm25 = BM25Index(chunks)
        return store

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[Chunk, float]]:
        scores = self.vectors @ query_vector
        top = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top]

    def _ensure_bm25(self) -> BM25Index:
        if self._bm25 is None:
            self._bm25 = BM25Index(self.chunks)
        return self._bm25

    def search_hybrid(
        self,
        query_text: str,
        query_vector,
        top_k: int = 5,
        candidate_k: int = 20,
        rrf_k: int = 60,
    ) -> list[tuple[Chunk, float]]:
        """Гибридный поиск: BM25 + векторный через RRF.

        Args:
            query_text: запрос в текстовом виде (для BM25).
            query_vector: вектор запроса (для cosine).
            top_k: сколько результатов вернуть.
            candidate_k: сколько кандидатов от каждого поиска до RRF.
            rrf_k: константа RRF (по умолчанию 60).

        Returns:
            Список (chunk, rrf_score), отсортированный по убыванию.
        """
        if not query_text.strip():
            return []
        vector_results = self.search(query_vector, top_k=candidate_k)
        bm25_results = self._ensure_bm25().search(
            query_text, top_k=candidate_k
        )

        # Ключ чанка: (path, chunk_index) — уникален в индексе
        rrf: dict[tuple[str, int], float] = {}
        chunk_by_key: dict[tuple[str, int], Chunk] = {}

        for rank, (chunk, _score) in enumerate(vector_results, start=1):
            key = (str(chunk.path), chunk.chunk_index)
            chunk_by_key[key] = chunk
            rrf[key] = rrf.get(key, 0.0) + 1.0 / (rrf_k + rank)

        for rank, (chunk, _score) in enumerate(bm25_results, start=1):
            key = (str(chunk.path), chunk.chunk_index)
            chunk_by_key[key] = chunk
            rrf[key] = rrf.get(key, 0.0) + 1.0 / (rrf_k + rank)

        sorted_keys = sorted(rrf.keys(), key=lambda k: rrf[k], reverse=True)
        return [
            (chunk_by_key[k], rrf[k]) for k in sorted_keys[:top_k]
        ]
    
    def __len__(self) -> int:
        return len(self.chunks)
