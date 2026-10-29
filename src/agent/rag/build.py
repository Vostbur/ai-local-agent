"""Build RAG index from document files."""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
import time
from pathlib import Path

import numpy as np

from src.agent.config import AppConfig, load_config
from src.agent.extractors import extract_text
from src.agent.indexer import iter_document_files
from src.agent.logging_setup import setup_logging
from src.agent.rag.chunker import Chunk, chunk_document
from src.agent.rag.embedder import Embedder
from src.agent.rag.store import VectorStore


def build_index(
    root: Path,
    config: AppConfig,
    reset: bool = False,
    batch_size: int = 32,
    logger: logging.Logger | None = None,
) -> VectorStore:
    """Build a RAG vector index from documents under *root*.

    Args:
        root: Directory containing document files.
        config: Application configuration.
        reset: If True, overwrite an existing index.
        batch_size: Batch size for embedding (passed through Embedder).
        logger: Optional pre-configured logger.

    Returns:
        A :class:`VectorStore` instance. If no chunks were extracted,
        returns an empty store without writing to disk.

    Raises:
        FileNotFoundError: If *root* does not exist.
        FileExistsError: If an index already exists and *reset* is False.
    """

    if not root.exists():
        raise FileNotFoundError(f"documents root does not exist: {root}")

    index_dir = config.paths.index_dir
    vectors_path = index_dir / "vectors.npy"
    if vectors_path.exists() and not reset:
        raise FileExistsError(
            f"index already exists at {index_dir}, use --reset to overwrite"
        )

    files = iter_document_files(root)
    total = len(files)
    all_chunks: list[Chunk] = []

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{total}] {path}", end="")
        doc = extract_text(path)
        if doc is None:
            print(" skip")
            continue
        chunks = chunk_document(doc, config.rag.chunk_size, config.rag.chunk_overlap)
        all_chunks.extend(chunks)
        print(f" -> {len(chunks)} chunks")

    print(f"Собрано: {len(all_chunks)} чанков из {total} файлов")

    meta = {
        "embedding_model": config.rag.embedding_model,
        "chunk_size": config.rag.chunk_size,
        "chunk_overlap": config.rag.chunk_overlap,
        "num_chunks": len(all_chunks),
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    if not all_chunks:
        print("no chunks extracted, nothing to index")
        return VectorStore(
            vectors=np.zeros((0, 0), dtype=np.float32),
            chunks=[],
            meta=meta,
        )

    embedder = Embedder(config.rag.embedding_model)
    print("Загрузка модели эмбеддингов (первый раз — скачивание ~470 МБ)...")

    texts = [c.text for c in all_chunks]
    start = time.time()
    vectors = embedder.embed(texts)
    elapsed = time.time() - start

    print(f"Эмбеддинги: shape={vectors.shape}, за {elapsed:.1f}с")

    store = VectorStore(vectors=vectors, chunks=all_chunks, meta=meta)
    store.save(index_dir)
    print(f"Индекс сохранён в {index_dir}: {len(store)} чанков")

    return store


def main() -> None:
    """CLI entry-point for building the RAG index."""

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    parser = argparse.ArgumentParser(description="Build RAG index from documents")
    parser.add_argument(
        "--documents",
        type=Path,
        default=None,
        help="Override config paths.documents_dir",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Overwrite existing index",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding (default: 32)",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print(
            "config/settings.toml not found. "
            "Copy config/settings.example.toml to config/settings.toml."
        )
        sys.exit(1)

    setup_logging(config.paths.logs_dir)
    logger = logging.getLogger("agent")

    root = args.documents.resolve() if args.documents else config.paths.documents_dir

    try:
        store = build_index(
            root=root,
            config=config,
            reset=args.reset,
            batch_size=args.batch_size,
            logger=logger,
        )
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        sys.exit(1)
    except FileExistsError as exc:
        print(f"Ошибка: {exc}")
        sys.exit(1)

    if len(store) == 0:
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
