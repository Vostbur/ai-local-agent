"""Тесты для build_orchestrator."""

import logging
from pathlib import Path

from src.agent.app import build_orchestrator
from src.agent.config import AppConfig, LLMConfig, PathsConfig, SafetyConfig
from src.agent.orchestrator import Orchestrator
from src.agent.registry import ToolRegistry


def _make_config() -> AppConfig:
    return AppConfig(
        llm=LLMConfig(
            provider="ollama",
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
        ),
        safety=SafetyConfig(
            confirm_file_operations=True,
        ),
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
