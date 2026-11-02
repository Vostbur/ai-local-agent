"""Тесты кэширования BM25-индекса на диске (T39)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.agent.rag.bm25 import BM25Index, compute_chunks_manifest
from src.agent.rag.chunker import Chunk
from src.agent.rag.store import VectorStore


def _chunk(
    text: str,
    path: str = "doc.md",
    index: int = 0,
    section: str | None = None,
) -> Chunk:
    return Chunk(text=text, path=Path(path), section=section, chunk_index=index)


def _chunks() -> list[Chunk]:
    return [
        _chunk("Как установить агент с нуля", "install.md", 0, "Установка"),
        _chunk("Требования к проекту и оперативной памяти", "req.md", 1, "Требования"),
        _chunk("Запуск агента через run_agent", "run.md", 2, "Запуск"),
    ]


def _store(chunks: list[Chunk]) -> VectorStore:
    rng = np.random.default_rng(42)
    vectors = rng.random((len(chunks), 8), dtype=np.float32)
    return VectorStore(
        vectors=vectors,
        chunks=chunks,
        meta={"num_chunks": len(chunks)},
    )


def _results(index: BM25Index, query: str, top_k: int = 3):
    return [
        (c.chunk_index, round(score, 10))
        for c, score in index.search(query, top_k=top_k)
    ]


# ----------------------------------------------------------------------
# to_dict / from_dict
# ----------------------------------------------------------------------

def test_to_dict_from_dict_roundtrip_search_equal():
    chunks = _chunks()
    original = BM25Index(chunks)
    restored = BM25Index.from_dict(original.to_dict(), chunks)

    for query in ("установить", "памяти требования", "run_agent"):
        assert _results(original, query) == _results(restored, query)


def test_from_dict_does_not_retokenize():
    """Восстановленный индекс не хранит токены (маркер кэша)."""
    chunks = _chunks()
    restored = BM25Index.from_dict(BM25Index(chunks).to_dict(), chunks)
    assert restored._doc_tokens == []


def test_from_dict_rejects_manifest_mismatch():
    chunks = _chunks()
    state = BM25Index(chunks).to_dict()
    other = _chunks()
    other[0].text = "Совершенно другой текст чанка"
    with pytest.raises(ValueError):
        BM25Index.from_dict(state, other)


def test_from_dict_rejects_num_chunks_mismatch():
    chunks = _chunks()
    state = BM25Index(chunks).to_dict()
    with pytest.raises(ValueError):
        BM25Index.from_dict(state, chunks[:2])


def test_from_dict_rejects_unknown_format_version():
    chunks = _chunks()
    state = BM25Index(chunks).to_dict()
    state["format_version"] = 999
    with pytest.raises(ValueError):
        BM25Index.from_dict(state, chunks)


def test_manifest_changes_with_text():
    chunks = _chunks()
    same = _chunks()
    assert compute_chunks_manifest(chunks) == compute_chunks_manifest(same)
    same[1].text = "отредактировано"
    assert compute_chunks_manifest(chunks) != compute_chunks_manifest(same)


# ----------------------------------------------------------------------
# VectorStore.save / load
# ----------------------------------------------------------------------

def test_store_save_writes_bm25_cache(tmp_path):
    _store(_chunks()).save(tmp_path)
    assert (tmp_path / "bm25.json").exists()


def test_store_load_uses_cache_and_search_works(tmp_path):
    chunks = _chunks()
    _store(chunks).save(tmp_path)

    loaded = VectorStore.load(tmp_path)

    assert loaded._bm25 is not None
    # Индекс восстановлен из кэша, а не перетокенизирован
    assert loaded._bm25._doc_tokens == []
    fresh = BM25Index(chunks)
    assert _results(loaded._bm25, "установить агент") == _results(
        fresh, "установить агент"
    )


def test_store_load_falls_back_on_manifest_mismatch(tmp_path):
    chunks = _chunks()
    _store(chunks).save(tmp_path)

    bm25_path = tmp_path / "bm25.json"
    data = json.loads(bm25_path.read_text(encoding="utf-8"))
    data["manifest"] = "0" * 64
    bm25_path.write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    loaded = VectorStore.load(tmp_path)

    # Кэш отклонён: индекс пересобирается лениво из чанков
    assert loaded._bm25 is None
    rebuilt = loaded._ensure_bm25()
    assert rebuilt._doc_tokens
    assert _results(rebuilt, "установить") == _results(
        BM25Index(chunks), "установить"
    )


def test_store_load_falls_back_on_broken_json(tmp_path):
    chunks = _chunks()
    _store(chunks).save(tmp_path)
    (tmp_path / "bm25.json").write_text("{not json", encoding="utf-8")

    loaded = VectorStore.load(tmp_path)

    assert loaded._bm25 is None
    assert loaded._ensure_bm25()._doc_tokens


def test_store_load_without_cache_file(tmp_path):
    chunks = _chunks()
    _store(chunks).save(tmp_path)
    (tmp_path / "bm25.json").unlink()

    loaded = VectorStore.load(tmp_path)

    assert loaded._bm25 is None
    assert loaded._ensure_bm25()._doc_tokens


def test_search_hybrid_works_after_cache_load(tmp_path):
    chunks = _chunks()
    _store(chunks).save(tmp_path)

    loaded = VectorStore.load(tmp_path)
    qvec = np.ones(8, dtype=np.float32)
    results = loaded.search_hybrid("установить агент", qvec, top_k=2)

    assert len(results) >= 1


def test_empty_store_roundtrip(tmp_path):
    store = VectorStore(
        vectors=np.zeros((0, 0), dtype=np.float32), chunks=[], meta={}
    )
    store.save(tmp_path)

    loaded = VectorStore.load(tmp_path)

    assert loaded._bm25 is not None
    assert loaded._bm25.search("что угодно") == []