"""Запуск агента: CLI и интерактивный режим."""

import argparse
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.app import build_orchestrator
from src.agent.config import load_config
from src.agent.logging_setup import setup_logging
from src.agent.orchestrator import MaxStepsExceeded


def _run_one(orchestrator, goal: str, logger: logging.Logger) -> None:
    print("[...] выполняется, подождите (на CPU это может занять несколько минут)")

    try:
        result = orchestrator.run(goal)
    except MaxStepsExceeded as exc:
        print(f"Достигнут лимит шагов: {exc}")
        return
    except RuntimeError as exc:
        exc_str = str(exc)
        if "Connection" in exc_str or "request failed" in exc_str:
            print("Ollama не отвечает. Запустите 'ollama serve' в отдельном терминале и повторите.")
        else:
            print(f"Ошибка при обращении к модели: {exc}")
        return
    except KeyboardInterrupt:
        print("Прервано пользователем.")
        return

    if result.success:
        print(f"Готово: {result.final_answer}")
        print(f"Шагов: {result.steps_used}")
        tool_results = getattr(result, "tool_results", [])
        if tool_results:
            print(f"Результаты инструментов: {tool_results}")
    else:
        print(f"Не удалось выполнить задачу. Шагов: {result.steps_used}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Local Agent")
    parser.add_argument("goal", nargs="?", help="Цель одной задачей. Если не указана — интерактивный режим.")
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError:
        print("Не найден config/settings.toml. Скопируйте config/settings.example.toml в config/settings.toml.")
        sys.exit(1)

    logger = setup_logging(config.paths.logs)

    orchestrator = build_orchestrator(config, logger)

    if args.goal:
        _run_one(orchestrator, args.goal, logger)
        return

    print(f"AI Local Agent (модель: {config.llm.model})")
    print("Введите цель или /quit для выхода.")

    while True:
        try:
            goal = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            print("Выход.")
            return

        if not goal.strip():
            continue

        if goal.strip().lower() in {"/quit", "/exit", "exit", "quit"}:
            print("Выход.")
            return

        _run_one(orchestrator, goal, logger)


if __name__ == "__main__":
    main()
