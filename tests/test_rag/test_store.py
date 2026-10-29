"""Tests for the vector store module."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.agent.rag.chunker import Chunk
from src.agent.rag.store import VectorStore


class TestSaveAndLoadRoundtrip:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        chunks = [
            Chunk(text="first chunk", path=Path("a.txt"), section="S1", chunk_index=0),
            Chunk(text="second chunk", path=Path("a.txt"), section="S1", chunk_index=1),
            Chunk(text="third chunk", path=Path("b.txt"), section="S2", chunk_index=2),
        ]
        vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)
        meta = {"embedding_model": "all-MiniLM-L6-v2", "num_chunks": 3}

        store = VectorStore(vectors=vectors, chunks=chunks, meta=meta)

        store.save(tmp_path)

        loaded = VectorStore.load(tmp_path)

        assert len(loaded) == 3
        for i in range(3):
            assert loaded.chunks[i].text == chunks[i].text
        np.testing.assert_array_equal(loaded.vectors, vectors)


class TestLoadMissing:
    def test_load_missing_raises(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            VectorStore.load(empty_dir)


class TestSearchReturnsTopK:
    def test_search_returns_top_k(self) -> None:
        chunks = [
            Chunk(text=f"chunk_{i}", path=Path("f.txt"), section=None, chunk_index=i)
            for i in range(5)
        ]
        # 5 vectors in 3-d space
        vectors = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.9, 0.1, 0.0],
                [0.1, 0.9, 0.0],
                [0.0, 0.0, 1.0],
                [0.5, 0.5, 0.0],
            ],
            dtype=np.float32,
        )
        store = VectorStore(vectors=vectors, chunks=chunks, meta={})

        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=2)

        assert len(results) == 2
        scores = [score for _, score in results]
        assert scores[0] >= scores[1]


class TestSearchReturnsChunksNotJustScores:
    def test_search_returns_chunks_not_just_scores(self) -> None:
        chunk = Chunk(text="hello", path=Path("x.txt"), section=None, chunk_index=0)
        vectors = np.array([[1.0, 0.0]], dtype=np.float32)
        store = VectorStore(vectors=vectors, chunks=[chunk], meta={})

        query = np.array([1.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=1)

        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert isinstance(item[0], Chunk)
        assert isinstance(item[1], float)
        assert item[0].text == "hello"


class TestSearchScoreIsCosine:
    def test_search_score_is_cosine(self) -> None:
        # With normalize_embeddings=True vectors are unit-length,
        # so cosine similarity == dot product.
        # search computes self.vectors @ query_vector which is dot product.
        v1 = np.array([[1.0, 0.0]], dtype=np.float32)
        v2 = np.array([[0.0, 1.0]], dtype=np.float32)

        # query = [1, 0]
        query = np.array([1.0, 0.0], dtype=np.float32)

        # dot([1,0], [1,0]) == 1.0
        store1 = VectorStore(vectors=v1, chunks=[Chunk(text="same", path=Path("p"), section=None, chunk_index=0)], meta={})
        result1 = store1.search(query, top_k=1)
        assert result1[0][1] == pytest.approx(1.0, abs=1e-6)

        # dot([0,1], [1,0]) == 0.0
        store2 = VectorStore(vectors=v2, chunks=[Chunk(text="orth", path=Path("p"), section=None, chunk_index=0)], meta={})
        result2 = store2.search(query, top_k=1)
        assert result2[0][1] == pytest.approx(0.0, abs=1e-6)


class TestMetaSavedAndLoaded:
    def test_meta_saved_and_loaded(self, tmp_path: Path) -> None:
        meta = {"embedding_model": "all-MiniLM-L6-v2", "num_chunks": 42}
        vectors = np.zeros((1, 3), dtype=np.float32)
        chunks = [Chunk(text="x", path=Path("f"), section=None, chunk_index=0)]

        store = VectorStore(vectors=vectors, chunks=chunks, meta=meta)
        store.save(tmp_path)

        loaded = VectorStore.load(tmp_path)
        assert loaded.meta["embedding_model"] == "all-MiniLM-L6-v2"
        assert loaded.meta["num_chunks"] == 42

        # Also verify meta.json on disk
        meta_disk = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta_disk["embedding_model"] == "all-MiniLM-L6-v2"
        assert meta_disk["num_chunks"] == 42


class TestSaveCreatesDirectory:
    def test_save_creates_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new_index"
        assert not new_dir.exists()

        vectors = np.zeros((1, 2), dtype=np.float32)
        chunks = [Chunk(text="hi", path=Path("f"), section=None, chunk_index=0)]
        store = VectorStore(vectors=vectors, chunks=chunks, meta={})

        store.save(new_dir)

        assert new_dir.exists()
        assert (new_dir / "vectors.npy").exists()
        assert (new_dir / "chunks.json").exists()
        assert (new_dir / "meta.json").exists()
