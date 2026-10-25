"""Сборка Orchestrator из конфигурации."""

import logging

from src.agent.config import AppConfig
from src.agent.llm_ollama import OllamaLLM
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry
from src.agent.tools.save_note import SAVE_NOTE_TOOL


def build_orchestrator(
    config: AppConfig, logger: logging.Logger | None = None
) -> Orchestrator:
    logger = logger or logging.getLogger("agent")

    registry = ToolRegistry()
    registry.register(SAVE_NOTE_TOOL)

    tools = [SAVE_NOTE_TOOL]

    llm = OllamaLLM(
        model=config.llm.model,
        base_url=config.llm.base_url,
        tools=tools,
    )

    tool_context = {
        "save_note": {"notes_dir": config.paths.notes_dir}
    }

    return Orchestrator(
        llm=llm,
        registry=registry,
        logger=logger,
        max_steps=config.llm.max_steps,
        tool_context=tool_context,
    )
