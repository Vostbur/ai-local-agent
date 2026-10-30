"""AgentService — единый интерфейс для CLI / web / других UI.

Собирает события оркестратора в поток `Iterator[Event]`. Sync, потому что
на CPU модель синхронная; web в U5 обернёт в async / SSE.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Union

from src.agent.app import build_orchestrator
from src.agent.config import AppConfig
from src.agent.orchestrator import (
    FinalEvent,
    MaxStepsExceeded,
    Orchestrator,
    OrchestratorResult,
    StepEvent,
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

    def ask(self, goal: str) -> Iterator[Event]:
        """Выполнить задачу с инструментами, выдать поток событий.

        События копятся во время `Orchestrator.run` и выдаются после
        завершения. Для CLI разницы нет; для SSE (U5) клиент получит
        все события разом, но отрендерит по одному. Настоящий
        live-stream — U6 (стриминг Ollama).
        """
        events: list[StepEvent] = []
        result: OrchestratorResult | None = None

        try:
            orch = self._get_orchestrator()
            result = orch.run(goal, on_step=events.append)
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

    def ask_plain(self, goal: str) -> Iterator[Event]:
        """Чат с моделью без инструментов. Один `FinalEvent` в конце."""
        from src.agent.llm_ollama import OllamaLLM

        llm = OllamaLLM(
            model=self.config.llm.model,
            base_url=self.config.llm.base_url,
            tools=[],
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )

        try:
            response = llm.chat([{"role": "user", "content": goal}])
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