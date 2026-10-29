"""Vector store for RAG chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from src.agent.rag.chunker import Chunk

if TYPE_CHECKING:
    pass


class VectorStore:
    """Store chunk embeddings and support cosine-like search."""

    def __init__(self, vectors: np.ndarray, chunks: list[Chunk], meta: dict) -> None:
        self.vectors = vectors
        self.chunks = chunks
        self.meta = meta

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

        return cls(vectors=vectors, chunks=chunks, meta=meta)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[Chunk, float]]:
        scores = self.vectors @ query_vector
        top = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top]

    def __len__(self) -> int:
        return len(self.chunks)
