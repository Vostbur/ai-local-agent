import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import load_config
from src.agent.logging_setup import setup_logging
from src.agent.rag.build import build_index


def main():
    parser = argparse.ArgumentParser(description="Build RAG index from documents")
    parser.add_argument("--documents", type=str, help="Path to documents directory")
    parser.add_argument("--reset", action="store_true", help="Reset existing index")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for processing")
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print("Ошибка: конфигурационный файл не найден")
        sys.exit(1)

    setup_logging(config.paths.logs_dir)

    root = Path(args.documents).resolve() if args.documents else config.paths.documents_dir

    try:
        store = build_index(root, config, reset=args.reset, batch_size=args.batch_size)
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    except FileExistsError as e:
        print(f"Ошибка: {e}. Используйте --reset для перезаписи.")
        sys.exit(1)

    print(f"Готово: {len(store)} чанков в {config.paths.index_dir}")


if __name__ == "__main__":
    main()
