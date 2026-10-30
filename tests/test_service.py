"""Tests for AgentService: поток событий из Orchestrator."""

import logging
from pathlib import Path

import pytest

from src.agent.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    RAGConfig,
    SafetyConfig,
)
from src.agent.llm import FakeLLM, LLMResponse
from src.agent.orchestrator import (
    FinalEvent,
    MaxStepsExceeded,
    StepEvent,
)
from src.agent.registry import ToolDefinition, ToolRegistry
from src.agent.service import AgentService

logger = logging.getLogger("test")


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        llm=LLMConfig(model="test-model", max_steps=3),
        paths=PathsConfig(
            data_dir=tmp_path / "data",
            notes_dir=tmp_path / "data" / "notes",
            inbox_dir=tmp_path / "data" / "inbox",
            photos_dir=tmp_path / "data" / "photos",
            documents_dir=tmp_path / "data" / "documents",
            logs_dir=tmp_path / "logs",
            generated_dir=tmp_path / "data" / "generated",
            index_dir=tmp_path / "data" / "index",
        ),
        safety=SafetyConfig(),
        rag=RAGConfig(),
    )


def _make_service_with_fake_llm(
    tmp_path: Path, responses: list[LLMResponse], monkeypatch
) -> AgentService:
    """Собрать AgentService с FakeLLM вместо OllamaLLM."""
    config = _make_config(tmp_path)

    registry = ToolRegistry()
    def echo(text: str) -> str:
        return text
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            func=echo,
        )
    )

    fake_llm = FakeLLM(responses)
    monkeypatch.setattr(
        "src.agent.service.build_orchestrator",
        lambda config, logger: __import__(
            "src.agent.orchestrator", fromlist=["Orchestrator"]
        ).Orchestrator(fake_llm, registry, logger, max_steps=config.llm.max_steps),
    )

    return AgentService(config, logger)


class TestAsk:
    def test_final_only(self, tmp_path, monkeypatch):
        service = _make_service_with_fake_llm(
            tmp_path,
            [LLMResponse(type="final", content="done")],
            monkeypatch,
        )

        events = list(service.ask("goal"))

        assert isinstance(events[0], StepEvent)
        assert events[0].event_type == "llm_call"
        assert events[0].step == 1

        assert isinstance(events[1], StepEvent)
        assert events[1].event_type == "final"
        assert events[1].status == "ok"

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].result.success is True
        assert events[-1].result.final_answer == "done"

    def test_tool_call_then_final(self, tmp_path, monkeypatch):
        service = _make_service_with_fake_llm(
            tmp_path,
            [
                LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "hi"}),
                LLMResponse(type="final", content="done"),
            ],
            monkeypatch,
        )

        events = list(service.ask("goal"))

        types = [e.event_type for e in events if isinstance(e, StepEvent)]
        assert "tool_result" in types
        tool_events = [e for e in events if isinstance(e, StepEvent) and e.event_type == "tool_result"]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "echo"
        assert tool_events[0].status == "SUCCESS"

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].result.success is True

    def test_max_steps_returns_final_event(self, tmp_path, monkeypatch):
        service = _make_service_with_fake_llm(
            tmp_path,
            [
                LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "a"}),
                LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "b"}),
                LLMResponse(type="tool_call", tool_name="echo", tool_arguments={"text": "c"}),
            ],
            monkeypatch,
        )

        events = list(service.ask("goal"))

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].result.success is False
        assert "Достигнут лимит" in (events[-1].result.error or "")

    def test_runtime_error_returns_final_event(self, tmp_path, monkeypatch):
        class BoomLLM:
            def chat(self, messages):
                raise RuntimeError("Ollama request failed: Connection refused")

        registry = ToolRegistry()
        monkeypatch.setattr(
            "src.agent.service.build_orchestrator",
            lambda config, logger: __import__(
                "src.agent.orchestrator", fromlist=["Orchestrator"]
            ).Orchestrator(BoomLLM(), registry, logger, max_steps=3),
        )
        service = AgentService(_make_config(tmp_path), logger)

        events = list(service.ask("goal"))

        assert isinstance(events[-1], FinalEvent)
        assert events[-1].result.success is False
        assert "llm_error" in (events[-1].result.error or "")


class TestAskPlain:
    def test_final_only(self, tmp_path, monkeypatch):
        class FakeLLMPlain:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def chat(self, messages):
                return LLMResponse(type="final", content="answer")

        monkeypatch.setattr("src.agent.llm_ollama.OllamaLLM", FakeLLMPlain)
        service = AgentService(_make_config(tmp_path), logger)

        events = list(service.ask_plain("q"))

        assert len(events) == 1
        assert isinstance(events[0], FinalEvent)
        assert events[0].result.success is True
        assert events[0].result.final_answer == "answer"

    def test_empty_response(self, tmp_path, monkeypatch):
        class FakeLLMPlain:
            def __init__(self, **kwargs):
                pass

            def chat(self, messages):
                return LLMResponse(type="final", content="")

        monkeypatch.setattr("src.agent.llm_ollama.OllamaLLM", FakeLLMPlain)
        service = AgentService(_make_config(tmp_path), logger)

        events = list(service.ask_plain("q"))

        assert len(events) == 1
        assert events[0].result.success is False
        assert events[0].result.error == "empty final answer"

    def test_runtime_error(self, tmp_path, monkeypatch):
        class FakeLLMPlain:
            def __init__(self, **kwargs):
                pass

            def chat(self, messages):
                raise RuntimeError("Connection refused")

        monkeypatch.setattr("src.agent.llm_ollama.OllamaLLM", FakeLLMPlain)
        service = AgentService(_make_config(tmp_path), logger)

        events = list(service.ask_plain("q"))

        assert len(events) == 1
        assert events[0].result.success is False
        assert "llm_error" in (events[0].result.error or "")

    def test_uses_empty_tools(self, tmp_path, monkeypatch):
        captured = {}

        class FakeLLMPlain:
            def __init__(self, **kwargs):
                captured["tools"] = kwargs.get("tools")

            def chat(self, messages):
                return LLMResponse(type="final", content="ok")

        monkeypatch.setattr("src.agent.llm_ollama.OllamaLLM", FakeLLMPlain)
        service = AgentService(_make_config(tmp_path), logger)

        list(service.ask_plain("q"))

        assert captured["tools"] == []