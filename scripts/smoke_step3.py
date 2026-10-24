"""Smoke test: step 3 — save_note + logging."""

import sys
from pathlib import Path

# Add project root to sys.path so `src` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.logging_setup import setup_logging
from src.agent.tools.save_note import save_note


def main() -> None:
    setup_logging(Path("logs"))

    path1 = save_note("Тестовая заметка", "Первый текст", Path("data/notes"))
    print(path1)

    path2 = save_note("Тестовая заметка", "Второй текст", Path("data/notes"))
    print(path2)

    print(path1.read_text(encoding="utf-8"))
    print(path2.read_text(encoding="utf-8"))

    logger = setup_logging(Path("logs"))
    logger.info("Smoke step 3 done")


if __name__ == "__main__":
    main()
