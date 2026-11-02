"""Тесты асинхронного режима Orchestrator.run_async()."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from src.agent.llm import LLMResponse
from src.agent.orchestrator import Orchestrator


class AsyncFakeLLM:
    """LLM-заглушка с асинхронным chat_async()."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat_async(self, messages: list[dict]) -> LLMResponse:
        self.calls.append(messages)
        await asyncio.sleep(0)
        if not self.responses:
            raise RuntimeError("AsyncFakeLLM ran out of responses")
        return self.responses.pop(0)


class SyncOnlyFakeLLM:
    """LLM-заглушка без chat_async() для проверки fallback."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> LLMResponse:
        self.calls.append(messages)
        if not self.responses:
            raise RuntimeError("SyncOnlyFakeLLM ran out of responses")
        return self.responses.pop(0)


class FakeRegistry:
    """Registry-заглушка для тестов инструментов."""

    def __init__(self, result=None) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def call(self, name: str, **arguments):
        self.calls.append((name, arguments))
        return self.result


class SlowAsyncLLM:
    """LLM-заглушка, которая долго ждёт для проверки отмены."""

    async def chat_async(self, messages: list[dict]) -> LLMResponse:
        await asyncio.sleep(60)
        return LLMResponse(type="final", content="too late")


@pytest.mark.anyio
async def test_run_async_final_answer():
    """run_async() возвращает финальный ответ модели."""
    llm = AsyncFakeLLM(
        [LLMResponse(type="final", content="Готово")]
    )
    registry = FakeRegistry()
    orchestrator = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("test"),
    )

    result = await orchestrator.run_async("тест")

    assert result.success is True
    assert result.final_answer == "Готово"
    assert result.steps_used == 1
    assert result.tool_results == []
    assert len(llm.calls) == 1


@pytest.mark.anyio
async def test_run_async_serializes_tool_results():
    """run_async() сохраняет исправление JSON-сериализации tool_results."""
    llm = AsyncFakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="list_notes",
                tool_arguments={},
            ),
            LLMResponse(type="final", content="Нашёл заметки"),
        ]
    )
    registry = FakeRegistry(
        result=[
            {
                "path": Path("data/notes/test.md"),
                "title": "Тест",
                "category": None,
            }
        ]
    )
    orchestrator = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("test"),
    )

    result = await orchestrator.run_async("покажи заметки")

    assert result.success is True
    assert result.final_answer == "Нашёл заметки"
    assert result.tool_results == [
        [
            {
                "path": "data/notes/test.md",
                "title": "Тест",
                "category": None,
            }
        ]
    ]
    json.dumps(result.tool_results, ensure_ascii=False)
    assert registry.calls == [("list_notes", {})]


@pytest.mark.anyio
async def test_run_async_fallback_to_sync_chat():
    """run_async() работает со старым LLM-клиентом, у которого есть только chat()."""
    llm = SyncOnlyFakeLLM(
        [LLMResponse(type="final", content="Ответ через fallback")]
    )
    registry = FakeRegistry()
    orchestrator = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("test"),
    )

    result = await orchestrator.run_async("тест")

    assert result.success is True
    assert result.final_answer == "Ответ через fallback"
    assert len(llm.calls) == 1


@pytest.mark.anyio
async def test_run_async_emits_steps():
    """run_async() отдаёт события шагов через on_step."""
    llm = AsyncFakeLLM(
        [
            LLMResponse(
                type="tool_call",
                tool_name="list_notes",
                tool_arguments={},
            ),
            LLMResponse(type="final", content="Готово"),
        ]
    )
    registry = FakeRegistry(result=[])
    events = []

    orchestrator = Orchestrator(
        llm=llm,
        registry=registry,
        logger=logging.getLogger("test"),
    )

    result = await orchestrator.run_async("покажи заметки", on_step=events.append)

    assert result.success is True
    assert [event.event_type for event in events] == [
        "llm_call",
        "tool_result",
        "llm_call",
        "final",
    ]
    assert events[1].tool_name == "list_notes"
    assert events[1].status == "SUCCESS"
    assert events[-1].status == "ok"


@pytest.mark.anyio
async def test_run_async_can_be_cancelled_while_waiting_llm():
    """run_async() отменяется во время ожидания LLM."""
    orchestrator = Orchestrator(
        llm=SlowAsyncLLM(),
        registry=FakeRegistry(),
        logger=logging.getLogger("test"),
    )

    task = asyncio.create_task(orchestrator.run_async("долгий запрос"))
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task