"""DEPRECATED: используйте `python -m src.agent index`.

Оставлен для обратной совместимости.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.cli import build_index_cmd
from src.agent.config import load_config
from src.agent.logging_setup import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAG index from documents")
    parser.add_argument("--documents", type=Path, default=None)
    parser.add_argument("--reset", action="store_true", default=False)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print(
            "Не найден config/settings.toml. "
            "Скопируйте config/settings.example.toml в config/settings.toml."
        )
        sys.exit(1)

    logger = setup_logging(config.paths.logs_dir)
    build_index_cmd(
        config=config,
        documents=args.documents,
        reset=args.reset,
        batch_size=args.batch_size,
        logger=logger,
    )


if __name__ == "__main__":
    main()