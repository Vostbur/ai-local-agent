"""DEPRECATED: используйте `python -m src.agent run "цель"` или `python -m src.agent chat`.

Оставлен для обратной совместимости.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.cli import interactive_loop, run_once
from src.agent.config import load_config
from src.agent.logging_setup import setup_logging


def main() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print(
            "Не найден config/settings.toml. "
            "Скопируйте config/settings.example.toml в config/settings.toml."
        )
        sys.exit(1)

    logger = setup_logging(config.paths.logs_dir)

    if len(sys.argv) > 1:
        run_once(sys.argv[1], config, logger)
    else:
        interactive_loop(config, logger)


if __name__ == "__main__":
    main()