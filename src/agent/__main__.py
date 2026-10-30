"""Единая точка входа: `python -m src.agent <command>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.agent.config import load_config
from src.agent.logging_setup import setup_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description=(
            "AI Local Agent: локальный агент для заметок, документов и RAG."
        ),
    )
    sub = parser.add_subparsers(
        dest="command", required=True, metavar="<command>"
    )

    p_run = sub.add_parser("run", help="Выполнить одну задачу")
    p_run.add_argument("goal", help="Цель агента (текст)")

    p_ask = sub.add_parser(
        "ask",
        help="Спросить модель без инструментов (как 'ollama run')",
    )
    p_ask.add_argument(
        "goal",
        nargs="?",
        default=None,
        help="Вопрос. Если не указан — интерактивный режим",
    )
    
    sub.add_parser("chat", help="Интерактивный режим")

    p_index = sub.add_parser("index", help="Пересобрать RAG-индекс")
    p_index.add_argument(
        "--documents",
        type=Path,
        default=None,
        help="Корень документов (по умолчанию config.paths.documents_dir)",
    )
    p_index.add_argument(
        "--reset", action="store_true", help="Перезаписать индекс"
    )
    p_index.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Размер батча при эмбеддинге (по умолчанию 32)",
    )

    p_search = sub.add_parser(
        "search", help="Отладка retrieval (без LLM)"
    )
    p_search.add_argument("query", help="Поисковый запрос")
    p_search.add_argument(
        "--top-k", type=int, default=5, help="Сколько фрагментов вернуть"
    )
    p_search.add_argument(
        "--no-truncate",
        action="store_true",
        help="Не обрезать текст фрагментов до 200 символов",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except FileNotFoundError:
        print(
            "Не найден config/settings.toml. "
            "Скопируйте config/settings.example.toml в config/settings.toml."
        )
        sys.exit(1)

    logger = setup_logging(config.paths.logs_dir)

    if args.command == "run":
        from src.agent.cli import run_once

        run_once(args.goal, config, logger)

    elif args.command == "chat":
        from src.agent.cli import interactive_loop

        interactive_loop(config, logger)

    elif args.command == "ask":
        from src.agent.cli import ask_interactive, ask_once

        if args.goal:
            ask_once(args.goal, config, logger)
        else:
            ask_interactive(config, logger)
            
    elif args.command == "index":
        from src.agent.cli import build_index_cmd

        build_index_cmd(
            config=config,
            documents=args.documents,
            reset=args.reset,
            batch_size=args.batch_size,
            logger=logger,
        )

    elif args.command == "search":
        from src.agent.cli import search_cmd

        search_cmd(
            query=args.query,
            top_k=args.top_k,
            truncate=not args.no_truncate,
            config=config,
        )


if __name__ == "__main__":
    main()