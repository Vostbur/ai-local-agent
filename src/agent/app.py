"""Сборка Orchestrator из конфигурации."""

import logging

from src.agent.config import AppConfig
from src.agent.llm_ollama import OllamaLLM
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry
from src.agent.tools.save_note import SAVE_NOTE_TOOL
from src.agent.tools.read_notes import READ_NOTES_TOOL
from src.agent.tools.search_notes import SEARCH_NOTES_TOOL
from src.agent.tools.search_documents import SEARCH_DOCUMENTS_TOOL
from src.agent.tools.read_document import READ_DOCUMENT_TOOL
from src.agent.tools.write_document import WRITE_DOCUMENT_TOOL

ALL_TOOLS = [
    SAVE_NOTE_TOOL,
    READ_NOTES_TOOL,
    SEARCH_NOTES_TOOL,
    SEARCH_DOCUMENTS_TOOL,
    READ_DOCUMENT_TOOL,
    WRITE_DOCUMENT_TOOL,
]


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

    tool_context: dict[str, dict] = {}
    for tool in ALL_TOOLS:
        ctx: dict = {}
        if tool.needs_notes_dir:
            ctx["notes_dir"] = config.paths.notes_dir
        if tool.needs_output_dir:
            ctx["output_dir"] = config.paths.generated_dir
        if ctx:
            tool_context[tool.name] = ctx

    return Orchestrator(
        llm=llm,
        registry=registry,
        logger=logger,
        max_steps=config.llm.max_steps,
        tool_context=tool_context,
        max_tool_failures=config.safety.max_tool_retries,
    )