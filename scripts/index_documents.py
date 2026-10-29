import argparse
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import load_config
from src.agent.logging_setup import setup_logging
from src.agent.indexer import index_documents, IndexResult, ExtractedDocument


def _make_progress_printer():
    def printer(i: int, total: int, path: Path, doc: ExtractedDocument | None) -> None:
        if doc is not None:
            print(f"[{i}/{total}] {path} → {len(doc.segments)} сегментов")
        else:
            print(f"[{i}/{total}] {path} → skip")
    return printer


def main():
    parser = argparse.ArgumentParser(description="Index documents for RAG")
    parser.add_argument("--documents", type=str, help="Корень корпуса документов. Перекрывает config.paths.documents_dir")
    parser.add_argument("--quiet", action="store_true", help="Не печатать прогресс по файлам")
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print("Не найден config/settings.toml...")
        sys.exit(1)

    setup_logging(config.paths.logs_dir)
    logger = logging.getLogger("agent")

    root = Path(args.documents).resolve() if args.documents else config.paths.documents_dir

    if not root.exists():
        print(f"Корень документов не существует: {root}")
        sys.exit(1)

    print(f"Документы: {root}")

    on_progress = None if args.quiet else _make_progress_printer()
    result = index_documents(root, logger, on_progress=on_progress)

    print()
    print(result.summary())


if __name__ == "__main__":
    main()
