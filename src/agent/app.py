"""Сборка Orchestrator из конфигурации."""

import logging

from src.agent.config import AppConfig
from src.agent.llm_ollama import OllamaLLM
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry
from src.agent.tools.save_note import SAVE_NOTE_TOOL
from src.agent.tools.read_notes import READ_NOTES_TOOL
from src.agent.tools.search_notes import SEARCH_NOTES_TOOL

ALL_TOOLS = [SAVE_NOTE_TOOL, READ_NOTES_TOOL, SEARCH_NOTES_TOOL]

TOOLS_WITH_NOTES_DIR = ("save_note", "read_notes", "search_notes")


def build_orchestrator(
    config: AppConfig, logger: logging.Logger | None = None
) -> Orchestrator:
    logger = logger or logging.getLogger("agent")

    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)

    llm = OllamaLLM(
        model=config.llm.model,
        base_url=config.llm.base_url,
        tools=ALL_TOOLS,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    tool_context = {
        name: {"notes_dir": config.paths.notes_dir}
        for name in TOOLS_WITH_NOTES_DIR
    }

    return Orchestrator(
        llm=llm,
        registry=registry,
        logger=logger,
        max_steps=config.llm.max_steps,
        tool_context=tool_context,
        max_tool_failures=config.safety.max_tool_retries,
    )