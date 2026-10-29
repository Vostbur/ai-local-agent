"""CLI для отладки семантического поиска по документам (без LLM)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import load_config
from src.agent.logging_setup import setup_logging
from src.agent.tools.search_documents import search_documents


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search RAG index for relevant document fragments"
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Search query (natural language)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of fragments to return (default: 5)",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Print full fragment text (default: truncate to 200 chars)",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print(
            "Не найден config/settings.toml. "
            "Скопируйте config/settings.example.toml в config/settings.toml."
        )
        sys.exit(1)

    setup_logging(config.paths.logs_dir)

    try:
        results = search_documents(args.query, top_k=args.top_k)
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        print("Соберите индекс: python scripts/build_index.py --reset")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Ошибка поиска: {exc}")
        sys.exit(1)

    if not results:
        print("Ничего не найдено.")
        sys.exit(0)

    print(f"Найдено {len(results)} фрагментов по запросу: {args.query!r}")
    print()

    for i, r in enumerate(results, start=1):
        print(f"[{i}] score={r['score']}  {r['path']}  section={r['section']}")
        text = r["text"]
        if not args.no_truncate and len(text) > 200:
            text = text[:200] + "..."
        print(f"    {text}")
        print()


if __name__ == "__main__":
    main()