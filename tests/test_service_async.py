"""Тесты асинхронного режима AgentService."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.agent.llm import LLMResponse
from src.agent.orchestrator import FinalEvent, StepEvent
from src.agent.service import AgentService


def _make_config():
    """Создать мок конфигуции для тестов."""
    config = MagicMock()
    config.llm.model = "test-model"
    config.llm.base_url = "http://localhost:11434"
    config.llm.temperature = 0.7
    config.llm.max_tokens = 1000
    config.llm.max_steps = 5
    config.paths.notes_dir = MagicMock()
    config.paths.generated_dir = MagicMock()
    config.paths.trash_dir = MagicMock()
    config.paths.documents_dir = MagicMock()
    config.paths.index_dir = MagicMock()
    config.safety.max_tool_retries = 2
    return config


@pytest.mark.anyio
async def test_ask_plain_async_success():
    """ask_plain_async возвращает ответ модели."""
    config = _make_config()
    logger = logging.getLogger("test")
    service = AgentService(config, logger)

    mock_response = LLMResponse(type="final", content="Привет!")

    with patch("src.agent.llm_ollama.OllamaLLM.chat_async", return_value=mock_response):
        events = []
        async for event in service.ask_plain_async("привет"):
            events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], FinalEvent)
    assert events[0].result.success is True
    assert events[0].result.final_answer == "Привет!"


@pytest.mark.anyio
async def test_ask_plain_async_empty_answer():
    """ask_plain_async обрабатывает пустой ответ."""
    config = _make_config()
    logger = logging.getLogger("test")
    service = AgentService(config, logger)

    mock_response = LLMResponse(type="final", content="")

    with patch("src.agent.llm_ollama.OllamaLLM.chat_async", return_value=mock_response):
        events = []
        async for event in service.ask_plain_async("привет"):
            events.append(event)

    assert len(events) == 1
    assert events[0].result.success is False
    assert events[0].result.error == "empty final answer"


@pytest.mark.anyio
async def test_ask_plain_async_llm_error():
    """ask_plain_async обрабатывает ошибку LLM."""
    config = _make_config()
    logger = logging.getLogger("test")
    service = AgentService(config, logger)

    with patch(
        "src.agent.llm_ollama.OllamaLLM.chat_async",
        side_effect=RuntimeError("Connection refused"),
    ):
        events = []
        async for event in service.ask_plain_async("привет"):
            events.append(event)

    assert len(events) == 1
    assert events[0].result.success is False
    assert "llm_error" in events[0].result.error


@pytest.mark.anyio
async def test_ask_async_streams_events():
    """ask_async отдаёт события шагов и финал."""
    config = _make_config()
    logger = logging.getLogger("test")
    service = AgentService(config, logger)

    # Мокаем оркестратор
    mock_orch = MagicMock()

    async def fake_run_async(goal, on_step=None):
        if on_step:
            on_step(StepEvent(step=1, event_type="llm_call"))
            on_step(
                StepEvent(
                    step=1,
                    event_type="tool_result",
                    tool_name="list_notes",
                    status="SUCCESS",
                )
            )
        from src.agent.orchestrator import OrchestratorResult
        return OrchestratorResult(
            success=True,
            final_answer="Готово",
            steps_used=1,
            tool_results=[],
        )

    mock_orch.run_async = fake_run_async
    service._orchestrator = mock_orch

    events = []
    async for event in service.ask_async("покажи заметки"):
        events.append(event)

    assert len(events) == 3
    assert isinstance(events[0], StepEvent)
    assert events[0].event_type == "llm_call"
    assert isinstance(events[1], StepEvent)
    assert events[1].tool_name == "list_notes"
    assert isinstance(events[2], FinalEvent)
    assert events[2].result.success is True
    assert events[2].result.final_answer == "Готово"


@pytest.mark.anyio
async def test_ask_async_handles_max_steps_exceeded():
    """ask_async обрабатывает превышение лимита шагов."""
    from src.agent.orchestrator import MaxStepsExceeded

    config = _make_config()
    logger = logging.getLogger("test")
    service = AgentService(config, logger)

    mock_orch = MagicMock()

    async def fake_run_async(goal, on_step=None):
        raise MaxStepsExceeded("Достигнут лимит шагов: 5")

    mock_orch.run_async = fake_run_async
    service._orchestrator = mock_orch

    events = []
    async for event in service.ask_async("долгая задача"):
        events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], FinalEvent)
    assert events[0].result.success is False
    assert "лимит шагов" in events[0].result.error