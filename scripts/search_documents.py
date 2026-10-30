"""DEPRECATED: используйте `python -m src.agent search "запрос"`.

Оставлен для обратной совместимости.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.cli import search_cmd
from src.agent.config import load_config
from src.agent.logging_setup import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search RAG index for relevant document fragments"
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-truncate", action="store_true")
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
    search_cmd(
        query=args.query,
        top_k=args.top_k,
        truncate=not args.no_truncate,
        config=config,
    )


if __name__ == "__main__":
    main()