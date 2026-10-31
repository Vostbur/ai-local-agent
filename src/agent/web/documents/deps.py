"""Адаптер для работы с документами и RAG-индексом."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agent.rag.store import VectorStore
from agent.rag.build import build_index
from agent.indexer import iter_document_files

def documents_dir(cfg: Any) -> Path:
    if cfg and hasattr(cfg, "paths") and hasattr(cfg.paths, "documents_dir"):
        return cfg.paths.documents_dir
    return Path("data/documents")

def index_dir(cfg: Any) -> Path:
    if cfg and hasattr(cfg, "paths") and hasattr(cfg.paths, "index_dir"):
        return cfg.paths.index_dir
    return Path("data/index")

def get_indexed_files(cfg: Any) -> dict[str, int]:
    """Возвращает {путь: количество чанков}."""
    idir = index_dir(cfg)
    if not idir.exists():
        return {}
    try:
        store = VectorStore.load(idir)
        counts = {}
        for chunk in store.chunks:
            counts[chunk.path] = counts.get(chunk.path, 0) + 1
        return counts
    except Exception:
        return {}

def list_files(cfg: Any) -> list[dict]:
    """Возвращает список файлов в documents_dir с их статусом индексации."""
    ddir = documents_dir(cfg)
    if not ddir.exists():
        return []

    indexed = get_indexed_files(cfg)
    files = []
    
    for p in iter_document_files(ddir):
        rel_path = str(p.relative_to(ddir)).replace("\\", "/")
        stat = p.stat()
        files.append({
            "path": rel_path,
            "full_path": str(p),
            "name": p.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_indexed": rel_path in indexed,
            "chunks": indexed.get(rel_path, 0),
            "suffix": p.suffix.lower().lstrip(".")
        })
    
    # Сортируем по дате изменения (сначала новые)
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files

def save_uploaded_file(cfg: Any, filename: str, file_obj: Any) -> None:
    ddir = documents_dir(cfg)
    ddir.mkdir(parents=True, exist_ok=True)
    target = ddir / filename
    with target.open("wb") as buffer:
        shutil.copyfileobj(file_obj, buffer)

def delete_file(cfg: Any, rel_path: str) -> bool:
    ddir = documents_dir(cfg)
    target = ddir / rel_path
    if target.exists() and target.is_file():
        target.unlink()
        return True
    return False

def rebuild_index(cfg: Any, reset: bool = True) -> dict:
    """Запускает полную переиндексацию папки documents_dir."""
    ddir = documents_dir(cfg)
    try:
        store = build_index(root=ddir, config=cfg, reset=reset, batch_size=32)
        return {"success": True, "chunks": len(store), "error": None}
    except Exception as e:
        return {"success": False, "chunks": 0, "error": str(e)}