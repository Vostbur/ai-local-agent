"""Тесты асинхронного режима веб-приложения."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import FastAPI

from src.agent.orchestrator import FinalEvent, OrchestratorResult, StepEvent
from src.agent.web.app import (
    TaskState,
    cleanup_expired_tasks,
    _run_task_async,
)


def _make_final_event(content="Готово", success=True):
    return FinalEvent(
        OrchestratorResult(
            success=success,
            final_answer=content,
            steps_used=1,
            tool_results=[],
        )
    )


@pytest.mark.anyio
async def test_run_task_async_success():
    """_run_task_async добавляет события и завершает задачу."""
    state = TaskState()
    service = MagicMock()

    async def fake_ask_async(goal):
        yield StepEvent(step=1, event_type="llm_call")
        yield _make_final_event("Ответ")

    service.ask_async = fake_ask_async

    await _run_task_async("task1", "цель", state, service, use_tools=True)

    assert len(state.events) == 3  # llm_call + final + None
    assert state.is_finished()
    assert state.finished_at is not None
    assert isinstance(state.events[0], StepEvent)
    assert isinstance(state.events[1], FinalEvent)
    assert state.events[2] is None


@pytest.mark.anyio
async def test_run_task_async_plain_mode():
    """_run_task_async использует ask_plain_async когда use_tools=False."""
    state = TaskState()
    service = MagicMock()

    async def fake_ask_plain(goal):
        yield _make_final_event("Чат без инструментов")

    service.ask_plain_async = fake_ask_plain

    await _run_task_async("task1", "привет", state, service, use_tools=False)

    assert len(state.events) == 2
    assert state.is_finished()
    assert state.events[0].result.final_answer == "Чат без инструментов"


@pytest.mark.anyio
async def test_run_task_async_handles_exception():
    """_run_task_async обрабатывает исключения и добавляет ошибку."""
    state = TaskState()
    service = MagicMock()

    async def failing_ask(goal):
        raise RuntimeError("Something went wrong")
        yield  # noqa: unreachable

    service.ask_async = failing_ask

    await _run_task_async("task1", "цель", state, service, use_tools=True)

    assert state.is_finished()
    final_event = state.events[0]
    assert isinstance(final_event, FinalEvent)
    assert final_event.result.success is False
    assert "Something went wrong" in final_event.result.error


@pytest.mark.anyio
async def test_run_task_async_cancellation():
    """_run_task_async корректно обрабатывает отмену."""
    state = TaskState()
    service = MagicMock()

    async def slow_ask(goal):
        await asyncio.sleep(60)
        yield _make_final_event("Не должно дойти")

    service.ask_async = slow_ask

    task = asyncio.create_task(
        _run_task_async("task1", "цель", state, service, use_tools=True)
    )
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # После отмены должно быть событие ошибки и сигнал завершения
    assert state.is_finished()
    # Ищем FinalEvent с ошибкой "cancelled"
    final_events = [e for e in state.events if isinstance(e, FinalEvent)]
    assert len(final_events) == 1
    assert final_events[0].result.error == "cancelled"


def test_cleanup_expired_tasks_with_async_task():
    """cleanup_expired_tasks отменяет живые асинхронные задачи при очистке."""
    app = FastAPI()
    app.state.tasks = {}

    # Завершенная задача старше 5 минут
    st1 = TaskState()
    st1.events.append(None)
    st1.mark_finished()
    st1.finished_at = time.time() - 400

    # Брошенная задача старше 2 часов с живой асинхронной задачей
    st2 = TaskState()
    st2.created_at = time.time() - 8000
    mock_async_task = MagicMock()
    mock_async_task.done.return_value = False
    st2.async_task = mock_async_task

    app.state.tasks = {"task1": st1, "task2": st2}

    deleted = cleanup_expired_tasks(app, time.time())

    assert deleted == 2
    assert "task1" not in app.state.tasks
    assert "task2" not in app.state.tasks
    mock_async_task.cancel.assert_called_once()