"""Функции подкоманд для `python -m src.agent`."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.agent.config import AppConfig
from src.agent.orchestrator import FinalEvent, StepEvent
from src.agent.rag.build import build_index
from src.agent.service import AgentService


def _run_one(service: AgentService, goal: str, logger: logging.Logger) -> None:
    """Выполнить одну задачу через AgentService и напечатать результат."""
    print("[...] выполняется, подождите (на CPU это может занять несколько минут)")

    try:
        for event in service.ask(goal):
            if isinstance(event, StepEvent):
                if event.event_type == "tool_result":
                    count_str = (
                        f", {event.count} элементов"
                        if event.count is not None
                        else ""
                    )
                    print(
                        f"[шаг {event.step}] {event.tool_name} → "
                        f"{event.status}{count_str}"
                    )
                # llm_call и final не печатаем — они разом после завершения
            elif isinstance(event, FinalEvent):
                result = event.result
                if result.success:
                    print(f"Готово: {result.final_answer}")
                    print(f"Шагов: {result.steps_used}")
                    if result.tool_results:
                        print(f"Результаты инструментов: {result.tool_results}")
                else:
                    print(
                        f"Не удалось выполнить задачу. "
                        f"Шагов: {result.steps_used}"
                    )
                    if result.error:
                        print(f"Причина: {result.error}")
    except KeyboardInterrupt:
        print("Прервано пользователем.")


def run_once(goal: str, config: AppConfig, logger: logging.Logger) -> None:
    """`python -m agent run "цель"` — одна задача."""
    service = AgentService(config, logger)
    _run_one(service, goal, logger)


def interactive_loop(config: AppConfig, logger: logging.Logger) -> None:
    """`python -m agent chat` — интерактивный режим."""
    service = AgentService(config, logger)

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

        _run_one(service, goal, logger)


def build_index_cmd(
    config: AppConfig,
    documents: Path | None,
    reset: bool,
    batch_size: int,
    logger: logging.Logger,
) -> None:
    """`python -m agent index` — пересборка RAG-индекса."""
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
    """`python -m agent search "запрос"` — отладка retrieval без LLM."""
    from src.agent.tools.search_documents import make_search_documents_tool

    tool = make_search_documents_tool(config)

    try:
        results = tool.func(query, top_k=top_k)
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


def ask_once(
    goal: str, config: AppConfig, logger: logging.Logger
) -> None:
    """`python -m agent ask "вопрос"` — чат с моделью без tools."""
    service = AgentService(config, logger)

    print("[...] модель думает (на CPU это может занять несколько минут)")

    try:
        for event in service.ask_plain(goal):
            if isinstance(event, FinalEvent):
                result = event.result
                if result.success:
                    print(result.final_answer)
                elif result.error == "empty final answer":
                    print("Модель вернула пустой ответ.")
                elif result.error and "Connection" in result.error:
                    print(
                        "Ollama не отвечает. Запустите 'ollama serve' "
                        "в отдельном терминале и повторите."
                    )
                else:
                    print(f"Ошибка: {result.error}")
    except KeyboardInterrupt:
        print("Прервано пользователем.")


def ask_interactive(
    config: AppConfig, logger: logging.Logger
) -> None:
    """`python -m agent ask` — интерактивный чат без инструментов."""
    service = AgentService(config, logger)

    print(
        f"AI Local Agent — чат с моделью "
        f"(модель: {config.llm.model}, без инструментов)"
    )
    print("Введите вопрос или /quit для выхода.")

    while True:
        try:
            question = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            print("Выход.")
            return

        if not question.strip():
            continue

        if question.strip().lower() in {"/quit", "/exit", "exit", "quit"}:
            print("Выход.")
            return

        try:
            for event in service.ask_plain(question):
                if isinstance(event, FinalEvent):
                    result = event.result
                    if result.success:
                        print(result.final_answer)
                    elif result.error == "empty final answer":
                        print("(модель вернула пустой ответ)")
                    elif result.error and "Connection" in result.error:
                        print(
                            "Ollama не отвечает. Запустите "
                            "'ollama serve' и повторите."
                        )
                    else:
                        print(f"Ошибка: {result.error}")
        except KeyboardInterrupt:
            print()
            print("Выход.")
            return

        print()