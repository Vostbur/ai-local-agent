"""Orchestrator — цикл plan-execute для агента."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.agent.llm import LLMClient
from src.agent.registry import ToolRegistry


class MaxStepsExceeded(Exception):
    pass


@dataclass
class OrchestratorResult:
    success: bool
    final_answer: str | None
    steps_used: int
    error: str | None = None


class Orchestrator:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        logger: logging.Logger,
        max_steps: int = 10,
        tool_context: dict[str, dict] | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.logger = logger
        self.max_steps = max_steps
        self.tool_context = tool_context or {}

    def run(self, goal: str) -> OrchestratorResult:
        messages: list[dict] = [{"role": "user", "content": goal}]

        for step in range(1, self.max_steps + 1):
            response = self.llm.chat(messages)
            self.logger.info("step=%d type=%s", step, response.type)

            if response.type == "final":
                self.logger.info("final: %s", response.content)
                return OrchestratorResult(
                    success=True,
                    final_answer=response.content,
                    steps_used=step,
                )

            if response.type == "tool_call":
                extra = self.tool_context.get(response.tool_name, {})
                arguments = {
                    **(response.tool_arguments or {}),
                    **extra,
                }
                try:
                    result = self.registry.call(
                        response.tool_name, **arguments
                    )
                except Exception as exc:
                    result = f"ERROR: {exc}"
                    self.logger.exception(
                        "tool %s failed", response.tool_name
                    )
                else:
                    self.logger.info(
                        "tool %s -> %s", response.tool_name, result
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            f"tool_call: {response.tool_name}({arguments})"
                        ),
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"tool_result: {result}",
                    }
                )

        raise MaxStepsExceeded(
            f"Достигнут лимит шагов: {self.max_steps}"
        )
