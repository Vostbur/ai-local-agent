"""Integration tests for the RAG index builder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.agent.config import load_config
from src.agent.extractors.base import ExtractedDocument, Segment
from src.agent.rag.build import build_index
from src.agent.rag.store import VectorStore


@pytest.fixture()
def tmp_settings(tmp_path: Path) -> Path:
    """Create a minimal settings.toml with absolute index_dir in tmp_path."""
    settings = tmp_path / "settings.toml"
    index_dir = tmp_path / "index"
    settings.write_text(
        f"""\
[llm]
model = "test-model"
base_url = "http://localhost:11434"

[paths]
data_dir = "{(tmp_path / 'data').as_posix()}"
index_dir = "{index_dir.as_posix()}"

[rag]
embedding_model = "test-model"
chunk_size = 800
chunk_overlap = 100
""",
        encoding="utf-8",
    )
    return settings


@pytest.fixture()
def sample_documents(tmp_path: Path) -> Path:
    """Create a documents directory with 2 .md files."""
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()

    (docs_dir / "doc1.md").write_text(
        "# Doc 1\n\nSome content for the first document.\n",
        encoding="utf-8",
    )
    (docs_dir / "doc2.md").write_text(
        "# Doc 2\n\nSome content for the second document.\n",
        encoding="utf-8",
    )
    return docs_dir


class TestBuildIndexEndToEnd:
    """Test build_index with mocked Embedder — no real model loading."""

    def test_build_index_end_to_end(
        self,
        sample_documents: Path,
        tmp_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """2 .md files, mocked extract + embed, verify index files."""
        config = load_config(path=tmp_settings)

        monkeypatch.setattr(
            "src.agent.rag.build.iter_document_files",
            lambda root: sorted(sample_documents.rglob("*.md")),
        )

        def fake_extract(path: Path) -> ExtractedDocument:
            return ExtractedDocument(
                path=path,
                segments=[
                    Segment(
                        text="word " * 100,  # 500 chars < chunk_size=800 => 1 chunk
                        section="Intro",
                    )
                ],
                metadata={},
            )

        monkeypatch.setattr("src.agent.rag.build.extract_text", fake_extract)

        embed_dim = 384

        def fake_embed(self: object, texts: list[str]) -> np.ndarray:
            return np.random.rand(len(texts), embed_dim).astype(np.float32)

        monkeypatch.setattr(
            "src.agent.rag.embedder.Embedder.embed", fake_embed
        )

        store = build_index(
            root=sample_documents,
            config=config,
            reset=True,
            batch_size=32,
        )

        # 2 documents, 1 chunk each => 2 chunks
        assert isinstance(store, VectorStore)
        assert len(store) == 2
        assert store.vectors.shape == (2, embed_dim)

        index_dir = config.paths.index_dir
        assert (index_dir / "vectors.npy").exists()
        assert (index_dir / "chunks.json").exists()
        assert (index_dir / "meta.json").exists()

        chunks_data = json.loads(
            (index_dir / "chunks.json").read_text(encoding="utf-8")
        )
        assert len(chunks_data) == 2

        meta = json.loads(
            (index_dir / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["num_chunks"] == 2
        assert "created_at" in meta
        assert meta["embedding_model"] == "test-model"

    def test_build_index_no_chunks_returns_empty_store(
        self,
        tmp_path: Path,
        tmp_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty documents directory => empty VectorStore, nothing written."""
        config = load_config(path=tmp_settings)
        empty_docs = tmp_path / "empty_docs"
        empty_docs.mkdir()

        monkeypatch.setattr(
            "src.agent.rag.build.iter_document_files",
            lambda root: [],
        )

        store = build_index(root=empty_docs, config=config, reset=True)

        assert len(store) == 0
        # Индекс не должен быть записан на диск
        assert not (config.paths.index_dir / "vectors.npy").exists()


class TestBuildIndexRefusesOverwrite:
    """Test that build_index refuses to overwrite an existing index."""

    def test_build_index_refuses_overwrite_without_reset(
        self,
        sample_documents: Path,
        tmp_settings: Path,
    ) -> None:
        """Existing index, without reset => FileExistsError."""
        config = load_config(path=tmp_settings)
        index_dir = config.paths.index_dir
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "vectors.npy", np.zeros((3, 384), dtype=np.float32))
        (index_dir / "chunks.json").write_text("[]", encoding="utf-8")
        (index_dir / "meta.json").write_text("{}", encoding="utf-8")

        with pytest.raises(FileExistsError, match="index already exists"):
            build_index(
                root=sample_documents,
                config=config,
                reset=False,
            )

    def test_build_index_overwrites_with_reset(
        self,
        sample_documents: Path,
        tmp_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Existing index with reset=True => no FileExistsError."""
        config = load_config(path=tmp_settings)
        index_dir = config.paths.index_dir
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "vectors.npy", np.zeros((3, 384), dtype=np.float32))
        (index_dir / "chunks.json").write_text("[]", encoding="utf-8")
        (index_dir / "meta.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr(
            "src.agent.rag.build.iter_document_files",
            lambda root: [],
        )

        # reset=True — не должно быть FileExistsError, но чанков нет => пустой store
        store = build_index(
            root=sample_documents,
            config=config,
            reset=True,
        )

        assert len(store) == 0