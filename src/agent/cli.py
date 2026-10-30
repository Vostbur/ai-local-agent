"""Функции подкоманд для `python -m src.agent`.

Логика вынесена из `scripts/*.py` без изменений. U4 (AgentService)
заменит это на сервисный слой с AsyncIterator[Event].
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.agent.app import build_orchestrator
from src.agent.config import AppConfig
from src.agent.orchestrator import MaxStepsExceeded
from src.agent.rag.build import build_index
from src.agent.tools.search_documents import search_documents


def _run_one(orchestrator, goal: str, logger: logging.Logger) -> None:
    """Выполнить одну задачу и напечатать результат."""
    print("[...] выполняется, подождите (на CPU это может занять несколько минут)")

    try:
        result = orchestrator.run(goal)
    except MaxStepsExceeded as exc:
        print(f"Достигнут лимит шагов: {exc}")
        return
    except RuntimeError as exc:
        exc_str = str(exc)
        if "Connection" in exc_str or "request failed" in exc_str:
            print(
                "Ollama не отвечает. Запустите 'ollama serve' "
                "в отдельном терминале и повторите."
            )
        else:
            print(f"Ошибка при обращении к модели: {exc}")
        return
    except KeyboardInterrupt:
        print("Прервано пользователем.")
        return

    if result.success:
        print(f"Готово: {result.final_answer}")
        print(f"Шагов: {result.steps_used}")
        if result.tool_results:
            print(f"Результаты инструментов: {result.tool_results}")
    else:
        print(f"Не удалось выполнить задачу. Шагов: {result.steps_used}")
        if result.error:
            print(f"Причина: {result.error}")


def run_once(goal: str, config: AppConfig, logger: logging.Logger) -> None:
    """`python -m src.agent run "цель"` — одна задача."""
    orchestrator = build_orchestrator(config, logger)
    _run_one(orchestrator, goal, logger)


def interactive_loop(config: AppConfig, logger: logging.Logger) -> None:
    """`python -m src.agent chat` — интерактивный режим."""
    orchestrator = build_orchestrator(config, logger)

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


def build_index_cmd(
    config: AppConfig,
    documents: Path | None,
    reset: bool,
    batch_size: int,
    logger: logging.Logger,
) -> None:
    """`python -m src.agent index` — пересборка RAG-индекса."""
    root = documents.resolve() if documents else config.paths.documents_dir

    try:
        store = build_index(
            root=root,
            config=config,
            reset=reset,
            batch_size=batch_size,
            logger=logger,
        )
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        sys.exit(1)
    except FileExistsError as exc:
        print(f"Ошибка: {exc}. Используйте --reset для перезаписи.")
        sys.exit(1)

    print(f"Готово: {len(store)} чанков в {config.paths.index_dir}")


def search_cmd(
    query: str,
    top_k: int,
    truncate: bool,
    config: AppConfig,
) -> None:
    """`python -m src.agent search "запрос"` — отладка retrieval без LLM."""
    try:
        results = search_documents(query, top_k=top_k)
    except FileNotFoundError as exc:
        print(f"Ошибка: {exc}")
        print("Соберите индекс: python -m src.agent index")
        sys.exit(1)

    if not results:
        print("Ничего не найдено.")
        return

    print(f"Найдено {len(results)} фрагментов по запросу: {query!r}")
    print()

    for i, r in enumerate(results, start=1):
        print(f"[{i}] score={r['score']}  {r['path']}  section={r['section']}")
        text = r["text"]
        if truncate and len(text) > 200:
            text = text[:200] + "..."
        print(f"    {text}")
        print()