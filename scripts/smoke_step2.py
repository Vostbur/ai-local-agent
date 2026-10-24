"""Smoke-тест: проверка ECHO-инструмента через ToolRegistry."""

import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH для импорта src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import load_config
from src.agent.logging_setup import setup_logging
from src.agent.registry import ToolRegistry
from src.agent.tools.stub import ECHO_TOOL


def main() -> None:
    config = load_config(Path("config", "settings.toml"))
    logger = setup_logging(config.paths.logs)

    registry = ToolRegistry()
    registry.register(ECHO_TOOL)

    result = registry.call("echo", text="hello")
    print(result)

    logger.info("Echo result: hello")


if __name__ == "__main__":
    main()
