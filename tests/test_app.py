"""Тесты для build_orchestrator."""

import logging
from pathlib import Path

from src.agent.app import build_orchestrator
from src.agent.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    RAGConfig,
    SafetyConfig,
    load_config,
)
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry


def _make_config() -> AppConfig:
    return AppConfig(
        llm=LLMConfig(
            model="test-model",
            base_url="http://localhost:11434",
            max_steps=3,
        ),
        paths=PathsConfig(
            data_dir=Path("data"),
            notes_dir=Path("data/notes"),
            inbox_dir=Path("data/inbox"),
            photos_dir=Path("data/photos"),
            logs_dir=Path("logs"),
            index_dir=Path("data/index"),
            documents_dir=Path("data/documents"),
        ),
        safety=SafetyConfig(
            confirm_file_operations=True,
        ),
        rag=RAGConfig(),
    )


def test_build_orchestrator_returns_orchestrator():
    config = _make_config()
    result = build_orchestrator(config, logging.getLogger("test"))
    assert isinstance(result, Orchestrator)


def test_registry_contains_save_note():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    tool = orch.registry.get("save_note")
    assert tool is not None
    assert tool.name == "save_note"


def test_tool_context_contains_save_note():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert "save_note" in orch.tool_context
    assert orch.tool_context["save_note"]["notes_dir"] == config.paths.notes_dir


def test_max_steps_matches_config():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.max_steps == config.llm.max_steps


def test_llm_model_matches_config():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.llm.model == config.llm.model


def test_build_orchestrator_registers_all_tools():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.registry.get("save_note") is not None
    assert orch.registry.get("read_notes") is not None
    assert orch.registry.get("search_notes") is not None
    assert orch.registry.get("search_documents") is not None


def test_tool_context_has_notes_dir_for_all_tools():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.tool_context["save_note"]["notes_dir"] == config.paths.notes_dir
    assert orch.tool_context["read_notes"]["notes_dir"] == config.paths.notes_dir
    assert orch.tool_context["search_notes"]["notes_dir"] == config.paths.notes_dir


def test_tool_context_not_set_for_search_documents():
    """search_documents работает с index_dir, а не с notes_dir."""
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert "search_documents" not in orch.tool_context


def test_toml_reaches_orchestrator_and_llm(tmp_path: Path):
    """TOML → AppConfig → Orchestrator.max_steps и OllamaLLM.model/base_url."""
    toml_file = tmp_path / "settings.toml"
    toml_file.write_text(
        """\
[llm]
model = "test-model-from-toml"
base_url = "http://test-host:11434"
max_steps = 7
""",
        encoding="utf-8",
    )

    config = load_config(toml_file)
    orch = build_orchestrator(config, logging.getLogger("test"))

    assert orch.max_steps == 7
    assert orch.llm.model == "test-model-from-toml"
    assert orch.llm.base_url == "http://test-host:11434"


def test_build_orchestrator_registers_read_and_write_document():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.registry.get("read_document") is not None
    assert orch.registry.get("write_document") is not None


def test_tool_context_has_output_dir_for_write_document():
    config = _make_config()
    orch = build_orchestrator(config, logging.getLogger("test"))
    assert orch.tool_context["write_document"]["output_dir"] == config.paths.generated_dir
    assert "read_document" not in orch.tool_context