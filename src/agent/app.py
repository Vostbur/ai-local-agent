"""Сборка Orchestrator из конфигурации."""

import logging

from src.agent.config import AppConfig
from src.agent.llm_ollama import OllamaLLM
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry
from src.agent.tools.save_note import SAVE_NOTE_TOOL
from src.agent.tools.read_notes import READ_NOTES_TOOL
from src.agent.tools.search_notes import SEARCH_NOTES_TOOL


def build_orchestrator(
    config: AppConfig, logger: logging.Logger | None = None
) -> Orchestrator:
    logger = logger or logging.getLogger("agent")

    registry = ToolRegistry()
    registry.register(SAVE_NOTE_TOOL)
    registry.register(READ_NOTES_TOOL)
    registry.register(SEARCH_NOTES_TOOL)

    tools = [SAVE_NOTE_TOOL, READ_NOTES_TOOL, SEARCH_NOTES_TOOL]

    llm = OllamaLLM(
        model=config.llm.model,
        base_url=config.llm.base_url,
        tools=tools,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    tool_context = {
        "save_note": {"notes_dir": config.paths.notes_dir},
        "read_notes": {"notes_dir": config.paths.notes_dir},
        "search_notes": {"notes_dir": config.paths.notes_dir},
    }

    return Orchestrator(
        llm=llm,
        registry=registry,
        logger=logger,
        max_steps=config.llm.max_steps,
        tool_context=tool_context,
    )
