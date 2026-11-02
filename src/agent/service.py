"""AgentService — единый интерфейс для CLI / web / других UI.

Собирает события оркестратора в поток `Iterator[Event]`.
Синхронные методы используются в CLI. Асинхронные методы используются
в FastAPI/SSE и позволяют не создавать отдельные потоки вручную.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Union

from src.agent.app import build_orchestrator
from src.agent.config import AppConfig
from src.agent.orchestrator import (
    FinalEvent,
    MaxStepsExceeded,
    Orchestrator,
    OrchestratorResult,
    StepEvent,
    sanitize_history,
)

Event = Union[StepEvent, FinalEvent]


class AgentService:
    """Обёртка над Orchestrator: поток событий вместо print в stdout."""

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._orchestrator: Orchestrator | None = None

    def _get_orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            self._orchestrator = build_orchestrator(self.config, self.logger)
        return self._orchestrator

    def _plain_messages(
        self, goal: str, history: list[dict] | None
    ) -> list[dict]:
        """Контекст для чата без инструментов: история + текущая реплика."""
        return [
            *sanitize_history(history),
            {"role": "user", "content": goal},
        ]

    # ------------------------------------------------------------------
    # Синхронные методы (для CLI и обратной совместимости)
    # ------------------------------------------------------------------

    def ask(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> Iterator[Event]:
        """Выполнить задачу с инструментами синхронно, выдать поток событий.

        ``history`` — предыдущие реплики диалога (T37).
        """
        events: list[StepEvent] = []
        result: OrchestratorResult | None = None

        try:
            orch = self._get_orchestrator()
            result = orch.run(goal, on_step=events.append, history=history)
        except MaxStepsExceeded as exc:
            result = OrchestratorResult(
                success=False,
                final_answer=None,
                steps_used=self.config.llm.max_steps,
                error=str(exc),
            )
        except RuntimeError as exc:
            result = OrchestratorResult(
                success=False,
                final_answer=None,
                steps_used=0,
                error=f"llm_error: {exc}",
            )

        yield from events
        yield FinalEvent(result)

    def ask_plain(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> Iterator[Event]:
        """Чат с моделью без инструментов синхронно. Один `FinalEvent` в конце."""
        from src.agent.llm_ollama import OllamaLLM

        llm = OllamaLLM(
            model=self.config.llm.model,
            base_url=self.config.llm.base_url,
            tools=[],
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )

        messages = self._plain_messages(goal, history)

        try:
            response = llm.chat(messages)
        except RuntimeError as exc:
            yield FinalEvent(
                OrchestratorResult(
                    success=False,
                    final_answer=None,
                    steps_used=1,
                    error=f"llm_error: {exc}",
                )
            )
            return

        if not response.content or not response.content.strip():
            yield FinalEvent(
                OrchestratorResult(
                    success=False,
                    final_answer=None,
                    steps_used=1,
                    error="empty final answer",
                )
            )
            return

        yield FinalEvent(
            OrchestratorResult(
                success=True,
                final_answer=response.content,
                steps_used=1,
                tool_results=[],
            )
        )

    # ------------------------------------------------------------------
    # Асинхронные методы (для FastAPI / SSE)
    # ------------------------------------------------------------------

    async def ask_async(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> AsyncIterator[Event]:
        """Выполнить задачу с инструментами асинхронно, выдать поток событий.

        ``history`` — предыдущие реплики диалога (T37).
        """
        orch = self._get_orchestrator()

        queue: asyncio.Queue[Event | None] = asyncio.Queue()

        def on_step(event: StepEvent) -> None:
            try:
                queue.put_nowait(event)
            except Exception:
                self.logger.exception("Failed to enqueue step event")

        async def runner() -> None:
            try:
                result = await orch.run_async(
                    goal, on_step=on_step, history=history
                )
                await queue.put(FinalEvent(result))
            except MaxStepsExceeded as exc:
                await queue.put(
                    FinalEvent(
                        OrchestratorResult(
                            success=False,
                            final_answer=None,
                            steps_used=self.config.llm.max_steps,
                            error=str(exc),
                        )
                    )
                )
            except RuntimeError as exc:
                await queue.put(
                    FinalEvent(
                        OrchestratorResult(
                            success=False,
                            final_answer=None,
                            steps_used=0,
                            error=f"llm_error: {exc}",
                        )
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Unexpected error in async ask")
                await queue.put(
                    FinalEvent(
                        OrchestratorResult(
                            success=False,
                            final_answer=None,
                            steps_used=0,
                            error=f"internal: {exc}",
                        )
                    )
                )
            finally:
                await queue.put(None)  # Сигнал завершения

        task = asyncio.create_task(runner())

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    async def ask_plain_async(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> AsyncIterator[Event]:
        """Чат с моделью без инструментов асинхронно."""
        from src.agent.llm_ollama import OllamaLLM

        llm = OllamaLLM(
            model=self.config.llm.model,
            base_url=self.config.llm.base_url,
            tools=[],
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )

        messages = self._plain_messages(goal, history)

        try:
            response = await llm.chat_async(messages)
        except RuntimeError as exc:
            yield FinalEvent(
                OrchestratorResult(
                    success=False,
                    final_answer=None,
                    steps_used=1,
                    error=f"llm_error: {exc}",
                )
            )
            return

        if not response.content or not response.content.strip():
            yield FinalEvent(
                OrchestratorResult(
                    success=False,
                    final_answer=None,
                    steps_used=1,
                    error="empty final answer",
                )
            )
            return

        yield FinalEvent(
            OrchestratorResult(
                success=True,
                final_answer=response.content,
                steps_used=1,
                tool_results=[],
            )
        )